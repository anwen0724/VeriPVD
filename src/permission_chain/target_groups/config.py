from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionTargetGroupConfig:
    schema_version: str = "0.2"
    max_accesses_per_candidate: int = 24
    max_source_locs_per_candidate: int = 32
    max_equivalence_objects_per_group: int = 6
    snippet_context_lines: int = 1
    max_source_chars_per_group: int = 12_000
    max_neighborhood_edges_per_group: int = 120
