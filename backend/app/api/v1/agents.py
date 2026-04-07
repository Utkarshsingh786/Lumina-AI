"""
Agent workflow endpoints — planner/executor pattern with run persistence.

An "agent workflow" is a named, multi-step prompt chain where each step
can use tools, reference prior step outputs, and stream its progress back
to the client via SSE.  Every run is persisted to the database so users
can view history, inspect outputs, and re-run past workflows.

Endpoints:
  GET  /agents/workflows           — list all available workflows + available models
  POST /agents/run                 — execute a workflow, SSE-streaming progress
  GET  /agents/runs                — paginated list of past runs (metadata only)
  GET  /agents/runs/{run_id}       — full run detail including step content
  DELETE /agents/runs/{run_id}     — delete a run record

SSE event types emitted by POST /agents/run:
  {"type": "run_created", "run_id": str}
  {"type": "step_start",  "step": int, "name": str, "total_steps": int}
  {"type": "token",       "content": str}
  {"type": "step_done",   "step": int, "name": str, "tokens": int}
  {"type": "done",        "run_id": str, "steps_completed": int, "total_tokens": int}
  {"type": "error",       "message": str}

Built-in workflows:
  research_assistant  — web search + synthesis into a structured report
  code_review         — analyse code for bugs, security issues, style
  data_analysis       — summarise data, suggest visualisations
  document_summary    — condense a long document into key points + action items
  brainstorm          — generate diverse ideas then rank them
"""

import asyncio
import json as _json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_chat_rate_limit
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.models.workflow_run import WorkflowRun

router = APIRouter(prefix="/agents", tags=["agents"])


# ── Workflow schema ────────────────────────────────────────────────────────────

class WorkflowStep(BaseModel):
    name: str
    prompt_template: str   # may contain {input}, {step_N_output} placeholders
    use_tools: bool = False
    max_tokens: int = 2048


class Workflow(BaseModel):
    id: str
    name: str
    description: str
    steps: list[WorkflowStep]
    icon: str = "⚡"


class RunWorkflowRequest(BaseModel):
    workflow_id: str = Field(..., description="ID of the workflow to run")
    input: str = Field(..., min_length=1, max_length=16_000, description="User-provided input text")
    model: str | None = Field(default=None, description="Override model for this run")


# ── Built-in workflows ─────────────────────────────────────────────────────────

_BUILT_IN_WORKFLOWS: list[Workflow] = [
    Workflow(
        id="research_assistant",
        name="Research Assistant",
        description="Search the web, synthesise findings, and produce a structured research report with citations.",
        icon="🔬",
        steps=[
            WorkflowStep(
                name="Plan research queries",
                prompt_template=(
                    "You are a research planner. Given the research topic below, produce "
                    "3-5 focused search queries that will collectively cover the topic well.\n\n"
                    "Topic: {input}\n\n"
                    "Output a numbered list of search queries only."
                ),
                use_tools=False,
                max_tokens=256,
            ),
            WorkflowStep(
                name="Search and gather information",
                prompt_template=(
                    "You are a research analyst. Use the web_search tool to look up each of the "
                    "following queries and gather key facts.\n\n"
                    "Queries from planning step:\n{step_0_output}\n\n"
                    "Original topic: {input}\n\n"
                    "Search each query and collect the most relevant information."
                ),
                use_tools=True,
                max_tokens=4096,
            ),
            WorkflowStep(
                name="Synthesise report",
                prompt_template=(
                    "You are a professional writer. Using the gathered research below, write a "
                    "comprehensive, well-structured report on the topic.\n\n"
                    "Topic: {input}\n\n"
                    "Research gathered:\n{step_1_output}\n\n"
                    "Format: use headings (##), bullet points, and a short summary section. "
                    "Cite sources where possible."
                ),
                use_tools=False,
                max_tokens=4096,
            ),
        ],
    ),
    Workflow(
        id="code_review",
        name="Code Review",
        description="Analyse code for bugs, security issues, performance problems, and style improvements.",
        icon="🔍",
        steps=[
            WorkflowStep(
                name="Identify issues",
                prompt_template=(
                    "You are a senior software engineer conducting a code review.\n\n"
                    "Analyse the following code and list ALL issues you find:\n"
                    "- Bugs / logic errors\n"
                    "- Security vulnerabilities (OWASP top 10, injection, auth issues)\n"
                    "- Performance problems\n"
                    "- Naming and style issues\n\n"
                    "Code:\n```\n{input}\n```\n\n"
                    "Be thorough. Number each issue."
                ),
                use_tools=False,
                max_tokens=2048,
            ),
            WorkflowStep(
                name="Provide fixes and recommendations",
                prompt_template=(
                    "You are a senior software engineer. Given the issues identified below, "
                    "provide concrete fixes and an improved version of the code.\n\n"
                    "Original code:\n```\n{input}\n```\n\n"
                    "Issues found:\n{step_0_output}\n\n"
                    "Provide:\n1. Fixed code snippet(s)\n2. Explanation of each change\n"
                    "3. Overall quality score (1-10) with justification"
                ),
                use_tools=False,
                max_tokens=4096,
            ),
        ],
    ),
    Workflow(
        id="data_analysis",
        name="Data Analysis",
        description="Analyse data or a data description, suggest insights, visualisations, and next steps.",
        icon="📊",
        steps=[
            WorkflowStep(
                name="Understand the data",
                prompt_template=(
                    "You are a data scientist. Examine the following data or data description "
                    "and provide an initial assessment:\n\n"
                    "{input}\n\n"
                    "Cover:\n"
                    "- Data type / structure\n"
                    "- Apparent quality issues (nulls, outliers, encoding)\n"
                    "- Key variables and their types\n"
                    "- Preliminary statistical observations"
                ),
                use_tools=False,
                max_tokens=1024,
            ),
            WorkflowStep(
                name="Generate insights and recommendations",
                prompt_template=(
                    "You are a data scientist. Based on the assessment below, provide:\n"
                    "1. Key insights and patterns in the data\n"
                    "2. Recommended visualisations (chart type + variables)\n"
                    "3. Suggested analyses (correlations, segmentation, trends)\n"
                    "4. Actionable next steps\n\n"
                    "Data: {input}\n\n"
                    "Assessment:\n{step_0_output}"
                ),
                use_tools=False,
                max_tokens=2048,
            ),
        ],
    ),
    Workflow(
        id="document_summary",
        name="Document Summary",
        description="Extract key points, decisions, and action items from a long document.",
        icon="📄",
        steps=[
            WorkflowStep(
                name="Extract key points",
                prompt_template=(
                    "You are an expert at distilling documents. Read the document below and "
                    "extract the most important points, facts, and claims. "
                    "Group them by theme.\n\n"
                    "Document:\n{input}"
                ),
                use_tools=False,
                max_tokens=2048,
            ),
            WorkflowStep(
                name="Produce executive summary",
                prompt_template=(
                    "You are a business analyst. Using the extracted key points, produce:\n"
                    "1. **Executive Summary** (3-5 sentences)\n"
                    "2. **Key Decisions / Findings** (bullet list)\n"
                    "3. **Action Items** (if any, with owners if mentioned)\n"
                    "4. **Open Questions** (things that need follow-up)\n\n"
                    "Key points:\n{step_0_output}\n\n"
                    "Original document length: ~{input_word_count} words"
                ),
                use_tools=False,
                max_tokens=1024,
            ),
        ],
    ),
    Workflow(
        id="brainstorm",
        name="Brainstorm",
        description="Generate diverse ideas on a topic, then evaluate and rank the best ones.",
        icon="💡",
        steps=[
            WorkflowStep(
                name="Generate ideas",
                prompt_template=(
                    "You are a creative strategist. Generate 10 diverse, creative ideas for "
                    "the following topic. Avoid obvious or clichéd suggestions.\n\n"
                    "Topic: {input}\n\n"
                    "For each idea: give it a catchy title and 2-3 sentence description."
                ),
                use_tools=False,
                max_tokens=2048,
            ),
            WorkflowStep(
                name="Evaluate and rank ideas",
                prompt_template=(
                    "You are a critical evaluator. Rank the following ideas for: {input}\n\n"
                    "Ideas:\n{step_0_output}\n\n"
                    "Rank by: feasibility × impact. For each idea provide:\n"
                    "- Rank\n- Feasibility score (1-5)\n- Impact score (1-5)\n"
                    "- Key advantage\n- Key risk\n\n"
                    "End with a recommended top 3 and why."
                ),
                use_tools=False,
                max_tokens=2048,
            ),
        ],
    ),
]

_WORKFLOW_MAP: dict[str, Workflow] = {w.id: w for w in _BUILT_IN_WORKFLOWS}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fill_template(template: str, context: dict[str, str]) -> str:
    """Safe template substitution — missing keys are left as-is."""
    result = template
    for key, value in context.items():
        result = result.replace(f"{{{key}}}", value)
    return result


async def _run_step(
    step: WorkflowStep,
    prompt: str,
    model: str,
) -> AsyncGenerator[dict, None]:
    """
    Execute one workflow step. Streams token events and returns the full text.
    Uses the tool loop when step.use_tools is True.
    """
    from app.ai.providers.base import ChatMessage
    from app.ai.providers.router import get_provider_for_model
    from app.ai.tools import tool_executor, tool_registry

    provider, resolved_model = get_provider_for_model(model)
    messages = [ChatMessage(role="user", content=prompt)]
    full_content = ""

    if step.use_tools and settings.TOOLS_ENABLED:
        tool_defs = tool_registry.get_tool_definitions()
        for _ in range(settings.TOOLS_MAX_ROUNDS):
            completion = await provider.chat_completion(
                messages=messages,
                model=resolved_model,
                max_tokens=step.max_tokens,
                tools=tool_defs,
            )
            if completion.finish_reason == "tool_calls" and completion.tool_calls:
                messages.append(
                    ChatMessage(role="assistant", content="", tool_calls=completion.tool_calls)
                )
                for tc in completion.tool_calls:
                    yield {"type": "tool_use", "tool_name": tc["name"]}
                    result = await tool_executor.execute_from_call(tc)
                    yield {"type": "tool_result", "tool_name": tc["name"], "is_error": result.is_error}
                    messages.append(
                        ChatMessage(
                            role="tool",
                            content=result.content,
                            name=tc["name"],
                            tool_call_id=tc["id"],
                        )
                    )
                continue
            full_content = completion.content
            break
    else:
        async for token in provider.stream_completion(
            messages=messages,
            model=resolved_model,
            max_tokens=step.max_tokens,
        ):
            full_content += token
            yield {"type": "token", "content": token}

    if step.use_tools:
        # Emit accumulated content as tokens for tool path
        _CHUNK = 6
        for i in range(0, len(full_content), _CHUNK):
            yield {"type": "token", "content": full_content[i : i + _CHUNK]}
            await asyncio.sleep(0.005)

    yield {"type": "__step_content__", "content": full_content}


async def _execute_workflow(
    workflow: Workflow,
    user_input: str,
    model: str,
    run_id: uuid.UUID,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    Full workflow execution generator. Yields SSE-formatted strings.
    Persists step results to DB as each step completes.
    """

    def _sse(data: dict) -> str:
        return f"data: {_json.dumps(data)}\n\n"

    step_outputs: list[str] = []
    step_results: list[dict[str, Any]] = []
    total_tokens = 0
    word_count = len(user_input.split())

    try:
        for i, step in enumerate(workflow.steps):
            yield _sse({"type": "step_start", "step": i, "name": step.name, "total_steps": len(workflow.steps)})

            context: dict[str, str] = {
                "input": user_input,
                "input_word_count": str(word_count),
            }
            for j, out in enumerate(step_outputs):
                context[f"step_{j}_output"] = out

            prompt = _fill_template(step.prompt_template, context)
            step_content = ""
            step_tokens = 0

            async for event in _run_step(step, prompt, model):
                if event["type"] == "__step_content__":
                    step_content = event["content"]
                    step_tokens = len(step_content.split()) * 4 // 3
                elif event["type"] in ("token", "tool_use", "tool_result"):
                    yield _sse(event)

            step_outputs.append(step_content)
            total_tokens += step_tokens
            step_results.append({
                "step": i,
                "name": step.name,
                "content": step_content,
                "tokens": step_tokens,
            })

            # Persist step result to DB after each step completes
            await db.execute(
                update(WorkflowRun)
                .where(WorkflowRun.id == run_id)
                .values(step_results=step_results, total_tokens=total_tokens)
            )
            await db.commit()

            yield _sse({"type": "step_done", "step": i, "name": step.name, "tokens": step_tokens})

        # Mark run as completed
        await db.execute(
            update(WorkflowRun)
            .where(WorkflowRun.id == run_id)
            .values(
                status="completed",
                completed_at=datetime.now(timezone.utc),
                total_tokens=total_tokens,
                step_results=step_results,
            )
        )
        await db.commit()

        yield _sse({
            "type": "done",
            "run_id": str(run_id),
            "steps_completed": len(workflow.steps),
            "total_tokens": total_tokens,
        })

    except Exception as exc:
        error_msg = str(exc)
        # Mark run as failed
        try:
            await db.execute(
                update(WorkflowRun)
                .where(WorkflowRun.id == run_id)
                .values(
                    status="failed",
                    completed_at=datetime.now(timezone.utc),
                    step_results=step_results,
                    total_tokens=total_tokens,
                    error=error_msg,
                )
            )
            await db.commit()
        except Exception:
            pass  # Best-effort — don't mask the original error

        yield _sse({"type": "error", "run_id": str(run_id), "message": error_msg})


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/workflows")
async def list_workflows(
    current_user: User = Depends(get_current_user),
) -> dict:
    """List all available agent workflows plus available models for the selector."""
    from app.ai.providers.router import MODEL_REGISTRY

    available_models = []
    for m in MODEL_REGISTRY:
        if m.tier == "embedding":
            continue
        if m.provider == "openai" and not settings.has_openai:
            continue
        if m.provider == "anthropic" and not settings.has_anthropic:
            continue
        if m.provider == "ollama" and not settings.has_ollama:
            continue
        if m.provider == "openrouter" and not settings.has_openrouter:
            continue
        if m.provider == "groq" and not settings.has_groq:
            continue
        if m.provider == "gemini" and not settings.has_gemini:
            continue
        available_models.append({"id": m.id, "name": m.name, "provider": m.provider, "is_free": m.is_free})

    if settings.has_ollama:
        default_model = settings.OLLAMA_DEFAULT_MODEL
    elif available_models:
        default_model = available_models[0]["id"]
    else:
        default_model = ""

    return {
        "workflows": [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description,
                "icon": w.icon,
                "steps": len(w.steps),
                "step_names": [s.name for s in w.steps],
            }
            for w in _BUILT_IN_WORKFLOWS
        ],
        "models": available_models,
        "default_model": default_model,
    }


@router.post("/run")
async def run_workflow(
    request: RunWorkflowRequest,
    current_user: User = Depends(get_current_user),
    _rl: None = Depends(require_chat_rate_limit),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Execute an agent workflow and stream progress via SSE.

    Creates a WorkflowRun record before streaming so the run_id is
    immediately available. Step results are persisted after each step.
    The run status is updated to completed/failed at the end.
    """
    workflow = _WORKFLOW_MAP.get(request.workflow_id)
    if not workflow:
        raise NotFoundError(f"Workflow '{request.workflow_id}' not found")

    from app.ai.providers.router import TaskType, get_provider_for_task

    if request.model:
        model = request.model
    elif settings.has_ollama:
        model = settings.OLLAMA_DEFAULT_MODEL
    else:
        _, model = get_provider_for_task(TaskType.CHAT)

    # Create the run record before streaming so the client gets the run_id
    run = WorkflowRun(
        user_id=current_user.id,
        workflow_id=workflow.id,
        workflow_name=workflow.name,
        workflow_icon=workflow.icon,
        input=request.input,
        model=model,
        status="running",
        step_results=[],
        total_tokens=0,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    run_id = run.id

    async def _stream() -> AsyncGenerator[str, None]:
        # Emit run_created so the client knows the run_id immediately
        yield f"data: {_json.dumps({'type': 'run_created', 'run_id': str(run_id)})}\n\n"
        async for chunk in _execute_workflow(workflow, request.input, model, run_id, db):
            yield chunk

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/runs")
async def list_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    workflow_id: str | None = Query(default=None, description="Filter by workflow ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Paginated list of past workflow runs for the current user.
    Returns metadata only (no step content) for fast loading.
    """
    q = (
        select(WorkflowRun)
        .where(WorkflowRun.user_id == current_user.id)
        .order_by(WorkflowRun.created_at.desc())
    )
    if workflow_id:
        q = q.where(WorkflowRun.workflow_id == workflow_id)

    # Total count
    count_result = await db.execute(
        select(func.count()).select_from(q.subquery())
    )
    total = count_result.scalar_one()

    # Page
    offset = (page - 1) * page_size
    result = await db.execute(q.offset(offset).limit(page_size))
    runs = result.scalars().all()

    return {
        "runs": [
            {
                "id": str(r.id),
                "workflow_id": r.workflow_id,
                "workflow_name": r.workflow_name,
                "workflow_icon": r.workflow_icon,
                "input_preview": r.input[:200] + ("…" if len(r.input) > 200 else ""),
                "model": r.model,
                "status": r.status,
                "total_tokens": r.total_tokens,
                "steps_completed": len(r.step_results),
                "created_at": r.created_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "error": r.error,
            }
            for r in runs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/runs/{run_id}")
async def get_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Full run detail including all step content."""
    result = await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.user_id == current_user.id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise NotFoundError(f"Run {run_id} not found")

    return {
        "id": str(run.id),
        "workflow_id": run.workflow_id,
        "workflow_name": run.workflow_name,
        "workflow_icon": run.workflow_icon,
        "input": run.input,
        "model": run.model,
        "status": run.status,
        "step_results": run.step_results,
        "total_tokens": run.total_tokens,
        "steps_completed": len(run.step_results),
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "error": run.error,
    }


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a workflow run record."""
    result = await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.user_id == current_user.id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise NotFoundError(f"Run {run_id} not found")

    await db.execute(
        delete(WorkflowRun).where(WorkflowRun.id == run_id)
    )
    await db.commit()
