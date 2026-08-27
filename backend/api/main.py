"""Public backend API. The frontend talks only to this service."""

import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.host.host_agent import HostAgent


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


app = FastAPI(
    title="Enterprise Multi-Agent AI Assistant",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:4311",
        "http://localhost:4311",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.host_agent = HostAgent()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    session_id = payload.session_id or str(uuid.uuid4())
    response = await request.app.state.host_agent.chat(
        payload.message.strip(), session_id
    )
    return ChatResponse(response=response, session_id=session_id)
