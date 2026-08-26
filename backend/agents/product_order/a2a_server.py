"""A2A server and Agent Card for the Agno Product and Order agent."""

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

from backend.agents.product_order.agent_executor import (
    ProductOrderAgentExecutor,
)
from backend.config import PRODUCT_AGENT_URL


agent_card = AgentCard(
    name="Enterprise Product and Order Agent",
    description="Uses Agno and MCP tools for products, inventory, and orders.",
    version="1.0.0",
    supported_interfaces=[
        AgentInterface(
            url=f"{PRODUCT_AGENT_URL}/a2a",
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
            id="product_search",
            name="Product Search",
            description="Find products by ID, name, or category.",
            tags=["product", "catalog", "category"],
            examples=["Show me information about product P1001."],
        ),
        AgentSkill(
            id="inventory_lookup",
            name="Inventory Lookup",
            description="Check product stock and warehouse quantities.",
            tags=["inventory", "stock", "availability"],
            examples=["How many laptops are currently available?"],
        ),
        AgentSkill(
            id="order_search",
            name="Order Search",
            description="Find orders by status, product, or customer.",
            tags=["order", "pending", "customer"],
            examples=["Show me pending orders."],
        ),
        AgentSkill(
            id="order_status",
            name="Order Status",
            description="Get current status and delivery date for an order.",
            tags=["order", "status", "delivery"],
            examples=["What is the status of order ORD1001?"],
        ),
    ],
)

request_handler = DefaultRequestHandler(
    agent_executor=ProductOrderAgentExecutor(),
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
