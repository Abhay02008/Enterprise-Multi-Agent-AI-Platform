import httpx

from backend.agents.hr_business.a2a_server import agent_card as hr_card
from backend.agents.product_order.a2a_server import agent_card as product_card
from backend.api.main import app
from backend.host.host_agent import HostAgent


class FakeA2AClient:
    def __init__(self):
        self.selected = None

    async def discover(self, _urls):
        return [hr_card, product_card]

    async def send(self, card, text, context_id):
        self.selected = card.name
        return f"{card.name} handled {text} in {context_id}"


async def test_host_routes_hr_from_discovered_skills():
    client = FakeA2AClient()
    host = HostAgent(client=client)
    await host.chat("What is the maternity leave policy?", "session-1")
    assert client.selected == "Enterprise HR and Business Agent"


async def test_host_routes_inventory_from_discovered_skills():
    client = FakeA2AClient()
    host = HostAgent(client=client)
    await host.chat("How many laptops are currently in stock?", "session-2")
    assert client.selected == "Enterprise Product and Order Agent"


async def test_host_routes_pricing_from_advertised_examples():
    client = FakeA2AClient()
    host = HostAgent(client=client)
    await host.chat("What is the price of the ergonomic keyboard?", "session-4")
    assert client.selected == "Enterprise Product and Order Agent"


async def test_host_handles_unknown_request():
    host = HostAgent(client=FakeA2AClient())
    response = await host.chat("Tell me a joke", "session-3")
    assert "HR policies" in response


class FakeHost:
    async def chat(self, message, session_id):
        return f"Response for {message}"


async def test_chat_endpoint():
    original = app.state.host_agent
    app.state.host_agent = FakeHost()
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/chat", json={"message": "Show product P1001."}
            )
        assert response.status_code == 200
        assert response.json()["response"] == "Response for Show product P1001."
        assert response.json()["session_id"]
    finally:
        app.state.host_agent = original
