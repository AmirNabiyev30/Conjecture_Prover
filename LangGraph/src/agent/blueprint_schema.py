"""
Shared blueprint schema for the Hierarchical Blueprint Retrieval & Refinement System.

Defines ``BlueprintNode`` and ``BlueprintGraph`` — the internal DAG
representation used by retrieval agents and the refinement pipeline.

These are distinct from the ``LemmaTask``/``LemmaStatus`` types in
``blueprint_converter.py``, which are runtime types for the proving workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── BlueprintNode ──────────────────────────────────────────────────────────────

@dataclass
class BlueprintNode:
    """A single node in the proof blueprint DAG.

    Represents one lemma, definition, or theorem with its dependencies,
    retrieval data, and agent feedback.
    """

    id: str                                              # unique identifier
    title: str                                           # human-readable title
    statement: str                                       # natural-language / LaTeX statement
    lean_statement: Optional[str] = None                 # formal Lean type signature
    dependencies: list[str] = field(default_factory=list)  # IDs of nodes this depends on
    lemma_type: Optional[str] = None                     # "lemma", "theorem", "definition", etc.
    retrieved_examples: list[str] = field(default_factory=list)   # names of similar Mathlib decls
    refinement_notes: list[str] = field(default_factory=list)     # agent feedback notes

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary for JSON interchange."""
        return {
            "id": self.id,
            "title": self.title,
            "statement": self.statement,
            "lean_statement": self.lean_statement,
            "dependencies": self.dependencies,
            "lemma_type": self.lemma_type,
            "retrieved_examples": self.retrieved_examples,
            "refinement_notes": self.refinement_notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> BlueprintNode:
        """Deserialize from a plain dictionary."""
        return cls(
            id=d["id"],
            title=d["title"],
            statement=d["statement"],
            lean_statement=d.get("lean_statement"),
            dependencies=d.get("dependencies", []),
            lemma_type=d.get("lemma_type"),
            retrieved_examples=d.get("retrieved_examples", []),
            refinement_notes=d.get("refinement_notes", []),
        )


# ── BlueprintGraph ─────────────────────────────────────────────────────────────

@dataclass
class BlueprintGraph:
    """A directed acyclic graph representing a proof blueprint.

    Nodes are lemmas/definitions/theorems.  Edges are encoded via each node's
    ``dependencies`` list: if B depends on A, then A must be proved before B.
    """

    theorem_name: str = ""
    nodes: dict[str, BlueprintNode] = field(default_factory=dict)
    root_node: str = ""                                # ID of the main theorem node

    # ── Mutation ───────────────────────────────────────────────────────────

    def add_node(self, node: BlueprintNode) -> None:
        """Add a node to the graph.  Overwrites if ID already exists."""
        self.nodes[node.id] = node

    def add_dependency(self, source_id: str, target_id: str) -> None:
        """Add a directed edge: *source* depends on *target*.

        That is, ``source_id`` requires ``target_id`` to be proved first.
        """
        if source_id not in self.nodes:
            raise KeyError(f"Source node '{source_id}' not in graph")
        if target_id not in self.nodes:
            raise KeyError(f"Target node '{target_id}' not in graph")
        if target_id not in self.nodes[source_id].dependencies:
            self.nodes[source_id].dependencies.append(target_id)

    # ── Traversal ──────────────────────────────────────────────────────────

    def topological_sort(self) -> list[str]:
        """Return node IDs in topological order (dependencies first).

        Uses Kahn's algorithm.  Raises ``ValueError`` if a cycle is detected.
        """
        in_degree: dict[str, int] = {nid: 0 for nid in self.nodes}
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep in in_degree:
                    in_degree[node.id] += 1

        # Nodes with no incoming edges (no one depends on them, or they have no deps)
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result: list[str] = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            # Find nodes that depend on `current`
            for node in self.nodes.values():
                if current in node.dependencies:
                    in_degree[node.id] -= 1
                    if in_degree[node.id] == 0:
                        queue.append(node.id)

        if len(result) != len(self.nodes):
            raise ValueError("Cycle detected in blueprint DAG — topological sort impossible")

        return result

    def get_leaf_nodes(self) -> list[str]:
        """Return IDs of nodes that have no dependencies (axioms/base cases)."""
        return [nid for nid, node in self.nodes.items() if not node.dependencies]

    def get_subproblems(self) -> list[str]:
        """Return IDs of all nodes except the root (the sub-lemmas to prove)."""
        return [nid for nid in self.nodes if nid != self.root_node]

    def get_dependents(self, node_id: str) -> list[str]:
        """Return IDs of nodes that directly depend on ``node_id``."""
        return [
            nid for nid, node in self.nodes.items()
            if node_id in node.dependencies
        ]

    def ancestors(self, node_id: str) -> set[str]:
        """Return the transitive closure of nodes that ``node_id`` depends on."""
        result: set[str] = set()
        stack = list(self.nodes[node_id].dependencies)
        while stack:
            dep = stack.pop()
            if dep not in result:
                result.add(dep)
                stack.extend(self.nodes[dep].dependencies)
        return result

    # ── Metrics ────────────────────────────────────────────────────────────

    @property
    def node_count(self) -> int:
        """Total number of nodes in the graph."""
        return len(self.nodes)

    @property
    def depth(self) -> int:
        """Longest path from any leaf to the root (0-based from leaves)."""
        memo: dict[str, int] = {}

        def _depth(nid: str) -> int:
            if nid in memo:
                return memo[nid]
            node = self.nodes[nid]
            if not node.dependencies:
                memo[nid] = 0
            else:
                memo[nid] = 1 + max(_depth(d) for d in node.dependencies)
            return memo[nid]

        if not self.nodes:
            return 0
        return _depth(self.root_node)

    @property
    def total_dependency_count(self) -> int:
        """Sum of all dependency edges in the graph."""
        return sum(len(n.dependencies) for n in self.nodes.values())

    # ── Serialization ──────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize the full graph to a plain dictionary."""
        return {
            "theorem_name": self.theorem_name,
            "root_node": self.root_node,
            "nodes": [node.to_dict() for node in self.nodes.values()],
        }

    @classmethod
    def from_dict(cls, d: dict) -> BlueprintGraph:
        """Deserialize from a plain dictionary."""
        graph = cls(
            theorem_name=d.get("theorem_name", ""),
            root_node=d.get("root_node", ""),
        )
        for node_dict in d.get("nodes", []):
            node = BlueprintNode.from_dict(node_dict)
            graph.add_node(node)
        return graph


# ── Conversion from blueprint JSON ─────────────────────────────────────────────

def blueprint_json_to_graph(
    blueprint_json: list[dict],
    theorem_name: str = "",
) -> BlueprintGraph:
    """Convert a ``lake build :blueprintJson`` output into a ``BlueprintGraph``.

    The blueprint JSON is an array of node objects with ``type`` and ``data``
    fields, as produced by LeanArchitect's ``@[blueprint]`` annotation compiler.

    Only entries with ``type == "node"`` are converted.  The first theorem-type
    node encountered is treated as the root.
    """
    graph = BlueprintGraph(theorem_name=theorem_name)
    root_set = False

    for entry in blueprint_json:
        if entry.get("type") != "node":
            continue

        data = entry["data"]
        node_id = data["name"]

        # Dependencies: prefer usesLabels (resolved graph edges), fall back to uses
        proof_data = data.get("proof")
        if proof_data:
            uses_labels = list(proof_data.get("usesLabels", []))
            uses = list(proof_data.get("uses", []))
            deps = uses_labels if uses_labels else uses
        else:
            deps = []

        kind = data.get("statement", {}).get("latexEnv", "")

        node = BlueprintNode(
            id=node_id,
            title=node_id.replace("_", " ").title(),
            statement=data.get("statement", {}).get("text", ""),
            lean_statement=None,  # not in blueprint JSON; could be added later
            dependencies=deps,
            lemma_type=kind if kind else None,
        )

        graph.add_node(node)

        # First theorem/lemma node becomes the root
        if not root_set and kind in ("theorem", "lemma", "proposition", "corollary"):
            graph.root_node = node_id
            root_set = True

    # Fallback: if no theorem-type node was found, use the last node
    if not root_set and graph.nodes:
        graph.root_node = next(reversed(graph.nodes))

    return graph
