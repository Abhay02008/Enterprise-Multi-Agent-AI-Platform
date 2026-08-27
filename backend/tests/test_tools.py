from backend.agents.hr_business.mcp_agent import HRBusinessMCPAgent
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


def test_retrieved_chunks_separate_the_document_title():
    match = search_hr_policy_data("What is the work from home policy?")[
        "matches"
    ][0]
    assert match["title"] == "Work From Home Policy"
    assert not match["text"].startswith("#")
    assert match["text"].startswith("Employees in eligible roles")


def test_retrieval_answer_reads_as_a_titled_answer():
    """Without an LLM the heading must not run into the first sentence."""
    match = search_hr_policy_data("What is the work from home policy?")[
        "matches"
    ][0]
    answer = HRBusinessMCPAgent._format_retrieved(match)
    assert answer.startswith(
        "Work From Home Policy: Employees in eligible roles"
    )


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


def test_offline_product_lookup_uses_product_name():
    agent = ProductOrderMCPAgent()
    assert agent._fallback_tool_choice(
        "What is the price of the ergonomic keyboard?"
    ) == (
        "search_products",
        {"product_id": None, "name": "keyboard", "category": None},
    )


def test_product_name_search_reaches_the_catalog():
    result = search_products_data(name="keyboard")
    assert [row["product_id"] for row in result["products"]] == ["P1003"]


def test_fallback_answers_never_contain_raw_json():
    """The chat UI renders plain text, so tool rows must be prose."""
    agent = ProductOrderMCPAgent()
    products = agent._format_fallback(
        "search_products", search_products_data(category="Electronics")
    )
    orders = agent._format_fallback(
        "search_orders", search_orders_data(status="Pending")
    )
    for answer in (products, orders):
        assert "{" not in answer and "[" not in answer

    assert "2 matching products:" in products
    assert "$1,299.00" in products
    assert "Order ORD1001" in orders


def test_multi_row_inventory_is_reported_per_warehouse():
    """A total across products must not be attributed to a single product."""
    agent = ProductOrderMCPAgent()
    answer = agent._format_fallback("check_inventory", check_inventory_data())
    assert "368 units" in answer
    assert "Northstar Pro Laptop (P1001): 50 units at Austin" in answer
    assert "Warehouse Scanner (P2001): 18 units at Singapore" in answer


def test_single_row_inventory_stays_a_sentence():
    agent = ProductOrderMCPAgent()
    answer = agent._format_fallback(
        "check_inventory", check_inventory_data(product_name="laptop")
    )
    assert answer == "Northstar Pro Laptop has 50 units in stock at Austin."
