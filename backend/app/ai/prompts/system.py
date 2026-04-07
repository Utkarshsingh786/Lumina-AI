"""
System prompt templates.

Why centralize prompts:
- Easy to iterate on prompt quality without hunting through code
- Version-controllable and reviewable
- Can be overridden per-conversation or per-user

Design principle: prompts are layered:
  1. BASE_SYSTEM — always included
  2. PERSONA prompts — override based on assistant mode
  3. Memory injection — appended at context-build time
  4. Tool instructions — appended when tools are enabled
  5. RAG context — appended when documents are retrieved
"""

from app.ai.prompts.personas import PERSONA_PROMPTS


BASE_SYSTEM = """\
You are Lumina, an intelligent AI assistant. You are helpful, accurate, and concise.

Core principles:
- Be direct and useful. Don't pad responses with unnecessary filler.
- When you don't know something, say so clearly instead of guessing.
- Format your responses with markdown when it improves readability.
- For code: always specify the language, use proper indentation, add brief comments.
- Respect the user's time — match response length to question complexity.
"""

TITLE_GENERATION_PROMPT = """\
Generate a short, descriptive title (max 6 words) for a chat conversation based on the user's first message.
Return ONLY the title — no quotes, no explanation, no punctuation at the end.
Examples: "Python async debugging help", "Marketing email draft", "Recipe ideas for dinner"
"""

SUMMARIZATION_PROMPT = """\
Summarize the following conversation into a compact paragraph (max 150 words).
Capture: main topics discussed, key decisions made, important information shared, user's goals.
Write in third person. Focus on information useful to continue the conversation later.
"""

MEMORY_EXTRACTION_PROMPT = """\
Extract important facts, preferences, or instructions from this conversation that would be useful to remember for future conversations with this user.

Focus on:
- Personal facts (name, job, location, expertise level)
- Explicit preferences ("I prefer X", "I always use Y")
- Instructions ("always respond in Spanish", "keep responses brief")
- Important context (current project, goals, constraints)

Return as a JSON array of objects with fields: "content" (the fact), "type" (fact|preference|instruction|context), "importance" (1-10).
Return [] if nothing important was found.
Only return the JSON array, no other text.
"""

TOOL_INSTRUCTION = """\
You have access to tools. Use them when they would genuinely help answer the user's question.
- Call tools with accurate, well-formed inputs
- Don't call tools unnecessarily
- If a tool fails, explain this to the user and try to answer from your knowledge
"""

RAG_CONTEXT_PREFIX = """\
The following excerpts are from documents the user has uploaded. Use them to answer the question accurately.
If the answer is in these excerpts, cite the source. If not, say so and answer from general knowledge.

--- DOCUMENT CONTEXT ---
{context}
--- END CONTEXT ---
"""

MEMORY_INJECTION_PREFIX = """\
The following are things I remember about this user from previous conversations:
{memories}

Use this context naturally when relevant, but don't reference it explicitly unless asked.
"""


def build_system_prompt(
    persona: str = "general",
    memories: list[str] | None = None,
    rag_context: str | None = None,
    custom_system_prompt: str | None = None,
    enable_tools: bool = False,
) -> str:
    """
    Assemble the final system prompt by layering components.
    Order matters: base → persona → memory → RAG → tools → custom override.
    """
    parts = []

    # Custom system prompt completely overrides base + persona if provided
    if custom_system_prompt:
        parts.append(custom_system_prompt)
    else:
        parts.append(BASE_SYSTEM)
        persona_prompt = PERSONA_PROMPTS.get(persona, PERSONA_PROMPTS["general"])
        if persona_prompt:
            parts.append(persona_prompt)

    if memories:
        formatted_memories = "\n".join(f"- {m}" for m in memories)
        parts.append(MEMORY_INJECTION_PREFIX.format(memories=formatted_memories))

    if rag_context:
        parts.append(RAG_CONTEXT_PREFIX.format(context=rag_context))

    if enable_tools:
        parts.append(TOOL_INSTRUCTION)

    return "\n\n".join(parts)
