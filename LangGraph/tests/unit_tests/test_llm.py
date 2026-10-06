"""Contract tests for the DeepSeek reasoning-content workaround in llm.py.

``llm.ReasoningPreservingChatDeepSeek`` exists because ``langchain-deepseek``
serialises assistant messages through a fixed allow-list of ``additional_kwargs``
and silently drops ``reasoning_content``. DeepSeek's thinking-mode API then
rejects a re-sent conversation with HTTP 400, which breaks every multi-turn graph
node — the model's own history becomes unsendable.

The first test below asserts the *upstream* behaviour. It is expected to fail the
day ``langchain-deepseek`` starts forwarding the field, and that failure is the
signal that the subclass (and this module) can be deleted — not a bug to fix. That
is why the dependency is pinned to an exact version in pyproject.toml: the day
should arrive as a deliberate upgrade, with someone reading this file, rather than
as a silent minor-version bump.

No network access: constructing a client does not call the API.
"""

import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_deepseek.chat_models import ChatDeepSeek

_AGENT_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "agent"
sys.path.insert(0, str(_AGENT_SRC))

from llm import ReasoningPreservingChatDeepSeek, init_chat_model  # noqa: E402

#: Enough to construct a client offline; no request is ever made.
_DUMMY = {"api_key": "dummy"}


def _assistant_on_the_wire(model, messages) -> dict:
    """The assistant entry the client would actually put in the request body."""
    payload = model._get_request_payload(messages)
    return next(m for m in payload["messages"] if m.get("role") == "assistant")


def _thinking_turn() -> list:
    """A re-sent conversation containing one thinking-mode assistant turn."""
    return [
        HumanMessage(content="hi"),
        AIMessage(content="...", additional_kwargs={"reasoning_content": "inner"}),
    ]


# ── the upstream behaviour this workaround depends on ────────────────────────

def test_upstream_drops_reasoning_content():
    """If this FAILS, the bug is fixed upstream: delete llm.py's subclass.

    This is a canary, not a regression. Check the newly resolved
    langchain-deepseek version, confirm the field now survives, then remove
    ReasoningPreservingChatDeepSeek, init_chat_model, and this file.
    """
    model = ChatDeepSeek(model="deepseek-v4-flash", **_DUMMY)
    assert "reasoning_content" not in _assistant_on_the_wire(model, _thinking_turn())


# ── the workaround ───────────────────────────────────────────────────────────

def test_subclass_re_adds_reasoning_content():
    model = ReasoningPreservingChatDeepSeek(model="deepseek-v4-flash", **_DUMMY)
    assert _assistant_on_the_wire(model, _thinking_turn())["reasoning_content"] == "inner"


def test_subclass_preserves_an_empty_reasoning_content():
    """The key has to be present even when empty, so presence — not truthiness —
    is what the override checks."""
    messages = [AIMessage(content="x", additional_kwargs={"reasoning_content": ""})]
    model = ReasoningPreservingChatDeepSeek(model="m", **_DUMMY)
    assert _assistant_on_the_wire(model, messages)["reasoning_content"] == ""


def test_subclass_leaves_messages_without_the_key_alone():
    messages = [HumanMessage(content="hi"), AIMessage(content="plain")]
    model = ReasoningPreservingChatDeepSeek(model="m", **_DUMMY)
    assert "reasoning_content" not in _assistant_on_the_wire(model, messages)


# ── the factory: which models get the subclass ───────────────────────────────

@pytest.mark.parametrize("model_name", ["deepseek-v4-flash", "deepseek-reasoner"])
def test_plain_deepseek_models_get_the_subclass(model_name):
    assert isinstance(init_chat_model(model_name, **_DUMMY),
                      ReasoningPreservingChatDeepSeek)


def test_explicit_deepseek_provider_gets_the_subclass():
    model = init_chat_model("deepseek-x", model_provider="deepseek", **_DUMMY)
    assert isinstance(model, ReasoningPreservingChatDeepSeek)


def test_openai_compatible_routing_is_left_alone():
    """e.g. deepseek-r1 through OpenRouter: langchain-openai does not drop the
    field, so the override must not apply."""
    model = init_chat_model(
        "deepseek/deepseek-r1", model_provider="openai",
        base_url="http://localhost", api_key="dummy",
    )
    assert not isinstance(model, ReasoningPreservingChatDeepSeek)


def test_non_deepseek_models_are_left_alone():
    model = init_chat_model("gpt-4o-mini", **_DUMMY)
    assert not isinstance(model, ReasoningPreservingChatDeepSeek)
