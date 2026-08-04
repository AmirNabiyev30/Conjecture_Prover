"""Interactive LLM-as-judge test for blueprint-generation A/B results.

Run explicitly with::

    RUN_BLUEPRINT_JUDGE=1 pytest -s tests/integration_tests/test_blueprint_ab_judge.py

Paste each generated blueprint one line at a time and finish each input with
``__END__`` on its own line.
"""

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage

_AGENT_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "agent"
sys.path.insert(0, str(_AGENT_SRC))

from config import MODEL_NAME, MODEL_TIMEOUT  # noqa: E402


pytestmark = pytest.mark.anyio
load_dotenv()


JUDGE_PROMPT = """You are an expert Lean 4 and Mathlib reviewer judging two blueprint
decompositions of the same theorem.

Compare the candidates using these criteria:
1. Faithfulness to the target theorem and its hypotheses.
2. Correctness and plausibility of Lean declarations and types.
3. Quality of the dependency graph and whether dependencies are meaningful.
4. Appropriate use of Mathlib rather than unnecessary custom definitions.
5. Minimality, clarity, and usefulness for a later theorem-proving agent.

Return:
- Winner: A, B, or Tie
- A score from 1–10 for each candidate
- The three most important reasons for the decision
- Any serious flaw that could invalidate either blueprint

Judge the code itself. Do not reward a candidate merely for being longer.
"""


def _read_blueprint(label: str) -> str:
    """Read multiline blueprint input until the sentinel line is entered."""
    print(f"\nPaste {label} blueprint; enter __END__ on its own line when finished:")
    lines: list[str] = []
    while True:
        line = input()
        if line == "__END__":
            break
        lines.append(line)
    return "\n".join(lines)


@pytest.mark.mcp
@pytest.mark.slow
async def test_judge_blueprint_generation_ab_results():
    """Ask an LLM to compare two manually supplied A/B blueprint outputs."""
    if not os.environ.get("RUN_BLUEPRINT_JUDGE"):
        pytest.skip("Set RUN_BLUEPRINT_JUDGE=1 to run the interactive judge")
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")

    blueprint_a = _read_blueprint("Variant A (with important-module analysis)")
    blueprint_b = _read_blueprint("Variant B (without module analysis)")
    assert blueprint_a.strip(), "Variant A blueprint cannot be empty"
    assert blueprint_b.strip(), "Variant B blueprint cannot be empty"

    llm = init_chat_model(MODEL_NAME, timeout=MODEL_TIMEOUT)
    response = await llm.ainvoke(
        [
            SystemMessage(content=JUDGE_PROMPT),
            HumanMessage(
                content=(
                    "Compare these two blueprint outputs for the same theorem.\n\n"
                    "===== VARIANT A =====\n"
                    f"{blueprint_a}\n\n"
                    "===== VARIANT B =====\n"
                    f"{blueprint_b}"
                )
            ),
        ]
    )

    judgment = str(getattr(response, "content", response))
    print("\n===== LLM BLUEPRINT A/B JUDGMENT =====")
    print(judgment)
    print("======================================\n")

    assert judgment.strip(), "The judge returned an empty response"
