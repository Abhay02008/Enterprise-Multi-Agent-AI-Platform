from backend.agents.product_order.mcp_agent import ProductOrderMCPAgent
from backend.mcp_servers.hr_business_server import (
    search_business_information_data,
    search_hr_policy_data,
)
from backend.mcp_servers.product_order_server import (
    check_inventory_data,
    get_order_status_data,
    search_orders_data,
    search_products_data,
)


def test_hr_policy_retrieval():
    result = search_hr_policy_data("What is the work from home policy?")
    assert result["matches"][0]["source"] == "workplace_policy.md"
    assert "three days per week" in result["matches"][0]["text"]


def test_business_information_retrieval():
    result = search_business_information_data("What are the business units?")
    assert "Enterprise Devices" in result["matches"][0]["text"]


def test_product_search():
    result = search_products_data(product_id="P1001")
    assert result["products"][0]["name"] == "Northstar Pro Laptop"


def test_inventory_lookup():
    result = check_inventory_data(product_name="laptop")
    assert result["total_quantity"] == 50


def test_order_tools():
    assert get_order_status_data("ORD1001")["order"]["status"] == "Pending"
    assert len(search_orders_data(status="Pending")["orders"]) == 1


def test_offline_tool_selection_matches_agno_tools():
    """The no-key fallback follows the same tool contract used by Agno."""
    agent = ProductOrderMCPAgent()
    assert agent._fallback_tool_choice("How many P1001 units are in stock?") == (
        "check_inventory",
        {"product_id": "P1001", "product_name": None},
    )
    assert agent._fallback_tool_choice("Status of order ORD1001?") == (
        "get_order_status",
        {"order_id": "ORD1001"},
    )
