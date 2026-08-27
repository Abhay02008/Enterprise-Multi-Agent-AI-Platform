"""Small HR/business agent that retrieves documents through MCP."""

import json
import os
from typing import Any

from agno.tools.mcp import MCPTools
from google import genai

from backend.config import GEMINI_MODEL, HR_MCP_URL


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
        elif os.getenv("GEMINI_API_KEY"):
            try:
                answer = await self._answer_with_gemini(
                    query, retrieval["matches"]
                )
            except Exception:
                # Invalid, denied, or rate-limited credentials must not break RAG.
                answer = retrieval["matches"][0]["text"].replace("#", "").strip()
        else:
            answer = retrieval["matches"][0]["text"].replace("#", "").strip()

        return {"is_task_complete": True, "content": answer}

    @staticmethod
    async def _answer_with_gemini(query: str, matches: list[dict]) -> str:
        context = "\n\n".join(
            f"Source: {match['source']}\n{match['text']}" for match in matches
        )
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        try:
            response = await client.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=(
                    "Answer the employee's question using only the supplied "
                    "enterprise context. Be concise and mention the source file.\n\n"
                    f"Question: {query}\n\nContext:\n{context}"
                ),
            )
            return response.text or "The retrieved policy did not contain an answer."
        finally:
            await client.aio.aclose()

    async def close(self) -> None:
        await self.mcp_tools.close()
