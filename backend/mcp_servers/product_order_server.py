"""FastMCP server owning product, inventory, and order data access."""

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from backend.config import DATA_DIR


mcp = FastMCP(
    "Enterprise Product and Order Tools",
    host="127.0.0.1",
    port=8112,
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
)


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def search_products_data(
    product_id: str | None = None,
    name: str | None = None,
    category: str | None = None,
) -> dict:
    """Filter the product catalog by identifier, name, or category."""
    products = _load(DATA_DIR / "products" / "products.json")
    if product_id:
        products = [
            row for row in products if row["product_id"].lower() == product_id.lower()
        ]
    if name:
        products = [
            row for row in products if name.lower() in row["name"].lower()
        ]
    if category:
        products = [
            row
            for row in products
            if row["category"].lower() == category.lower()
        ]
    return {
        "products": products,
        "message": None if products else "No matching product was found.",
    }


def check_inventory_data(
    product_id: str | None = None, product_name: str | None = None
) -> dict:
    """Return stock for a product ID or product name."""
    products = _load(DATA_DIR / "products" / "products.json")
    inventory = _load(DATA_DIR / "inventory" / "inventory.json")

    matching_ids = {
        row["product_id"]
        for row in products
        if (not product_id or row["product_id"].lower() == product_id.lower())
        and (not product_name or product_name.lower() in row["name"].lower())
    }
    stock = [
        {
            **row,
            "product_name": next(
                product["name"]
                for product in products
                if product["product_id"] == row["product_id"]
            ),
        }
        for row in inventory
        if row["product_id"] in matching_ids
    ]
    return {
        "inventory": stock,
        "total_quantity": sum(row["quantity"] for row in stock),
        "message": None if stock else "Product not found in inventory.",
    }


def get_order_status_data(order_id: str) -> dict:
    """Return status and delivery information for one order."""
    orders = _load(DATA_DIR / "orders" / "orders.json")
    order = next(
        (row for row in orders if row["order_id"].lower() == order_id.lower()),
        None,
    )
    return {
        "order": order,
        "message": None if order else f"Order {order_id} was not found.",
    }


def search_orders_data(
    status: str | None = None,
    product_id: str | None = None,
    customer: str | None = None,
) -> dict:
    """Filter orders by status, product, or customer."""
    orders = _load(DATA_DIR / "orders" / "orders.json")
    if status:
        orders = [
            row for row in orders if row["status"].lower() == status.lower()
        ]
    if product_id:
        orders = [
            row
            for row in orders
            if row["product_id"].lower() == product_id.lower()
        ]
    if customer:
        orders = [
            row for row in orders if customer.lower() in row["customer"].lower()
        ]
    return {
        "orders": orders,
        "message": None if orders else "No matching orders were found.",
    }


@mcp.tool()
def search_products(
    product_id: str | None = None,
    name: str | None = None,
    category: str | None = None,
) -> dict:
    """Search product details by ID, partial name, or category."""
    return search_products_data(product_id, name, category)


@mcp.tool()
def check_inventory(
    product_id: str | None = None, product_name: str | None = None
) -> dict:
    """Check available inventory by product ID or product name."""
    return check_inventory_data(product_id, product_name)


@mcp.tool()
def get_order_status(order_id: str) -> dict:
    """Get the current status of an order by its order ID."""
    return get_order_status_data(order_id)


@mcp.tool()
def search_orders(
    status: str | None = None,
    product_id: str | None = None,
    customer: str | None = None,
) -> dict:
    """Search orders by status, product ID, or customer."""
    return search_orders_data(status, product_id, customer)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
