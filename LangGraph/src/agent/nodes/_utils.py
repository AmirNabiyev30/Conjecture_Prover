"""
Shared helpers used across multiple graph nodes.
"""

from langchain.messages import AnyMessage


def print_ai_response(label: str, msg: AnyMessage) -> None:
    """Print the AI's response content and any tool calls."""
    if hasattr(msg, "content") and msg.content:
        content = str(msg.content)
        if content.strip():
            print(f"   💬 {label} AI says: {content[:500]}")
            if len(content) > 500:
                print(f"      ... ({len(content)} total chars)")
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        print(f"   🛠️  {label} AI made {len(tool_calls)} tool call(s):")
        for tc in tool_calls:
            print(f" → {tc['name']}")
