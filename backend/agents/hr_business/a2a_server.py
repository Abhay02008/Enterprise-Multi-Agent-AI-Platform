"""A2A server and discoverable Agent Card for HR and business retrieval."""

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)
from fastapi import FastAPI

from backend.agents.hr_business.agent_executor import (
    HRBusinessAgentExecutor,
)
from backend.config import HR_AGENT_URL


agent_card = AgentCard(
    name="Enterprise HR and Business Agent",
    description="Retrieves HR policies and enterprise business information.",
    version="1.0.0",
    supported_interfaces=[
        AgentInterface(
            url=f"{HR_AGENT_URL}/a2a",
            protocol_binding="JSONRPC",
            protocol_version="1.0",
        )
    ],
    capabilities=AgentCapabilities(
        streaming=False, push_notifications=False
    ),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    skills=[
        AgentSkill(
            id="hr_policy_search",
            name="HR Policy Search",
            description="Search leave, workplace, travel, and expense policies.",
            tags=["hr", "policy", "leave", "expenses"],
            examples=["What is the work from home policy?"],
        ),
        AgentSkill(
            id="business_information_search",
            name="Business Information Search",
            description="Search company, office, department, and business-unit facts.",
            tags=["business", "company", "department", "office"],
            examples=["What are the company's business units?"],
        ),
    ],
)

request_handler = DefaultRequestHandler(
    agent_executor=HRBusinessAgentExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=agent_card,
)

app = FastAPI(title=agent_card.name)
add_a2a_routes_to_fastapi(
    app,
    agent_card_routes=create_agent_card_routes(agent_card),
    jsonrpc_routes=create_jsonrpc_routes(request_handler, rpc_url="/a2a"),
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "agent": agent_card.name}
