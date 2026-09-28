from __future__ import annotations

import copy
import json
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from permission_chain.target_screening.config import PermissionTargetScreeningConfig



SYSTEM_TASK = """You are screening grouped SystemVerilog RTL objects before permission-vulnerability analysis.

For each target group, decide only whether its supplied local RTL structure and code make it worth following as a permission-related security check target.

Labels:
- permission_relevant: the group represents or directly participates in authorization, privilege, lock/protection, debug/test access, access mediation, security-sensitive lifecycle/reset control, or a protected security asset.
- uncertain: the supplied local evidence is insufficient, ambiguous, or could become permission-relevant through context not shown.
- non_permission: the group is ordinary functional logic with no meaningful permission-security role in the supplied evidence.

Important boundaries:
- Do not decide whether a vulnerability exists.
- Do not judge whether protection is sufficient.
- Do not invent missing paths or code.
- Grouping is structural. Members can be related without being semantically identical.
- Use uncertain whenever exclusion is not strongly supported.
- Return one decision for every target_group_id exactly once.

Input fields:
- members: rule-selected RTL candidates. point_roles and matched_rule_ids are rule hints, not ground truth.
- equivalence_evidence: graph facts proving alias-like, no-transformation structural equivalence.
- related_evidence: graph facts showing members share local access/control structure without claiming equivalence.
- neighborhood: one-hop reads, writes, and connects facts around members.
- source_snippets: deterministic local code excerpts for declarations, direct accesses, assignments, and bindings.

Return only JSON with this schema:
{
  "decisions": [
    {
      "target_group_id": "TG-0001",
      "classification": "permission_relevant | uncertain | non_permission",
      "confidence": "high | medium | low",
      "reason": "brief evidence-based reason"
    }
  ]
}
"""


def build_screening_prompt(groups: list[dict[str, Any]]) -> str:
    return SYSTEM_TASK + "\nTarget groups:\n" + json.dumps(groups, ensure_ascii=False, separators=(",", ":"))


def compact_group_context(group: dict[str, Any], config: PermissionTargetScreeningConfig) -> dict[str, Any]:
    compact = copy.deepcopy(group)
    compact["members"] = [_compact_member(member, config) for member in compact.get("members", []) or []]
    compact["equivalence_evidence"] = [
        _compact_evidence(item, config)
        for item in (compact.get("equivalence_evidence", []) or [])[: config.max_evidence_items_per_group]
    ]
    compact["related_evidence"] = [
        _compact_evidence(item, config)
        for item in (compact.get("related_evidence", []) or [])[: config.max_evidence_items_per_group]
    ]
    neighborhood = compact.get("neighborhood") or {}
    neighborhood["nodes"] = [
        _compact_node(node)
        for node in list(neighborhood.get("nodes", []))[: config.max_neighborhood_nodes_per_group]
    ]
    neighborhood["edges"] = [
        _compact_edge(edge)
        for edge in list(neighborhood.get("edges", []))[: config.max_neighborhood_edges_per_group]
    ]
    compact["neighborhood"] = neighborhood
    point_ids = {
        str(member.get("point", {}).get("node_id", ""))
        for member in compact.get("members", [])
        if member.get("point", {}).get("node_id")
    }
    access_ids = {
        str(access.get("node_id", ""))
        for member in compact.get("members", [])
        for access in member.get("accesses", [])
        if access.get("node_id")
    }
    ranked_snippets = sorted(
        compact.get("source_snippets", []) or [],
        key=lambda item: _snippet_sort_key(item, point_ids, access_ids),
    )[: config.max_source_snippets_per_group]
    remaining = config.max_source_chars_per_group
    snippets = []
    for snippet in ranked_snippets:
        if remaining <= 0:
            break
        item = _compact_snippet(snippet, remaining, config.max_ids_per_evidence_item)
        code = str(item.get("code", ""))
        snippets.append(item)
        remaining -= len(code)
    compact["source_snippets"] = snippets
    return compact


def make_batches(
    groups: list[dict[str, Any]],
    config: PermissionTargetScreeningConfig,
) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for group in sorted(groups, key=lambda item: str(item.get("target_group_id", ""))):
        compact = compact_group_context(group, config)
        single_size = len(build_screening_prompt([compact]))
        if single_size > config.max_input_chars_per_batch:
            raise ValueError(
                f"Compacted target group {compact.get('target_group_id')} exceeds prompt budget: "
                f"{single_size} > {config.max_input_chars_per_batch}"
            )
        if current and (
            len(current) >= config.max_groups_per_batch
            or len(build_screening_prompt([*current, compact])) > config.max_input_chars_per_batch
        ):
            batches.append(current)
            current = []
        current.append(compact)
    if current:
        batches.append(current)
    return batches


def _compact_edge(edge: dict[str, Any]) -> dict[str, Any]:
    attrs = edge.get("attrs") or {}
    allowed_attrs = {
        key: _bounded_attr(attrs[key])
        for key in (
            "actual_expr",
            "actual_base_signal",
            "formal_port",
            "formal_port_direction",
            "direction",
            "read_role",
            "lhs_raw",
            "raw_expr",
        )
        if key in attrs
    }
    return {
        "edge_id": edge.get("edge_id"),
        "kind": edge.get("kind"),
        "src": edge.get("src"),
        "dst": edge.get("dst"),
        "attrs": allowed_attrs,
    }


def _bounded_attr(value: Any, max_chars: int = 500) -> Any:
    if isinstance(value, str):
        return value[:max_chars]
    if isinstance(value, list):
        return [_bounded_attr(item, max_chars) for item in value[:16]]
    return value


def _compact_snippet(snippet: dict[str, Any], code_budget: int, id_limit: int) -> dict[str, Any]:
    result = {
        key: snippet.get(key)
        for key in ("snippet_id", "file", "line_start", "line_end")
        if snippet.get(key) not in (None, "")
    }
    for key in ("node_ids", "edge_ids", "statement_ids"):
        values = list(snippet.get(key, []) or [])[:id_limit]
        if values:
            result[key] = values
    result["code"] = str(snippet.get("code", ""))[:code_budget]
    return result


def _snippet_sort_key(
    snippet: dict[str, Any],
    point_ids: set[str],
    access_ids: set[str],
) -> tuple[int, str, int, str]:
    refs = {
        str(value)
        for key in ("node_ids", "statement_ids")
        for value in (snippet.get(key, []) or [])
    }
    if refs.intersection(point_ids):
        priority = 0
    elif refs.intersection(access_ids):
        priority = 1
    else:
        priority = 2
    return (
        priority,
        str(snippet.get("file", "")),
        int(snippet.get("line_start", 0) or 0),
        str(snippet.get("snippet_id", "")),
    )


def _compact_member(member: dict[str, Any], config: PermissionTargetScreeningConfig) -> dict[str, Any]:
    accesses = _select_representative_accesses(
        member.get("accesses", []) or [],
        config.max_accesses_per_member,
    )
    return {
        "target_id": member.get("target_id"),
        "point": member.get("point") or {},
        "accesses": [_compact_access(item) for item in accesses],
        "matched_rule_ids": list(member.get("matched_rule_ids", []) or []),
        "structural_evidence": list(member.get("structural_evidence", []) or []),
    }


def _compact_access(access: dict[str, Any]) -> dict[str, Any]:
    return {
        key: access.get(key)
        for key in ("node_id", "kind", "type", "access_roles")
        if access.get(key) not in (None, [], "")
    }


def _access_sort_key(access: dict[str, Any]) -> tuple[int, str, str]:
    kind = str(access.get("kind", ""))
    priority = {
        "writes": 0,
        "procedural_assign": 0,
        "state_update": 0,
        "connects": 1,
        "reads": 2,
    }.get(kind, 3)
    return (priority, kind, str(access.get("node_id", "")))


def _select_representative_accesses(accesses: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    ordered = sorted(accesses, key=_access_sort_key)
    selected: list[dict[str, Any]] = []
    seen_shapes: set[tuple[str, str, tuple[str, ...]]] = set()
    for access in ordered:
        shape = (
            str(access.get("kind", "")),
            str(access.get("type", "")),
            tuple(sorted(str(role) for role in (access.get("access_roles", []) or []))),
        )
        if shape in seen_shapes:
            continue
        selected.append(access)
        seen_shapes.add(shape)
        if len(selected) >= limit:
            return selected
    selected_ids = {id(item) for item in selected}
    for access in ordered:
        if id(access) in selected_ids:
            continue
        selected.append(access)
        if len(selected) >= limit:
            break
    return selected


def _compact_evidence(item: dict[str, Any], config: PermissionTargetScreeningConfig) -> dict[str, Any]:
    limit = config.max_ids_per_evidence_item
    result = {"kind": item.get("kind")}
    for key in ("node_ids", "edge_ids", "statement_ids", "member_target_ids"):
        values = list(item.get(key, []) or [])[:limit]
        if values:
            result[key] = values
    return result


def _compact_node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        key: node.get(key)
        for key in ("node_id", "kind", "name", "module", "loc")
        if node.get(key) not in (None, {}, "")
    }
