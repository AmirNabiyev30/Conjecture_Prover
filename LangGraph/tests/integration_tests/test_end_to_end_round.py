"""Real end-to-end round test: blueprint generator → prove_lemma → aggregator.

Runs the ACTUAL compiled LangGraph one full round on the real Putnam 2025 A2
problem (seeded from ``test_blueprints/putnam_problems.txt/a2.txt``):

    blueprint_gen ──(tool loop)──▶ rebuild_blueprint ──(theorem_proving Sends)──▶
        prove_lemma ×N ──▶ aggregator ──▶ END

The graph is capped to a single round by monkeypatching
``routing.MAX_REFINEMENT_ROUNDS = 0`` so ``route_after_aggregator`` returns END
after the first aggregator (``global_round`` becomes 1). Everything is REAL:
the LLM, the Lean MCP REPL, ``lake build :blueprintJson``, and the file edits
applied to ``LeanWorkspace.lean`` — which is backed up and restored around the
run so the workspace is untouched afterward.

What this verifies that the isolated node tests cannot: the aggregator ACTUALLY
processes the proposals the provers returned. For every lemma the provers mark
PROVED, we assert the prover's ``old_str`` matches the pre-aggregator file
exactly once (the ``search_replace_workspace`` precondition), that the edit was
applied (old text gone from the post-aggregator file), and that the rebuilt
blueprint marks the lemma ``proved`` / ``sorry_free``.

Run with::

    cd LangGraph
    PYTHONPATH=src:src/agent python3 -m pytest tests/integration_tests/test_end_to_end_round.py -s -v -m "mcp"

Note: Putnam 2025 A2 is hard — a single round may prove zero lemmas. The test
is tolerant of that: the structural pipeline asserts always run, while the
edit-processing asserts only apply to lemmas the provers actually PROVED. Rich
output is printed so you can see exactly what happened either way.
"""

import difflib
import os
import sys
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv

_AGENT_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "agent"
sys.path.insert(0, str(_AGENT_SRC))

from config import MODEL_NAME, PROJECT_ROOT, WORKSPACE_PATH  # noqa: E402
from graph import build_graph  # noqa: E402
from nodes import routing as routing_module  # noqa: E402

pytestmark = [pytest.mark.anyio, pytest.mark.mcp, pytest.mark.slow]
load_dotenv()

# Putnam 2025 A2 input fixture (raw problem — the generator decomposes it).
A2_PATH = PROJECT_ROOT / "test_blueprints" / "putnam_problems.txt" / "a2.txt"

# Tunables (bounded so the test stays tractable on a hard theorem).
MAX_TURNS_PER_LEMMA = 10   # per-prover LLM turn budget (config default is 20)
RECURSION_LIMIT = 400      # generator tool loop + top-level node steps


def _trunc(text: str, width: int = 800) -> str:
    text = str(text)
    if len(text) <= width:
        return text
    return text[:width] + f"... ({len(text)} total chars)"


def _print_statuses(title: str, statuses: dict) -> None:
    print(f"      {title}:")
    for name, ls in statuses.items():
        print(
            f"         {name:45s} status={ls['status']:8s} sorry_free={ls['sorry_free']}"
        )


async def test_end_to_end_round(monkeypatch):
    """Full production graph, one round: generator → prover → aggregator."""
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")
    assert A2_PATH.is_file(), f"Missing input fixture: {A2_PATH}"

    workspace = Path(WORKSPACE_PATH)
    assert workspace.is_file(), f"Workspace file does not exist: {workspace}"
    a2_source = A2_PATH.read_text(encoding="utf-8")

    # ── Backup real workspace + blueprint JSON build artifacts ────────────
    workspace_backup = workspace.read_text(encoding="utf-8")
    json_dir = PROJECT_ROOT / ".lake" / "build" / "blueprint" / "module"
    json_files = [
        "LeanWorkspace.json",
        "LeanWorkspace.json.hash",
        "LeanWorkspace.json.trace",
    ]
    json_backup: dict[str, str] = {}
    for fn in json_files:
        p = json_dir / fn
        if p.is_file():
            json_backup[fn] = p.read_text(encoding="utf-8")

    try:
        # ── Seed the workspace with the real Putnam A2 problem ──────────
        workspace.write_text(a2_source, encoding="utf-8")
        print(f"\n{'=' * 70}")
        print("🧪 E2E ROUND: blueprint_gen → prove_lemma → aggregator")
        print(f"   Input: {A2_PATH}  |  workspace: {workspace}")
        print(f"   Model: {MODEL_NAME}  |  max_turns_per_lemma: {MAX_TURNS_PER_LEMMA}")
        print(f"{'=' * 70}\n")

        # ── Cap the graph to ONE aggregator round ────────────────────────
        monkeypatch.setattr(routing_module, "MAX_REFINEMENT_ROUNDS", 0)

        # ── Build the REAL production graph ──────────────────────────────
        graph = await build_graph()

        inputs = {
            "theorem": (
                "The target formalization is in the Lean workspace file at "
                f"`{workspace}`. Read the file to find the theorem statement "
                "and any existing definitions."
            ),
            "workspacePATH": str(workspace),
            "project_root": str(PROJECT_ROOT),
        }
        context = {
            "model": MODEL_NAME,
            "max_iterations": 16,
            "max_turns_per_lemma": MAX_TURNS_PER_LEMMA,
        }
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}

        # ── Stream the run, capturing each node's update ─────────────────
        first_pass_statuses: dict = {}
        first_pass_blueprint = None
        proposals: list[dict] = []
        aggregator_result: dict | None = None
        generator_final = ""
        generator_tool_calls: list[str] = []
        pre_aggregator_content: str | None = None
        post_aggregator_content: str | None = None
        interrupted: list[str] = []

        async for chunk in graph.astream(
            inputs, config=config, context=context, stream_mode="updates"
        ):
            if "__interrupt__" in chunk:
                interrupted.append(str(chunk["__interrupt__"]))
                print(f"   ⛔ INTERRUPT: {chunk['__interrupt__']}")
                break
            for node, update in chunk.items():
                print(f"\n   ▶ NODE: {node}")
                if node == "blueprint_gen":
                    msgs = update.get("blueprint_generator_messages", [])
                    if msgs:
                        generator_final = str(getattr(msgs[-1], "content", ""))
                    generator_tool_calls = [
                        call["name"]
                        for m in msgs
                        for call in getattr(m, "tool_calls", [])
                    ]
                    print(f"      generator_tool_calls={generator_tool_calls}")
                elif node.startswith("rebuild_blueprint"):
                    first_pass_blueprint = update.get("blueprint")
                    first_pass_statuses = update.get("lemma_statuses", {})
                    if workspace.is_file():
                        pre_aggregator_content = workspace.read_text(encoding="utf-8")
                    n_nodes = (
                        len(first_pass_blueprint.nodes)
                        if first_pass_blueprint is not None
                        else 0
                    )
                    print(f"      blueprint nodes={n_nodes}")
                    _print_statuses("first-pass statuses (post-rebuild)", first_pass_statuses)
                elif node.startswith("prove_lemma"):
                    for p in update.get("pending_proposals", []):
                        proposals.append(p)
                        print(
                            f"      proposal: {p.get('lemma_id')}  "
                            f"status={p.get('status')}  proved={p.get('proved')}"
                        )
                elif node == "aggregator":
                    aggregator_result = update
                    if workspace.is_file():
                        post_aggregator_content = workspace.read_text(encoding="utf-8")
                    print(
                        f"      global_round={update.get('global_round')}  "
                        f"pending_reset={update.get('pending_proposals') == []}"
                    )
                    _print_statuses(
                        "aggregator statuses (post-rebuild)", update.get("lemma_statuses", {})
                    )
                else:
                    # tools_bp / tools_br / human_tool_* — informational only
                    print(f"      (tool loop turn)")
                print(f"      update: {_trunc(update)}")

        # ── Summary ──────────────────────────────────────────────────────
        final_statuses = (aggregator_result or {}).get("lemma_statuses", {})
        n_nodes = (
            len(first_pass_blueprint.nodes) if first_pass_blueprint is not None else 0
        )
        n_unproved = sum(
            1 for ls in first_pass_statuses.values() if ls["status"] == "unproved"
        )
        n_proved = sum(1 for p in proposals if p.get("proved"))
        print("\n" + "=" * 70)
        print("📊 E2E ROUND SUMMARY")
        print("=" * 70)
        print(f"generator_tool_calls   = {generator_tool_calls}")
        print(f"generator_final_chars  = {len(generator_final)}")
        print(f"first_pass_nodes       = {n_nodes}")
        print(f"first_pass_unproved    = {n_unproved}")
        print(f"proposals              = {len(proposals)}  (proved={n_proved})")
        print(
            f"aggregator_round       = {aggregator_result.get('global_round') if aggregator_result else None}"
        )
        print(f"final_proved           = {sum(1 for ls in final_statuses.values() if ls['status'] == 'proved')} / {len(final_statuses)}")
        print("=" * 70)

        # ── Show exactly what the aggregator changed in the file ─────────
        if (
            pre_aggregator_content is not None
            and post_aggregator_content is not None
            and pre_aggregator_content != post_aggregator_content
        ):
            diff = difflib.unified_diff(
                pre_aggregator_content.splitlines(),
                post_aggregator_content.splitlines(),
                fromfile="post-generator (pre-aggregator)",
                tofile="post-aggregator",
                lineterm="",
            )
            print("\n── AGGREGATOR FILE DIFF (what the aggregator changed) ──")
            for line in diff:
                print("   " + line)
            print("──────────────────────────────────────────────────────────")
        else:
            print("\n   (aggregator made no file changes — no edits applied)")

        # ── Structural: the pipeline actually ran ────────────────────────
        assert not interrupted, f"Graph interrupted by ask_human: {interrupted}"
        assert (
            first_pass_blueprint is not None and first_pass_blueprint.nodes
        ), "rebuild_blueprint produced no blueprint nodes — the generator skeleton likely failed to build"
        assert n_unproved >= 1, "no unproved lemmas after rebuild — nothing for prove_lemma to do"
        assert proposals, "no prove_lemma proposals collected — Send dispatch / line-range splicing failed"
        assert aggregator_result is not None, "aggregator did not run (graph ended before aggregator)"
        assert aggregator_result.get("global_round") == 1, (
            f"expected global_round == 1, got {aggregator_result.get('global_round')}"
        )
        assert aggregator_result.get("pending_proposals") == [], (
            "aggregator did not reset pending_proposals"
        )

        # ── Headline check: aggregator ACTUALLY processed the edits ──────
        proved_props = [p for p in proposals if p.get("proved") and p.get("new_str")]
        if not proved_props:
            print(
                "\n   ⚠️  No lemma was PROVED this round (hard theorem). "
                "Skipping edit-application asserts — the pipeline ran end-to-end."
            )
        else:
            assert pre_aggregator_content is not None and post_aggregator_content is not None
            for p in proved_props:
                name = p["lemma_id"]
                old, new = p["old_str"], p["new_str"]
                found = pre_aggregator_content.count(old)
                assert found == 1, (
                    f"PROVED proposal '{name}': old_str appears {found} time(s) in the "
                    f"pre-aggregator file (search_replace_workspace requires exactly 1). "
                    f"This is the end-to-end splice/match invariant."
                )
                assert post_aggregator_content.count(old) == 0, (
                    f"PROVED proposal '{name}': old_str still present after aggregator — "
                    f"the edit was NOT applied"
                )
                ls = final_statuses.get(name)
                assert ls is not None, f"final statuses missing lemma '{name}'"
                assert ls["status"] == "proved", (
                    f"lemma '{name}' not proved after aggregation: {ls}"
                )
                assert ls["sorry_free"] is True, (
                    f"lemma '{name}' not sorry_free after aggregation: {ls}"
                )
                print(
                    f"   ✅ aggregator applied edit for '{name}' "
                    f"(prover new_str present verbatim: {new.strip() in post_aggregator_content})"
                )

    finally:
        # ── Restore the real workspace + blueprint JSON ──────────────────
        workspace.write_text(workspace_backup, encoding="utf-8")
        for fn, content in json_backup.items():
            (json_dir / fn).write_text(content, encoding="utf-8")
        print("\n   ♻️  Restored LeanWorkspace.lean + blueprint JSON from backup")
