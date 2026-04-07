"""
Web search tool — DuckDuckGo Instant Answer API (free, no API key required).

DuckDuckGo's Instant Answer API returns curated answers for queries.
It's not a full web search (no crawled results), but gives useful
factual summaries for many questions.

For a real web search integration, replace this with:
- Brave Search API (https://brave.com/search/api/) — paid but good
- Serper API (https://serper.dev/) — Google results, cheap
- Tavily API (https://tavily.com/) — built for AI agents

The interface is stable regardless of backend — swap the execute()
implementation without changing any callers.
"""

from typing import Any

import httpx

from app.ai.tools.base import BaseTool, ToolResult
from app.core.logging import get_logger

logger = get_logger(__name__)

DDGS_URL = "https://api.duckduckgo.com/"
REQUEST_TIMEOUT = 8.0


def _format_ddgs_response(data: dict, query: str) -> str | None:
    """Extract a useful summary from DuckDuckGo Instant Answer response."""
    parts = []

    # Abstract (main answer for entities/topics)
    abstract = data.get("Abstract", "").strip()
    abstract_source = data.get("AbstractSource", "")
    if abstract:
        source_note = f" (via {abstract_source})" if abstract_source else ""
        parts.append(f"{abstract}{source_note}")

    # Answer (direct answers like "2 + 2 = 4" — rare but useful)
    answer = data.get("Answer", "").strip()
    if answer and answer != abstract:
        parts.append(f"Direct answer: {answer}")

    # Definition
    definition = data.get("Definition", "").strip()
    definition_source = data.get("DefinitionSource", "")
    if definition and definition != abstract:
        source_note = f" (via {definition_source})" if definition_source else ""
        parts.append(f"Definition: {definition}{source_note}")

    # Related topics — top 3 only to keep the response concise
    related = data.get("RelatedTopics", [])
    related_texts = []
    for topic in related[:3]:
        if isinstance(topic, dict) and "Text" in topic:
            related_texts.append(f"- {topic['Text']}")
    if related_texts:
        parts.append("Related:\n" + "\n".join(related_texts))

    return "\n\n".join(parts) if parts else None


class WebSearchTool(BaseTool):
    name = "web_search"
    description = (
        "Search the web for information about a topic. Returns factual summaries "
        "and related information. Best for: current events, factual questions, "
        "definitions, and general knowledge queries."
    )
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query. Be specific for better results.",
            }
        },
        "required": ["query"],
    }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        query = args.get("query", "").strip()
        if not query:
            return ToolResult(
                tool_name=self.name,
                content="Error: no search query provided",
                is_error=True,
            )

        logger.info("web_search.query", query=query)

        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(DDGS_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException:
            return ToolResult(
                tool_name=self.name,
                content=f"Search timed out for '{query}'. Please try again.",
                is_error=True,
            )
        except Exception as e:
            logger.error("web_search.error", query=query, error=str(e))
            return ToolResult(
                tool_name=self.name,
                content=f"Search failed for '{query}': {e}",
                is_error=True,
            )

        result = _format_ddgs_response(data, query)
        if not result:
            return ToolResult(
                tool_name=self.name,
                content=(
                    f"No instant answer found for '{query}'. "
                    "The query may be too specific or require a full web search."
                ),
                metadata={"query": query, "no_results": True},
            )

        return ToolResult(
            tool_name=self.name,
            content=f"Search results for '{query}':\n\n{result}",
            metadata={"query": query},
        )
