from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import ChainTargetRef


def load_targets(path: str | Path) -> tuple[str, list[dict[str, Any]]]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if "focuses" in doc:
        return str(doc.get("graph_id", "")), list(doc.get("focuses", []))
    if "groups" in doc:
        return str(doc.get("graph_id", "")), list(doc.get("groups", []))
    return str(doc.get("graph_id", "")), list(doc.get("targets", []))


def target_ref(target: dict[str, Any]) -> ChainTargetRef:
    point = target.get("point") or {}
    return ChainTargetRef(
        target_id=str(target.get("target_id", "")),
        node_id=str(point.get("node_id", "")),
        name=str(point.get("name", "")),
        module=str(point.get("module", "")),
    )


def target_refs(target_or_group: dict[str, Any]) -> list[ChainTargetRef]:
    members = target_or_group.get("members")
    if isinstance(members, list):
        return [target_ref(member) for member in members]
    return [target_ref(target_or_group)]


def seed_node_ids(target: dict[str, Any], include_access_nodes: bool = True) -> list[str]:
    members = target.get("members")
    if isinstance(members, list):
        result: list[str] = []
        for member in members:
            member_access_nodes = include_access_nodes and "focus_id" not in target
            for node_id in seed_node_ids(member, member_access_nodes):
                if node_id not in result:
                    result.append(node_id)
        for node_id in target.get("focus_statement_ids", []) or []:
            if node_id and str(node_id) not in result:
                result.append(str(node_id))
        for node_id in target.get("equivalence_node_ids", []) or []:
            if node_id and str(node_id) not in result:
                result.append(str(node_id))
        for evidence in target.get("equivalence_evidence", []) or []:
            for node_id in evidence.get("node_ids", []) or []:
                if node_id and str(node_id) not in result:
                    result.append(str(node_id))
            for statement_id in evidence.get("statement_ids", []) or []:
                if statement_id and str(statement_id) not in result:
                    result.append(str(statement_id))
        return result
    result: list[str] = []
    point = target.get("point") or {}
    if point.get("node_id"):
        result.append(str(point["node_id"]))
    if include_access_nodes:
        for access in target.get("accesses", []) or []:
            node_id = access.get("node_id")
            if node_id and str(node_id) not in result:
                result.append(str(node_id))
    return result


def seed_record_id(target_or_group: dict[str, Any]) -> str:
    return str(
        target_or_group.get("focus_id")
        or target_or_group.get("target_group_id")
        or target_or_group.get("target_id")
        or ""
    )


def is_mechanism_focus(target_or_group: dict[str, Any]) -> bool:
    return bool(target_or_group.get("focus_id") and isinstance(target_or_group.get("members"), list))


def focus_member_node_ids(focus: dict[str, Any]) -> set[str]:
    return {
        str(member.get("point", {}).get("node_id", ""))
        for member in focus.get("members", []) or []
        if member.get("point", {}).get("node_id")
    }


def shared_focus_node_ids(focus: dict[str, Any]) -> set[str]:
    shared_ids = {str(item) for item in focus.get("shared_member_target_ids", []) or []}
    return {
        str(member.get("point", {}).get("node_id", ""))
        for member in focus.get("members", []) or []
        if str(member.get("target_id", "")) in shared_ids and member.get("point", {}).get("node_id")
    }
