"""Agno agent connected only to MCP-hosted product and order tools."""

import json
import os
import re
from collections.abc import Callable
from typing import Any

from agno.agent import Agent, RunOutput
from agno.models.groq import Groq
from agno.run.agent import RunStatus
from agno.tools.mcp import MCPTools

from backend.config import (
    GROQ_MAX_RETRIES,
    GROQ_MAX_TOKENS,
    GROQ_MODEL,
    GROQ_TIMEOUT_SECONDS,
    PRODUCT_MCP_URL,
)


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

        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            self.agent = Agent(
                name="Enterprise Product and Order Agent",
                model=self._build_model(api_key),
                tools=[self.mcp_tools],
                instructions=[
                    "Use the MCP tools for every product, inventory, or order fact.",
                    "Choose exactly the tool that matches the request.",
                    "Never invent product, stock, or order data.",
                    "Give a concise business answer and preserve IDs and quantities.",
                    "When the request names no specific product, call the tool "
                    "with no filters to report every row instead of asking the "
                    "user to narrow it down.",
                    "List each inventory row with its own warehouse and quantity.",
                    "Write currency with two decimal places, such as $89.00.",
                    "Reply in plain text: no Markdown, no asterisks, and no "
                    "headings, because the chat UI renders your answer verbatim.",
                ],
                tool_call_limit=3,
                markdown=False,
            )

    @staticmethod
    def _build_model(api_key: str) -> Groq:
        """Groq model that Agno uses to pick an MCP tool."""
        return Groq(
            id=GROQ_MODEL,
            api_key=api_key,
            temperature=0,
            max_tokens=GROQ_MAX_TOKENS,
            timeout=int(GROQ_TIMEOUT_SECONDS),
            max_retries=GROQ_MAX_RETRIES,
        )

    async def invoke(self, query: str, context_id: str) -> dict[str, Any]:
        if self.agent:
            try:
                response: RunOutput = await self.agent.arun(
                    query, session_id=context_id
                )
                if response.status == RunStatus.completed:
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

    PRODUCT_NAME_WORDS = ("laptop", "monitor", "keyboard", "scanner")
    CATEGORY_WORDS = ("electronics", "accessories", "industrial")
    ORDER_STATUS_WORDS = ("pending", "shipped", "delivered")

    @classmethod
    def _fallback_tool_choice(cls, query: str) -> tuple[str, dict]:
        lower = query.lower()
        product_id = re.search(r"\bP\d{4}\b", query, re.IGNORECASE)
        order_id = re.search(r"\bORD\d{4}\b", query, re.IGNORECASE)
        name = next(
            (word for word in cls.PRODUCT_NAME_WORDS if word in lower), None
        )

        if "order" in lower and order_id and (
            "status" in lower or "where" in lower
        ):
            return "get_order_status", {"order_id": order_id.group().upper()}
        if "order" in lower:
            status = next(
                (word for word in cls.ORDER_STATUS_WORDS if word in lower),
                None,
            )
            return "search_orders", {
                "status": status,
                "product_id": product_id.group().upper() if product_id else None,
            }
        if any(word in lower for word in ["stock", "inventory", "available"]):
            return "check_inventory", {
                "product_id": product_id.group().upper() if product_id else None,
                "product_name": name,
            }
        category = next(
            (word for word in cls.CATEGORY_WORDS if word in lower), None
        )
        return "search_products", {
            "product_id": product_id.group().upper() if product_id else None,
            "name": name,
            "category": category,
        }

    @classmethod
    def _format_fallback(cls, tool_name: str, data: dict) -> str:
        if data.get("message"):
            return data["message"]
        if tool_name == "check_inventory":
            return cls._format_inventory(data)
        if tool_name == "get_order_status":
            order = data["order"]
            return (
                f"Order {order['order_id']} is {order['status']}. Expected "
                f"delivery: {order['expected_delivery']}."
            )
        if tool_name == "search_orders":
            return cls._format_rows(
                data["orders"], cls._order_line, "matching order"
            )
        return cls._format_rows(
            data["products"], cls._product_line, "matching product"
        )

    @staticmethod
    def _format_inventory(data: dict) -> str:
        rows = data["inventory"]
        if len(rows) == 1:
            row = rows[0]
            return (
                f"{row['product_name']} has {row['quantity']} units in stock "
                f"at {row['warehouse']}."
            )
        lines = "\n".join(
            f"- {row['product_name']} ({row['product_id']}): "
            f"{row['quantity']} units at {row['warehouse']}"
            for row in rows
        )
        return (
            f"{len(rows)} stocked items totalling "
            f"{data['total_quantity']} units:\n{lines}"
        )

    @staticmethod
    def _product_line(row: dict) -> str:
        return (
            f"{row['product_id']} — {row['name']} ({row['category']}), "
            f"${row['price']:,.2f}. {row['description']}"
        )

    @staticmethod
    def _order_line(row: dict) -> str:
        return (
            f"Order {row['order_id']} — {row['quantity']} x "
            f"{row['product_id']} for {row['customer']}, {row['status']}, "
            f"expected {row['expected_delivery']}"
        )

    @staticmethod
    def _format_rows(
        rows: list[dict], line: Callable[[dict], str], label: str
    ) -> str:
        """Render tool rows as prose so the chat UI never shows raw JSON."""
        if len(rows) == 1:
            return line(rows[0])
        listed = "\n".join(f"- {line(row)}" for row in rows)
        return f"{len(rows)} {label}s:\n{listed}"

    async def close(self) -> None:
        await self.mcp_tools.close()
