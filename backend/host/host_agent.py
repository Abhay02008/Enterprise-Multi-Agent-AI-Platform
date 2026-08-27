"""LangGraph Host: discover, route, and delegate through A2A."""

import re
from typing import TypedDict

from a2a.types import AgentCard
from langgraph.graph import END, START, StateGraph

from backend.config import HR_AGENT_URL, PRODUCT_AGENT_URL
from backend.host.a2a_client import RemoteAgentClient


class HostState(TypedDict, total=False):
    message: str
    session_id: str
    cards: list[AgentCard]
    selected_card: AgentCard
    response: str


class HostAgent:
    """The Host knows remote Agent Cards, never remote MCP tools."""

    def __init__(
        self,
        remote_urls: list[str] | None = None,
        client: RemoteAgentClient | None = None,
    ):
        self.remote_urls = remote_urls or [HR_AGENT_URL, PRODUCT_AGENT_URL]
        self.client = client or RemoteAgentClient()

        graph = StateGraph(HostState)
        graph.add_node("discover_agents", self._discover_agents)
        graph.add_node("select_agent", self._select_agent)
        graph.add_node("delegate_with_a2a", self._delegate_with_a2a)
        graph.add_edge(START, "discover_agents")
        graph.add_edge("discover_agents", "select_agent")
        graph.add_conditional_edges(
            "select_agent",
            lambda state: "delegate" if state.get("selected_card") else "unknown",
            {"delegate": "delegate_with_a2a", "unknown": END},
        )
        graph.add_edge("delegate_with_a2a", END)
        self.graph = graph.compile()

    async def _discover_agents(self, state: HostState) -> HostState:
        try:
            cards = await self.client.discover(self.remote_urls)
            return {"cards": cards}
        except Exception as exc:
            return {
                "cards": [],
                "response": f"Remote A2A agent discovery failed: {exc}",
            }

    async def _select_agent(self, state: HostState) -> HostState:
        if not state.get("cards"):
            return {}

        query_terms = self._meaningful_terms(state["message"])
        scored_cards = [
            (self._card_score(query_terms, card), card)
            for card in state["cards"]
        ]
        score, selected = max(scored_cards, key=lambda item: item[0])
        if score == 0:
            return {
                "response": (
                    "I can help with HR policies, business information, "
                    "products, inventory, and orders. Please ask about one "
                    "of those areas."
                )
            }
        return {"selected_card": selected}

    async def _delegate_with_a2a(self, state: HostState) -> HostState:
        try:
            response = await self.client.send(
                state["selected_card"],
                state["message"],
                state["session_id"],
            )
            return {"response": response}
        except Exception as exc:
            return {
                "response": (
                    f"{state['selected_card'].name} is currently unavailable: {exc}"
                )
            }

    @staticmethod
    def _meaningful_terms(text: str) -> set[str]:
        ignored = {
            "a",
            "an",
            "are",
            "about",
            "currently",
            "how",
            "is",
            "me",
            "of",
            "please",
            "show",
            "the",
            "what",
        }
        return {
            token
            for token in re.findall(r"[a-z0-9]+", text.lower())
            if token not in ignored
        }

    def _card_score(self, query_terms: set[str], card: AgentCard) -> int:
        advertised = " ".join(
            [
                card.name,
                card.description,
                *(
                    text
                    for skill in card.skills
                    for text in [
                        skill.name,
                        skill.description,
                        *skill.tags,
                        *skill.examples,
                    ]
                ),
            ]
        )
        return len(query_terms & self._meaningful_terms(advertised))

    async def chat(self, message: str, session_id: str) -> str:
        result = await self.graph.ainvoke(
            {"message": message, "session_id": session_id}
        )
        return result["response"]
