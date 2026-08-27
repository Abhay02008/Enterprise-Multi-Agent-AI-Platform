"""FastMCP server for HR and business document retrieval."""

from mcp.server.fastmcp import FastMCP

from backend.config import DATA_DIR
from backend.rag.retriever import SimpleRetriever


mcp = FastMCP(
    "Enterprise HR and Business Tools",
    host="127.0.0.1",
    port=8111,
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
)

hr_retriever = SimpleRetriever([DATA_DIR / "hr"])
business_retriever = SimpleRetriever([DATA_DIR / "business"])


def search_hr_policy_data(query: str) -> dict:
    """Retrieve HR policy chunks relevant to a natural-language question."""
    matches = hr_retriever.search(query)
    return {
        "query": query,
        "matches": matches,
        "message": None if matches else "No relevant HR policy document was found.",
    }


def search_business_information_data(query: str) -> dict:
    """Retrieve company and business information relevant to a question."""
    matches = business_retriever.search(query)
    return {
        "query": query,
        "matches": matches,
        "message": (
            None if matches else "No relevant business document was found."
        ),
    }


@mcp.tool()
def search_hr_policy(query: str) -> dict:
    """Search leave, workplace, travel, and expense policies."""
    return search_hr_policy_data(query)


@mcp.tool()
def search_business_information(query: str) -> dict:
    """Search company, department, office, and business-unit information."""
    return search_business_information_data(query)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
