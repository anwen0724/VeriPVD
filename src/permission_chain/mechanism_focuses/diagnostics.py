from __future__ import annotations

from typing import Any


def build_focus_diagnostics(graph_id: str, groups: list[dict[str, Any]], rows: list[dict[str, Any]], focus_count: int) -> dict[str, Any]:
    distribution: dict[str, int] = {}
    by_group = {str(row.get("target_group_id", "")): row for row in rows}
    for group in groups:
        group_id = str(group.get("target_group_id", ""))
        row = by_group.get(group_id, {})
        count = int(row.get("focus_count", 1))
        distribution[str(count)] = distribution.get(str(count), 0) + 1
    return {
        "graph_id": graph_id,
        "target_group_count": len(groups),
        "focus_count": focus_count,
        "split_target_group_count": sum(row.get("decision") == "split" for row in rows),
        "fallback_target_group_count": sum(row.get("decision") == "fallback" for row in rows),
        "focus_count_distribution": dict(sorted(distribution.items(), key=lambda item: int(item[0]))),
        "per_group": rows,
    }
