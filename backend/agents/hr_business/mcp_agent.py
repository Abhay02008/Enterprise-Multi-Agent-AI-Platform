"""Small HR/business agent that retrieves documents through MCP."""

import json
import os
from typing import Any

from agno.tools.mcp import MCPTools
from groq import AsyncGroq

from backend.config import (
    GROQ_MAX_RETRIES,
    GROQ_MAX_TOKENS,
    GROQ_MODEL,
    GROQ_TIMEOUT_SECONDS,
    HR_MCP_URL,
)


class HRBusinessMCPAgent:
    def __init__(self, mcp_url: str = HR_MCP_URL):
        self.mcp_tools = MCPTools(url=mcp_url, transport="streamable-http")

    async def connect(self) -> None:
        await self.mcp_tools.connect()
        if self.mcp_tools.session is None:
            raise ConnectionError(
                f"HR and Business MCP server is unavailable at {self.mcp_tools.url}"
            )

    async def invoke(self, query: str, context_id: str) -> dict[str, Any]:
        business_words = ("business unit", "company", "department", "office")
        tool_name = (
            "search_business_information"
            if any(word in query.lower() for word in business_words)
            else "search_hr_policy"
        )
        result = await self.mcp_tools.session.call_tool(
            tool_name, {"query": query}
        )
        retrieval = json.loads(result.content[0].text)
        if retrieval["message"]:
            answer = retrieval["message"]
        elif os.getenv("GROQ_API_KEY"):
            try:
                answer = await self._answer_with_groq(
                    query, retrieval["matches"]
                )
            except Exception:
                # Invalid, denied, or rate-limited credentials must not break RAG.
                answer = self._format_retrieved(retrieval["matches"][0])
        else:
            answer = self._format_retrieved(retrieval["matches"][0])

        return {"is_task_complete": True, "content": answer}

    @staticmethod
    def _format_retrieved(match: dict) -> str:
        """Render one retrieved chunk as a readable answer without an LLM."""
        body = " ".join(str(match["text"]).split())
        title = str(match.get("title") or "").strip()
        return f"{title}: {body}" if title else body

    @staticmethod
    def _completion_request(query: str, matches: list[dict]) -> dict[str, Any]:
        """Build the Groq chat request for a grounded, source-cited answer."""
        context = "\n\n".join(
            f"Source: {match['source']}\n"
            f"Document: {match.get('title') or match['source']}\n"
            f"{match['text']}"
            for match in matches
        )
        return {
            "model": GROQ_MODEL,
            "temperature": 0,
            "max_tokens": GROQ_MAX_TOKENS,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You answer employee questions about enterprise HR and "
                        "business documents. Use only the supplied context, "
                        "never outside knowledge. Be concise and name the "
                        "source file. Reply in plain text: no Markdown, no "
                        "asterisks, and no headings, because the chat UI "
                        "renders your answer verbatim."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Question: {query}\n\nContext:\n{context}",
                },
            ],
        }

    @staticmethod
    def _answer_text(completion: Any) -> str:
        answer = (completion.choices[0].message.content or "").strip()
        if not answer:
            # A reasoning model that exhausts the token budget returns an empty
            # message; let the caller fall back to retrieved text.
            raise ValueError("Groq returned an empty answer.")
        return answer

    @classmethod
    async def _answer_with_groq(cls, query: str, matches: list[dict]) -> str:
        client = AsyncGroq(
            api_key=os.environ["GROQ_API_KEY"],
            timeout=GROQ_TIMEOUT_SECONDS,
            max_retries=GROQ_MAX_RETRIES,
        )
        try:
            completion = await client.chat.completions.create(
                **cls._completion_request(query, matches)
            )
            return cls._answer_text(completion)
        finally:
            await client.close()

    async def close(self) -> None:
        await self.mcp_tools.close()
