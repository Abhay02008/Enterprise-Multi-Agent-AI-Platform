"""Official A2A SDK client used by the LangGraph Host."""

import uuid

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    Message,
    Part,
    Role,
    SendMessageRequest,
)


class RemoteAgentClient:
    async def discover(self, base_urls: list[str]) -> list[AgentCard]:
        """Fetch Agent Cards; the Host learns skills, not implementations."""
        cards: list[AgentCard] = []
        async with httpx.AsyncClient(timeout=10) as http:
            for base_url in base_urls:
                resolver = A2ACardResolver(http, base_url)
                cards.append(await resolver.get_agent_card())
        return cards

    async def send(
        self, card: AgentCard, text: str, context_id: str
    ) -> str:
        """Send one A2A task and return its final text artifact."""
        http = httpx.AsyncClient(timeout=60)
        client = ClientFactory(
            ClientConfig(streaming=False, httpx_client=http)
        ).create(card)
        request = SendMessageRequest(
            message=Message(
                message_id=str(uuid.uuid4()),
                context_id=context_id,
                role=Role.ROLE_USER,
                parts=[Part(text=text)],
            )
        )
        answer = ""
        try:
            async for event in client.send_message(request):
                if event.HasField("message"):
                    answer = self._message_text(event.message)
                if event.HasField("task"):
                    for artifact in event.task.artifacts:
                        answer = self._parts_text(artifact.parts) or answer
                if event.HasField("artifact_update"):
                    answer = (
                        self._parts_text(event.artifact_update.artifact.parts)
                        or answer
                    )
        finally:
            await client.close()
            if not http.is_closed:
                await http.aclose()

        if not answer:
            raise RuntimeError(f"{card.name} returned no text artifact.")
        return answer

    @staticmethod
    def _parts_text(parts) -> str:
        return "\n".join(part.text for part in parts if part.text)

    def _message_text(self, message: Message) -> str:
        return self._parts_text(message.parts)
