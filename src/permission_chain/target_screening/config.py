from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionTargetScreeningConfig:
    schema_version: str = "0.2"
    max_groups_per_batch: int = 6
    max_input_chars_per_batch: int = 60_000
    max_source_chars_per_group: int = 8_000
    max_source_snippets_per_group: int = 12
    max_neighborhood_nodes_per_group: int = 24
    max_neighborhood_edges_per_group: int = 24
    max_accesses_per_member: int = 8
    max_evidence_items_per_group: int = 8
    max_ids_per_evidence_item: int = 8
    max_llm_attempts: int = 2
