from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .decomposer import decompose_target_group
from .diagnostics import build_focus_diagnostics
from .graph_index import MechanismFocusGraphIndex
from .schema import PermissionMechanismFocus, PermissionMechanismFocuses
from .writer import write_focus_outputs


def build_permission_mechanism_focuses(
    graph_path: str | Path,
    retained_groups_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    groups_doc = json.loads(Path(retained_groups_path).read_text(encoding="utf-8"))
    graph_id = str(graph.get("graph_id", ""))
    groups_graph_id = str(groups_doc.get("graph_id", ""))
    if groups_graph_id and groups_graph_id != graph_id:
        raise ValueError(f"Target group graph_id {groups_graph_id} differs from graph_id {graph_id}")
    groups = list(groups_doc.get("groups", []) or [])
    index = MechanismFocusGraphIndex.from_json_dict(graph)
    focuses: list[PermissionMechanismFocus] = []
    rows: list[dict[str, Any]] = []
    for group in sorted(groups, key=lambda item: str(item.get("target_group_id", ""))):
        members_by_id = {str(member.get("target_id", "")): member for member in group.get("members", []) or []}
        partitions, row = decompose_target_group(group, index)
        for partition in partitions:
            focuses.append(
                PermissionMechanismFocus(
                    focus_id=f"FOCUS-{len(focuses)+1:04d}",
                    source_target_group_id=str(group.get("target_group_id", "")),
                    members=[members_by_id[target_id] for target_id in partition.member_target_ids],
                    focus_statement_ids=list(partition.statement_ids),
                    equivalence_node_ids=list(partition.equivalence_node_ids),
                    shared_member_target_ids=list(partition.shared_member_target_ids),
                )
            )
        row["focus_count"] = len(partitions)
        rows.append(row)
    formal = PermissionMechanismFocuses(graph_id=graph_id, focuses=focuses)
    diagnostics = build_focus_diagnostics(graph_id, groups, rows, len(focuses))
    write_focus_outputs(output_dir, formal, diagnostics)
    return {
        "graph_id": graph_id,
        "target_group_count": len(groups),
        "focus_count": len(focuses),
        "split_target_group_count": diagnostics["split_target_group_count"],
        "output_dir": str(output_dir),
    }
