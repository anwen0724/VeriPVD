from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TargetPoint:
    node_id: str
    name: str
    module: str
    point_roles: list[str]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "module": self.module,
            "point_roles": list(self.point_roles),
        }


@dataclass(frozen=True)
class TargetAccess:
    node_id: str
    kind: str
    type: str
    access_roles: list[str]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "type": self.type,
            "access_roles": list(self.access_roles),
        }


@dataclass(frozen=True)
class TargetSourceLoc:
    node_id: str
    file: str
    line_start: int
    line_end: int
    role: str

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "file": self.file,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "role": self.role,
        }


@dataclass(frozen=True)
class PermissionCheckTarget:
    target_id: str
    point: TargetPoint
    accesses: list[TargetAccess] = field(default_factory=list)
    source_locs: list[TargetSourceLoc] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "point": self.point.to_json_dict(),
            "accesses": [access.to_json_dict() for access in self.accesses],
            "source_locs": [loc.to_json_dict() for loc in self.source_locs],
        }


@dataclass(frozen=True)
class PermissionCheckTargets:
    graph_id: str
    targets: list[PermissionCheckTarget] = field(default_factory=list)
    schema_version: str = "0.1"
    generation_mode: str = "algorithm"

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "schema_version": self.schema_version,
            "generation_mode": self.generation_mode,
            "targets": [target.to_json_dict() for target in self.targets],
        }


@dataclass
class TargetGenerationDiagnostics:
    graph_id: str
    candidate_point_count: int = 0
    target_count_before_dedup: int = 0
    target_count_after_dedup: int = 0
    target_count_final: int = 0
    point_roles_distribution: dict[str, int] = field(default_factory=dict)
    access_roles_distribution: dict[str, int] = field(default_factory=dict)
    matched_rules_distribution: dict[str, int] = field(default_factory=dict)
    evidence_mode_distribution: dict[str, int] = field(default_factory=dict)
    targets_trimmed_by_repo_limit: int = 0
    targets_trimmed_by_module_limit: int = 0
    deduplicated_target_count: int = 0
    missing_source_loc_count: int = 0
    reset_branch_explicit: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "candidate_point_count": self.candidate_point_count,
            "target_count_before_dedup": self.target_count_before_dedup,
            "target_count_after_dedup": self.target_count_after_dedup,
            "target_count_final": self.target_count_final,
            "point_roles_distribution": dict(sorted(self.point_roles_distribution.items())),
            "access_roles_distribution": dict(sorted(self.access_roles_distribution.items())),
            "matched_rules_distribution": dict(sorted(self.matched_rules_distribution.items())),
            "evidence_mode_distribution": dict(sorted(self.evidence_mode_distribution.items())),
            "targets_trimmed_by_repo_limit": self.targets_trimmed_by_repo_limit,
            "targets_trimmed_by_module_limit": self.targets_trimmed_by_module_limit,
            "deduplicated_target_count": self.deduplicated_target_count,
            "missing_source_loc_count": self.missing_source_loc_count,
            "reset_branch_explicit": self.reset_branch_explicit,
            "warnings": list(self.warnings),
        }
