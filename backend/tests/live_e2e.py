"""Run after all five backend services are started."""

import asyncio

import httpx


CASES = [
    ("What is the work from home policy?", "three days"),
    ("How many laptops are currently in stock?", "50"),
    ("What is the status of order ORD1001?", "Pending"),
    ("Show me information about product P1001.", "P1001"),
]


async def main() -> None:
    async with httpx.AsyncClient(timeout=90) as client:
        for query, expected in CASES:
            response = await client.post(
                "http://127.0.0.1:8311/chat", json={"message": query}
            )
            response.raise_for_status()
            answer = response.json()["response"]
            assert expected.lower() in answer.lower(), (query, answer)
            print(f"PASS: {query}\n  {answer}\n")


if __name__ == "__main__":
    asyncio.run(main())
