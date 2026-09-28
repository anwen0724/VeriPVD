from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


FORBIDDEN_FORMAL_KEYS = {
    "chain_question",
    "analysis_task",
    "prompt",
    "semantic_roles",
    "role_hint",
    "candidate_role",
    "source_snippets",
    "retrieved_knowledge",
    "finding",
    "confidence",
    "diagnostics",
}


@dataclass(frozen=True)
class ChainTargetRef:
    target_id: str
    node_id: str
    name: str
    module: str

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "node_id": self.node_id,
            "name": self.name,
            "module": self.module,
        }


@dataclass(frozen=True)
class ChainLoc:
    file: str
    line_start: int
    line_end: int

    def to_json_dict(self) -> dict[str, Any]:
        return {"file": self.file, "line_start": self.line_start, "line_end": self.line_end}


@dataclass(frozen=True)
class ChainNode:
    node_id: str
    kind: str
    name: str
    module: str
    loc: ChainLoc | None = None

    def to_json_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "node_id": self.node_id,
            "kind": self.kind,
            "name": self.name,
            "module": self.module,
        }
        if self.loc is not None:
            result["loc"] = self.loc.to_json_dict()
        return result


@dataclass(frozen=True)
class ChainEdge:
    edge_id: str
    src: str
    dst: str
    kind: str

    def to_json_dict(self) -> dict[str, Any]:
        return {"edge_id": self.edge_id, "src": self.src, "dst": self.dst, "kind": self.kind}


@dataclass(frozen=True)
class ChainSourceLocation:
    loc_id: str
    file: str
    line_start: int
    line_end: int
    node_ids: list[str] = field(default_factory=list)
    edge_ids: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "loc_id": self.loc_id,
            "file": self.file,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "node_ids": list(self.node_ids),
            "edge_ids": list(self.edge_ids),
        }


@dataclass(frozen=True)
class PermissionChain:
    chain_id: str
    seed_targets: list[ChainTargetRef]
    nodes: list[ChainNode]
    edges: list[ChainEdge]
    source_locations: list[ChainSourceLocation]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "seed_targets": [target.to_json_dict() for target in self.seed_targets],
            "nodes": [node.to_json_dict() for node in self.nodes],
            "edges": [edge.to_json_dict() for edge in self.edges],
            "source_locations": [loc.to_json_dict() for loc in self.source_locations],
        }


@dataclass(frozen=True)
class PermissionChainGraphs:
    graph_id: str
    chains: list[PermissionChain]
    schema_version: str = "0.1"

    def to_json_dict(self) -> dict[str, Any]:
        result = {
            "graph_id": self.graph_id,
            "schema_version": self.schema_version,
            "chains": [chain.to_json_dict() for chain in self.chains],
        }
        assert_no_forbidden_formal_keys(result)
        return result


def assert_no_forbidden_formal_keys(payload: Any) -> None:
    if isinstance(payload, dict):
        bad = FORBIDDEN_FORMAL_KEYS.intersection(payload.keys())
        if bad:
            raise ValueError(f"Formal chain graph artifact contains forbidden fields: {sorted(bad)}")
        for value in payload.values():
            assert_no_forbidden_formal_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_forbidden_formal_keys(item)
