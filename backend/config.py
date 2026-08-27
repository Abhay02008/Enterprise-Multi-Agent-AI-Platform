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

# The Groq SDK defaults to a 60 s read timeout with two retries, which can
# stall an agent for minutes when the API is unreachable. The Host allows a
# task 60 s in total, so each Groq attempt must fail well inside that budget
# for the deterministic fallback to still answer in time.
GROQ_TIMEOUT_SECONDS = float(os.getenv("GROQ_TIMEOUT_SECONDS", "15"))
GROQ_MAX_RETRIES = int(os.getenv("GROQ_MAX_RETRIES", "1"))

DATA_DIR = Path(__file__).resolve().parent / "data"
