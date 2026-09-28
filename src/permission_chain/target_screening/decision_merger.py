from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


RETENTION_POLICY = "exclude_non_permission_keep_relevant_or_uncertain_v1"


def merge_screening_decisions(
    groups_doc: dict[str, Any],
    raw_decisions: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    decisions_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for decision in raw_decisions:
        decisions_by_id[str(decision.get("target_group_id", ""))].append(decision)
    normalized = []
    retained = []
    fallback_count = 0
    excluded_count = 0
    classification_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    expected_ids = {str(group.get("target_group_id", "")) for group in groups_doc.get("groups", []) or []}
    unexpected_ids = sorted(set(decisions_by_id) - expected_ids)

    for group in groups_doc.get("groups", []) or []:
        group_id = str(group.get("target_group_id", ""))
        supplied = decisions_by_id.get(group_id, [])
        if len(supplied) != 1:
            fallback_count += 1
            reason = "missing_llm_decision" if not supplied else "duplicate_llm_decision"
            decision = {
                "target_group_id": group_id,
                "classification": "uncertain",
                "confidence": "low",
                "reason": reason,
                "decision_source": "conservative_fallback",
                "retained": True,
            }
        else:
            decision = dict(supplied[0])
            decision["decision_source"] = "llm"
            decision["retained"] = decision.get("classification") != "non_permission"
        normalized.append(decision)
        classification_counts[str(decision["classification"])] += 1
        confidence_counts[str(decision["confidence"])] += 1
        if decision["retained"]:
            retained.append(group)
        else:
            excluded_count += 1

    screening_doc = {
        "graph_id": groups_doc.get("graph_id", ""),
        "schema_version": "0.2",
        "retention_policy": RETENTION_POLICY,
        "decisions": normalized,
    }
    retained_doc = {
        "graph_id": groups_doc.get("graph_id", ""),
        "schema_version": groups_doc.get("schema_version", "0.2"),
        "generation_mode": "algorithm_plus_llm_screening",
        "retention_policy": RETENTION_POLICY,
        "groups": retained,
    }
    diagnostics = {
        "input_group_count": len(groups_doc.get("groups", []) or []),
        "raw_decision_count": len(raw_decisions),
        "retained_group_count": len(retained),
        "excluded_group_count": excluded_count,
        "fallback_group_count": fallback_count,
        "unexpected_target_group_ids": unexpected_ids,
        "classification_distribution": dict(sorted(classification_counts.items())),
        "confidence_distribution": dict(sorted(confidence_counts.items())),
        "retention_policy": RETENTION_POLICY,
    }
    return screening_doc, retained_doc, diagnostics
