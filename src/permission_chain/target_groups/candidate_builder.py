from __future__ import annotations

from typing import Any

from .candidates.access_collector import collect_accesses
from .candidates.config import PermissionTargetConfig
from .candidates.point_selector import select_candidate_points
from .candidates.target_builder import make_target

from .config import PermissionTargetGroupConfig
from .graph_index import TargetGroupGraphIndex


def build_untrimmed_candidates(
    index: TargetGroupGraphIndex,
    config: PermissionTargetGroupConfig,
) -> list[dict[str, Any]]:
    target_config = PermissionTargetConfig(
        max_targets_per_repo=10**9,
        max_targets_per_module=10**9,
        max_accesses_per_target=config.max_accesses_per_candidate,
        max_source_locs_per_target=config.max_source_locs_per_candidate,
        deduplicate_similar_targets=False,
    )
    candidates: list[dict[str, Any]] = []
    for sequence, point in enumerate(select_candidate_points(index), start=1):
        accesses = collect_accesses(index, point.node_id, target_config)
        target = make_target(index, point, accesses, sequence, target_config).to_json_dict()
        target["matched_rule_ids"] = list(point.matched_rules)
        target["structural_evidence"] = sorted(point.evidence_modes)
        candidates.append(target)
    return candidates
