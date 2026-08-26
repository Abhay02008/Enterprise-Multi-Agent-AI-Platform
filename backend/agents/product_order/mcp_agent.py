"""Agno agent connected only to MCP-hosted product and order tools."""

import json
import os
import re
from typing import Any

from agno.agent import Agent, RunOutput
from agno.models.google import Gemini
from agno.tools.mcp import MCPTools

from backend.config import GEMINI_MODEL, PRODUCT_MCP_URL


class ProductOrderMCPAgent:
    """Connect MCP tools, let Agno choose a tool, and normalize the answer."""

    def __init__(self, mcp_url: str = PRODUCT_MCP_URL):
        # Agno 3 replaced MultiMCPTools with one MCPTools object per server.
        self.mcp_tools = MCPTools(url=mcp_url, transport="streamable-http")
        self.agent: Agent | None = None

    async def connect(self) -> None:
        await self.mcp_tools.connect()
        if self.mcp_tools.session is None:
            raise ConnectionError(
                f"Product and Order MCP server is unavailable at {self.mcp_tools.url}"
            )

        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            self.agent = Agent(
                name="Enterprise Product and Order Agent",
                model=Gemini(id=GEMINI_MODEL, api_key=api_key, temperature=0),
                tools=[self.mcp_tools],
                instructions=[
                    "Use the MCP tools for every product, inventory, or order fact.",
                    "Choose exactly the tool that matches the request.",
                    "Never invent product, stock, or order data.",
                    "Give a concise business answer and preserve IDs and quantities.",
                ],
                tool_call_limit=3,
                markdown=False,
            )

    async def invoke(self, query: str, context_id: str) -> dict[str, Any]:
        if self.agent:
            try:
                response: RunOutput = await self.agent.arun(
                    query, session_id=context_id
                )
                return {
                    "is_task_complete": True,
                    "content": str(response.content),
                }
            except Exception:
                # Keep the local demo useful for denied, invalid, or rate-limited keys.
                pass

        # A deterministic local fallback keeps the demo usable without an API key.
        # Production execution above uses Agno's LLM-based tool selection.
        tool_name, arguments = self._fallback_tool_choice(query)
        result = await self.mcp_tools.session.call_tool(tool_name, arguments)
        data = json.loads(result.content[0].text)
        return {
            "is_task_complete": True,
            "content": self._format_fallback(tool_name, data),
        }

    @staticmethod
    def _fallback_tool_choice(query: str) -> tuple[str, dict]:
        lower = query.lower()
        product_id = re.search(r"\bP\d{4}\b", query, re.IGNORECASE)
        order_id = re.search(r"\bORD\d{4}\b", query, re.IGNORECASE)

        if "order" in lower and order_id and (
            "status" in lower or "where" in lower
        ):
            return "get_order_status", {"order_id": order_id.group().upper()}
        if "order" in lower:
            status = next(
                (value for value in ["pending", "shipped", "delivered"] if value in lower),
                None,
            )
            return "search_orders", {
                "status": status,
                "product_id": product_id.group().upper() if product_id else None,
            }
        if any(word in lower for word in ["stock", "inventory", "available"]):
            name = next(
                (
                    value
                    for value in ["laptop", "monitor", "keyboard", "scanner"]
                    if value in lower
                ),
                None,
            )
            return "check_inventory", {
                "product_id": product_id.group().upper() if product_id else None,
                "product_name": name,
            }
        category = next(
            (value for value in ["electronics", "accessories", "industrial"] if value in lower),
            None,
        )
        return "search_products", {
            "product_id": product_id.group().upper() if product_id else None,
            "category": category,
        }

    @staticmethod
    def _format_fallback(tool_name: str, data: dict) -> str:
        if data.get("message"):
            return data["message"]
        if tool_name == "check_inventory":
            rows = data["inventory"]
            return (
                f"{rows[0]['product_name']} has {data['total_quantity']} units "
                f"in stock at {rows[0]['warehouse']}."
            )
        if tool_name == "get_order_status":
            order = data["order"]
            return (
                f"Order {order['order_id']} is {order['status']}. Expected "
                f"delivery: {order['expected_delivery']}."
            )
        rows = data["orders"] if tool_name == "search_orders" else data["products"]
        return json.dumps(rows, indent=2)

    async def close(self) -> None:
        await self.mcp_tools.close()
