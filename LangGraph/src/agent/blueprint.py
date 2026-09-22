"""
Canonical blueprint data model + runtime types.

``Blueprint`` is the single typed representation of a proof blueprint used
across the agent.  Its ``nodes`` are :class:`LemmaTask` objects — the unit of
work handed to each parallel prover — so there is no separate node class or
converter layer:

- parsing ``lake build :blueprintJson`` output (``from_blueprint_json``)
- a plain ``dict`` view for LLM context injection (``to_dict`` / ``from_dict``)
- runtime projections (``derive_lemma_statuses``) and workflow types
  (``LemmaTask`` / ``LemmaStatus`` / ``ProofProposal`` / ``ProofResult``)

The LLM never parses raw blueprint JSON — code does, through this class.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional, TypedDict


# ── Runtime types ──────────────────────────────────────────────────────────────

ProposalStatus = Literal["PROVED", "TOO_HARD", "STATEMENT_WRONG"]


class LemmaStatus(TypedDict):
    """Status of a single lemma, derived fresh each aggregator round from the
    blueprint + pending proposals. Not manually maintained."""
    name: str
    statement: str                    # LaTeX statement text
    sorry_free: bool                  # from blueprint JSON (no sorries in body)
    status: Literal["unproved", "proved"]
    dependencies: list[str]           # LaTeX labels this lemma depends on
    feedback: str                     # failure reason if unproved (from prover)


class LemmaTask(TypedDict):
    """A single lemma/theorem/definition in the blueprint.

    This is the primary unit of work passed into LangGraph nodes: each task is
    one blueprint node, and parallel provers prove tasks independently.
    """
    name: str                          # e.g. "monotone_tendsto_ge"
    kind: str                          # "definition" | "theorem" | "lemma"
    statement: str                     # LaTeX statement text
    proof_sketch: str | None           # natural-language proof sketch (if any)
    file: str                          # source .lean file path
    start_line: int                    # line range start (1-indexed)
    end_line: int                      # line range end (1-indexed)
    dependencies: list[str]            # LaTeX labels this lemma depends on
    sorry_free: bool                   # from blueprint JSON (no sorries in body)


class ProofProposal(TypedDict):
    """What a single parallel prover agent returns. Never applied directly —
    only the aggregator writes to the canonical file."""
    lemma_id: str
    status: ProposalStatus             # PROVED | TOO_HARD | STATEMENT_WRONG
    old_str: str                       # full lemma declaration, must be unique in file
    new_str: str | None                # None if failed
    proved: bool
    feedback: str                      # trial log / failure details (for blueprint_refiner)


class ProofResult(TypedDict):
    """Result of proving a single lemma."""
    name: str                          # lemma name
    success: bool                      # whether the proof was completed
    error: str | None                  # error message if failed


@dataclass
class UnsolvedSummary:
    """Count how many blueprint nodes were left unsolved after the workflow ran to its budget.

    Produced by :func:`scan_unsolved`.  ``unsolved`` is the ordered list of node
    names whose status is still ``"unproved"``.
    """
    total: int = 0
    proved: int = 0
    unproved: int = 0
    unsolved: list[str] = field(default_factory=list)


# ── Blueprint ─────────────────────────────────────────────────────────────────

@dataclass
class Blueprint:
    """A proof blueprint: a DAG of :class:`LemmaTask` nodes plus theorem metadata."""

    theorem_name: str = ""
    statement: str = ""                                   # informal statement of the main theorem
    nodes: list[LemmaTask] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    domain: list[str] = field(default_factory=list)
    source: str = "blueprint"                             # "blueprint" | "mathlib"

    # ── Construction from `lake build :blueprintJson` ─────────────────────

    @classmethod
    def from_blueprint_json(
        cls,
        blueprint_json: list[dict],
        theorem_name: str = "",
        project_root: str | Path | None = None,
    ) -> Blueprint:
        """Parse the array-of-nodes format emitted by ``lake build :blueprintJson``.

        Only entries with ``type == "node"`` are converted.  Dependencies prefer
        ``proof.usesLabels`` (resolved graph edges); they fall back to
        ``proof.uses`` (Lean names) when no labels exist.

        When *project_root* is given, absolute ``file`` paths (as written by
        Lean's ``extract_blueprint``) are normalized to paths relative to the
        project root, so the parsed blueprint is portable across machines.
        """
        root = Path(project_root) if project_root is not None else None
        nodes: list[LemmaTask] = []
        for entry in blueprint_json:
            if entry.get("type") != "node":
                continue
            data = entry["data"]
            proof = data.get("proof") or {}
            uses_labels = list(proof.get("usesLabels", []))
            uses = list(proof.get("uses", []))
            deps = uses_labels if uses_labels else uses
            loc = (data.get("location") or {}).get("range") or {}
            nodes.append(LemmaTask(
                name=data["name"],
                kind=data.get("statement", {}).get("latexEnv", "") or "unknown",
                statement=data.get("statement", {}).get("text", ""),
                proof_sketch=proof.get("text"),
                file=_normalize_file_path(data.get("file", ""), root),
                start_line=(loc.get("pos") or {}).get("line", 0),
                end_line=(loc.get("endPos") or {}).get("line", 0),
                dependencies=deps,
                sorry_free=bool(data.get("sorryFree", False)),
            ))

        blueprint = cls(theorem_name=theorem_name, nodes=nodes)
        if not blueprint.theorem_name:
            blueprint.theorem_name = blueprint.root_node() or ""
        return blueprint

    # ── Dict serialization ────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary (theorem, nodes/edges, metadata)."""
        return {
            "theorem": self.theorem_name,
            "statement": self.statement,
            "blueprint": {
                "nodes": [dict(n) for n in self.nodes],
                "edges": [
                    {"source": n["name"], "target": dep}
                    for n in self.nodes for dep in n["dependencies"]
                ],
            },
            "metadata": {
                "imports": self.imports,
                "domain": self.domain,
                "source": self.source,
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> Blueprint:
        """Deserialize from a plain dictionary produced by :meth:`to_dict`."""
        blueprint_data = d.get("blueprint", {}) or {}
        metadata = d.get("metadata", {}) or {}
        return cls(
            theorem_name=d.get("theorem", ""),
            statement=d.get("statement", ""),
            nodes=[dict(nd) for nd in blueprint_data.get("nodes", [])],
            imports=list(metadata.get("imports", [])),
            domain=list(metadata.get("domain", [])),
            source=metadata.get("source", "blueprint"),
        )

    # ── Lookup & traversal ────────────────────────────────────────────────

    def node_by_id(self, node_id: str) -> Optional[LemmaTask]:
        """Return the node (:class:`LemmaTask`) with *node_id*, or ``None``."""
        for node in self.nodes:
            if node["name"] == node_id:
                return node
        return None

    def root_node(self) -> Optional[str]:
        """Name of the main theorem node: the last theorem/lemma/proposition/
        corollary node (the main result is emitted last in topological order),
        else the last node as a fallback."""
        root = None
        for node in self.nodes:
            if node["kind"] in ("theorem", "lemma", "proposition", "corollary"):
                root = node["name"]
        return root if root is not None else (self.nodes[-1]["name"] if self.nodes else None)

    def topological_order(self) -> list[str]:
        """Return node names in topological order (dependencies first).

        Uses Kahn's algorithm.  Raises ``ValueError`` if a cycle is detected.
        """
        in_degree: dict[str, int] = {n["name"]: 0 for n in self.nodes}
        children: dict[str, list[str]] = {n["name"]: [] for n in self.nodes}
        for node in self.nodes:
            for dep in node["dependencies"]:
                if dep in in_degree:
                    in_degree[node["name"]] += 1
                    children[dep].append(node["name"])

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result: list[str] = []
        while queue:
            current = queue.pop(0)
            result.append(current)
            for child in children[current]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(result) != len(self.nodes):
            raise ValueError("Cycle detected in blueprint DAG — topological sort impossible")
        return result


# ── Loading & projections ──────────────────────────────────────────────────────

def _normalize_file_path(file: str, project_root: Path | None) -> str:
    """Convert an absolute ``file`` path from the generated blueprint JSON into a
    path relative to *project_root* (when the file lives inside it).

    Lean's ``extract_blueprint`` writes absolute source paths into the JSON
    (e.g. ``/home/user/project/LeanWorkspace.lean``); converting them to
    relative paths keeps the parsed blueprint portable across machines.
    """
    if not file or project_root is None:
        return file
    path = Path(file)
    if path.is_absolute():
        try:
            return str(path.relative_to(project_root))
        except ValueError:
            pass
    return file


def load_blueprint_json(project_root: str | Path, module_name: str = "ConjectureProver") -> list[dict]:
    """Load the blueprint JSON file for a given module.

    Args:
        project_root: Path to the Lean project root.
        module_name: Name of the Lean module (default: "ConjectureProver").

    Returns:
        The parsed blueprint JSON (list of node dicts).
    """
    json_path = (
        Path(project_root)
        / ".lake/build/blueprint/module"
        / f"{module_name}.json"
    )
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def derive_lemma_statuses(blueprint: Blueprint) -> dict[str, LemmaStatus]:
    """Derive a fresh dict of LemmaStatus from a parsed :class:`Blueprint`.

    Called by the aggregator after ``build_blueprint_json()``, so the blueprint
    is always up to date.  ``sorry_free`` comes directly from the parsed nodes
    (it reflects whether the lemma body still contains ``sorry``).  Status is
    initially ``"proved"`` if ``sorry_free`` else ``"unproved"``; the aggregator
    then merges in feedback from any proposals whose lemma was not proved.
    """
    return {
        node["name"]: LemmaStatus(
            name=node["name"],
            statement=node["statement"],
            sorry_free=node["sorry_free"],
            status="proved" if node["sorry_free"] else "unproved",
            dependencies=node["dependencies"],
            feedback="",
        )
        for node in blueprint.nodes
    }


def scan_unsolved(
    blueprint: Blueprint | None = None,
    lemma_statuses: dict[str, LemmaStatus] | None = None,
) -> UnsolvedSummary:
    """Scan how many nodes were left unsolved after the workflow ran to its budget.

    Counts EVERY node with ``status == "unproved"`` regardless of ``kind`` — an
    unproved definition counts the same as an unproved lemma.  This is a thin,
    reusable wrapper around the same ``status == "unproved"`` logic used by the
    refiner/aggregator, so "unsolved" has a single source of truth.

    When *lemma_statuses* is None, statuses are derived fresh from *blueprint*
    via :func:`derive_lemma_statuses`.  ``total`` is ``len(blueprint.nodes)``
    when a blueprint is given, else ``len(lemma_statuses)``.

    Args:
        blueprint: The parsed :class:`Blueprint` (optional). Supplies the node
            count and the fallback status derivation when no statuses are given.
        lemma_statuses: A ``dict[str, LemmaStatus]`` as produced by
            :func:`derive_lemma_statuses` (optional).

    Returns:
        An :class:`UnsolvedSummary` with total/proved/unproved counts and the
        ordered list of unsolved node names.
    """
    if lemma_statuses is None:
        if blueprint is None:
            return UnsolvedSummary()
        lemma_statuses = derive_lemma_statuses(blueprint)

    total = len(blueprint.nodes) if blueprint is not None else len(lemma_statuses)
    unsolved = [name for name, ls in lemma_statuses.items() if ls["status"] == "unproved"]
    return UnsolvedSummary(
        total=total,
        proved=total - len(unsolved),
        unproved=len(unsolved),
        unsolved=unsolved,
    )


# ── Source-text status derivation ─────────────────────────────────────────────

# Escape hatches an LLM could use to leave a proof unfinished.  ``sorry`` also
# covers ``sorry_using`` and ``sorryAx`` as substrings.
_SORRY_ESCAPE_MARKERS = ("sorry", "admit")


def _decl_contains_escape(decl_text: str) -> bool:
    """True if a spliced Lean declaration body still contains an escape hatch.

    Mirrors the prover/refiner contract that a real proof must contain no
    ``sorry`` / ``sorry_using`` / ``admit`` escape.  ``sorry`` is a substring of
    ``sorry_using`` and ``sorryAx``, so a single marker check covers all of them.
    """
    lowered = decl_text.lower()
    return any(marker in lowered for marker in _SORRY_ESCAPE_MARKERS)


def derive_lemma_statuses_from_source(
    blueprint: Blueprint,
    source_text: str,
) -> dict[str, LemmaStatus]:
    """Derive :class:`LemmaStatus` by inspecting the actual Lean source text.

    The LeanArchitect blueprint JSON does not emit a ``sorryFree`` field, so
    :func:`derive_lemma_statuses` cannot distinguish proved from unproved nodes
    from the JSON alone.  This function splices each node's declaration by its
    line range — the same pattern ``theorem_proving`` uses — and marks a node
    ``unproved`` while its body still contains a ``sorry`` / ``sorry_using`` /
    ``admit`` escape; otherwise ``proved``.  Nodes with no usable line range fall
    back to the JSON-derived status.
    """
    lines = source_text.splitlines(keepends=True)
    statuses = derive_lemma_statuses(blueprint)
    for node in blueprint.nodes:
        start, end = node["start_line"], node["end_line"]
        if start <= 0 or end < start or end > len(lines):
            continue
        decl = "".join(lines[start - 1:end])
        has_escape = _decl_contains_escape(decl)
        statuses[node["name"]] = {
            **statuses[node["name"]],
            "sorry_free": not has_escape,
            "status": "unproved" if has_escape else "proved",
        }
    return statuses


def scan_unsolved_from_file(
    blueprint: Blueprint,
    source_text: str,
) -> UnsolvedSummary:
    """Scan unsolved nodes from the actual Lean workspace source.

    Prefer this over :func:`scan_unsolved` when the blueprint JSON lacks the
    ``sorryFree`` field (LeanArchitect output): "unsolved" is decided from the
    real declaration bodies in *source_text* rather than from the JSON.
    """
    return scan_unsolved(
        blueprint,
        derive_lemma_statuses_from_source(blueprint, source_text),
    )


def derive_lemma_statuses_from_workspace(
    blueprint: Blueprint,
    workspace_path: str | Path,
) -> dict[str, LemmaStatus]:
    """Derive :class:`LemmaStatus` from the real workspace source text.

    Wraps :func:`derive_lemma_statuses_from_source` so the aggregator and the
    blueprint rebuild can detect proofs that the LeanArchitect blueprint JSON
    cannot (it has no ``sorryFree`` field, so every node defaults to unproved).
    Falls back to the JSON-derived statuses if the source cannot be read.
    """
    try:
        source_text = Path(workspace_path).read_text()
        return derive_lemma_statuses_from_source(blueprint, source_text)
    except Exception as e:
        print(f"   ⚠️  Could not derive statuses from source; using JSON statuses: {e}")
        return derive_lemma_statuses(blueprint)
