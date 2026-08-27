"""Time every layer of the stack to locate a hang or failure.

Run with all services started:  python -m backend.diagnose
Each step is capped, so the script always finishes and prints a verdict.
"""

import asyncio
import os
import time

import httpx

from backend.config import (
    GROQ_MAX_RETRIES,
    GROQ_MAX_TOKENS,
    GROQ_MODEL,
    GROQ_TIMEOUT_SECONDS,
    HR_AGENT_URL,
    HR_MCP_URL,
    PRODUCT_AGENT_URL,
    PRODUCT_MCP_URL,
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8311")
STEP_CAP_SECONDS = 45


def _mask(secret: str | None) -> str:
    if not secret:
        return "NOT SET (deterministic fallbacks will be used)"
    return f"set, {secret[:7]}...{secret[-4:]} ({len(secret)} chars)"


async def _report(name: str, coroutine) -> bool:
    start = time.time()
    try:
        detail = await asyncio.wait_for(coroutine, timeout=STEP_CAP_SECONDS)
        print(f"PASS  {name}  ({time.time() - start:.1f}s)  {detail}")
        return True
    except TimeoutError:
        print(
            f"HANG  {name}  gave no response within {STEP_CAP_SECONDS}s "
            "<-- this layer is your problem"
        )
        return False
    except Exception as exc:
        print(
            f"FAIL  {name}  ({time.time() - start:.1f}s)  "
            f"{type(exc).__name__}: {exc}"
        )
        return False


async def check_http(url: str) -> str:
    async with httpx.AsyncClient(timeout=10) as http:
        response = await http.get(url)
        return f"HTTP {response.status_code}"


async def check_groq_models() -> str:
    async with httpx.AsyncClient(timeout=15) as http:
        response = await http.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
        )
        response.raise_for_status()
        return "key accepted"


async def check_groq_completion() -> str:
    """POST differs from GET on some networks, so test a real completion."""
    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": "Reply with: ok"}],
                "max_tokens": 256,
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return f"model replied: {content[:40]!r}"


async def check_hr_agent() -> str:
    from backend.agents.hr_business.mcp_agent import HRBusinessMCPAgent

    agent = HRBusinessMCPAgent()
    await agent.connect()
    try:
        result = await agent.invoke(
            "What is the work from home policy?", "diagnose-hr"
        )
        return f"answer: {result['content'][:60]!r}"
    finally:
        await agent.close()


async def check_product_agent() -> str:
    from backend.agents.product_order.mcp_agent import ProductOrderMCPAgent

    agent = ProductOrderMCPAgent()
    await agent.connect()
    try:
        result = await agent.invoke(
            "How many laptops are currently in stock?", "diagnose-po"
        )
        return f"answer: {result['content'][:60]!r}"
    finally:
        await agent.close()


async def check_chat_api() -> str:
    async with httpx.AsyncClient(timeout=STEP_CAP_SECONDS - 1) as http:
        response = await http.post(
            f"{BACKEND_URL}/chat",
            json={"message": "What is the work from home policy?"},
        )
        response.raise_for_status()
        return f"answer: {response.json()['response'][:60]!r}"


async def main() -> None:
    print("Configuration")
    print(f"  GROQ_API_KEY        {_mask(os.getenv('GROQ_API_KEY'))}")
    print(f"  GROQ_MODEL          {GROQ_MODEL}")
    print(
        f"  GROQ timeout        {GROQ_TIMEOUT_SECONDS}s x "
        f"{1 + GROQ_MAX_RETRIES} attempts, max_tokens {GROQ_MAX_TOKENS}"
    )
    print()

    print("Local services")
    mcp_base_hr = HR_MCP_URL.removesuffix("/mcp")
    mcp_base_po = PRODUCT_MCP_URL.removesuffix("/mcp")
    await _report("HR MCP server         (8111)", check_http(mcp_base_hr))
    await _report("Product MCP server    (8112)", check_http(mcp_base_po))
    await _report(
        "HR A2A agent card     (8211)",
        check_http(f"{HR_AGENT_URL}/.well-known/agent-card.json"),
    )
    await _report(
        "Product A2A agent card(8212)",
        check_http(f"{PRODUCT_AGENT_URL}/.well-known/agent-card.json"),
    )
    print()

    if os.getenv("GROQ_API_KEY"):
        print("Groq API")
        await _report("Groq model list (GET)", check_groq_models())
        await _report("Groq completion (POST)", check_groq_completion())
        print()

    print("Agents invoked directly (bypasses A2A and the Host)")
    await _report("HR/Business agent", check_hr_agent())
    await _report("Product/Order agent", check_product_agent())
    print()

    print("Full flow through the Host")
    await _report("POST /chat            (8311)", check_chat_api())


if __name__ == "__main__":
    asyncio.run(main())
