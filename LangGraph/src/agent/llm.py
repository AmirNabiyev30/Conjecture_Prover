"""
Reasoning-aware chat model factory.

DeepSeek's thinking-mode models (e.g. `deepseek-v4-flash`, `deepseek-reasoner`)
return a `reasoning_content` field on every assistant message. When a
conversation is re-sent across turns — exactly what LangGraph does when a node
passes its accumulated message history back to the model — `langchain-openai`'s
`_convert_message_to_dict` drops arbitrary `additional_kwargs`, including
`reasoning_content`. DeepSeek's API then rejects the request with HTTP 400:

    The `reasoning_content` in the thinking mode must be passed back to the API.

This was reproduced against the real DeepSeek API: the drop happens for any
re-sent assistant message, and the 400 fires when a thinking-mode assistant turn
is sent back without its `reasoning_content` key (the graph's state-replacement
pattern `[AIMessage]` is the trigger).

This module provides:
- `ReasoningPreservingChatDeepSeek` — a `ChatDeepSeek` subclass that re-injects
  `reasoning_content` into the outgoing request payload whenever the source
  `AIMessage` carries the key (even if its value is an empty string).
- `init_chat_model` — a drop-in replacement for
  `langchain.chat_models.init_chat_model` that returns the subclass for
  DeepSeek models and otherwise delegates to the original factory.
"""

from __future__ import annotations

from typing import Any

from langchain.chat_models import init_chat_model as _init_chat_model
from langchain_core.messages import AIMessage
from langchain_deepseek.chat_models import ChatDeepSeek


class ReasoningPreservingChatDeepSeek(ChatDeepSeek):
    """`ChatDeepSeek` that preserves `reasoning_content` across multi-turn calls.

    The base `_get_request_payload` serializes each message with
    `_convert_message_to_dict`, which only forwards a fixed allow-list of
    `additional_kwargs` (`tool_calls`, `function_call`, `audio`, `name`, `role`)
    and silently drops `reasoning_content`. This override re-adds the key to
    each outgoing assistant message when the corresponding source `AIMessage`
    still carries it, so DeepSeek's thinking-mode requirement is satisfied.
    """

    def _get_request_payload(
        self,
        input_: Any,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        messages = self._convert_input(input_).to_messages()
        out = payload.get("messages", [])
        for i, msg in enumerate(out):
            if i < len(messages) and isinstance(messages[i], AIMessage):
                additional_kwargs = messages[i].additional_kwargs
                if "reasoning_content" in additional_kwargs:
                    msg["reasoning_content"] = additional_kwargs["reasoning_content"]
        return payload


def init_chat_model(model_name: str, **kwargs: Any):
    """Initialize a chat model, preserving DeepSeek reasoning content.

    Mirrors `langchain.chat_models.init_chat_model`; only for a *plain* DeepSeek
    setup (model name prefixed `deepseek-*`, no explicit provider override, no
    custom `base_url`/`api_base`) does it return a
    `ReasoningPreservingChatDeepSeek` so multi-turn conversation history is
    accepted by the API.

    Every other case — OpenAI (`gpt-*`, `o1`/`o3`), Anthropic, or any model
    routed through an OpenAI-compatible proxy such as OpenRouter (e.g.
    `deepseek/deepseek-r1` with `model_provider="openai"` and a `base_url`) — is
    delegated to the original `langchain.chat_models.init_chat_model` unchanged,
    so no other provider is affected.
    """
    model_provider = kwargs.get("model_provider", "deepseek")
    is_plain_deepseek = (
        isinstance(model_name, str)
        and model_name.startswith("deepseek")
        and (model_provider is None or model_provider == "deepseek")
        and "base_url" not in kwargs
        and "api_base" not in kwargs
    )
    if is_plain_deepseek:
        # ChatDeepSeek has no `model_provider` param; drop it before construction.
        kwargs = {k: v for k, v in kwargs.items() if k != "model_provider"}
        return ReasoningPreservingChatDeepSeek(model=model_name, **kwargs)
    return _init_chat_model(model_name, **kwargs)
