from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionTargetConfig:
    max_targets_per_repo: int = 160
    max_targets_per_module: int = 80
    max_accesses_per_target: int = 12
    max_source_locs_per_target: int = 16
    deduplicate_similar_targets: bool = True
