"""Groq is the single model provider for both remote agents."""

from types import SimpleNamespace

import pytest
from agno.models.groq import Groq

from backend.agents.hr_business.mcp_agent import HRBusinessMCPAgent
from backend.agents.product_order.mcp_agent import ProductOrderMCPAgent
from backend.config import (
    GROQ_MAX_RETRIES,
    GROQ_MAX_TOKENS,
    GROQ_MODEL,
    GROQ_TIMEOUT_SECONDS,
)
from backend.mcp_servers.hr_business_server import search_hr_policy_data


def _completion(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_groq_defaults_are_a_tool_calling_chat_model():
    assert GROQ_MODEL == "openai/gpt-oss-120b"
    # Reasoning shares this budget, so a small cap truncates the answer away.
    assert GROQ_MAX_TOKENS >= 512


def test_agno_tool_selection_uses_groq():
    model = ProductOrderMCPAgent._build_model("test-key")
    assert isinstance(model, Groq)
    assert model.id == GROQ_MODEL
    assert model.api_key == "test-key"
    assert model.temperature == 0
    assert model.max_tokens == GROQ_MAX_TOKENS
    assert model.timeout == int(GROQ_TIMEOUT_SECONDS)
    assert model.max_retries == GROQ_MAX_RETRIES


def test_groq_attempts_fit_inside_the_host_task_budget():
    """The Host allows 60 s per task; a hung Groq call must fail sooner so the
    deterministic fallback still answers instead of timing out the A2A client."""
    worst_case = GROQ_TIMEOUT_SECONDS * (1 + GROQ_MAX_RETRIES)
    assert worst_case < 60


def test_retrieval_request_grounds_the_model_in_retrieved_context():
    matches = search_hr_policy_data("What is the work from home policy?")[
        "matches"
    ]
    request = HRBusinessMCPAgent._completion_request(
        "What is the work from home policy?", matches
    )

    assert request["model"] == GROQ_MODEL
    assert request["max_tokens"] == GROQ_MAX_TOKENS
    assert request["temperature"] == 0

    system, user = request["messages"]
    assert system["role"] == "system"
    assert "only the supplied context" in system["content"]
    assert user["role"] == "user"
    assert "What is the work from home policy?" in user["content"]
    assert "workplace_policy.md" in user["content"]
    assert "Work From Home Policy" in user["content"]
    assert "three days per week" in user["content"]


def test_model_answer_is_used_when_present():
    assert (
        HRBusinessMCPAgent._answer_text(_completion("  Remote work is allowed. "))
        == "Remote work is allowed."
    )


@pytest.mark.parametrize("content", [None, "", "   "])
def test_empty_model_answer_is_rejected_so_retrieval_can_take_over(content):
    """A truncated reasoning response must not reach the user as a blank reply."""
    with pytest.raises(ValueError):
        HRBusinessMCPAgent._answer_text(_completion(content))
