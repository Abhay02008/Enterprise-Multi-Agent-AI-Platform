"""Shared local service configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

HR_MCP_URL = os.getenv("HR_MCP_URL", "http://127.0.0.1:8111/mcp")
PRODUCT_MCP_URL = os.getenv(
    "PRODUCT_MCP_URL", "http://127.0.0.1:8112/mcp"
)
HR_AGENT_URL = os.getenv("HR_AGENT_URL", "http://127.0.0.1:8211")
PRODUCT_AGENT_URL = os.getenv(
    "PRODUCT_AGENT_URL", "http://127.0.0.1:8212"
)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DATA_DIR = Path(__file__).resolve().parent / "data"
