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
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# The default model reasons before answering, and reasoning shares this budget.
# Too small a budget returns an empty message with finish_reason "length".
GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "1024"))

DATA_DIR = Path(__file__).resolve().parent / "data"
