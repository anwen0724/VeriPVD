from __future__ import annotations

from .config import PermissionTargetConfig
from .evidence import EvidenceAnalyzer
from .graph_index import RtlGraphIndex
from .schema import TargetAccess


def collect_accesses(index: RtlGraphIndex, signal_id: str, config: PermissionTargetConfig) -> list[TargetAccess]:
    accesses: list[TargetAccess] = []
    evidence = EvidenceAnalyzer(index)

    for edge in index.incoming_edges(signal_id, "writes"):
        stmt = index.maybe_node(edge.get("from", ""))
        if not stmt:
            continue
        roles = ["register_write"]
        if _stmt_kind(stmt) == "state_update":
            roles.insert(0, "state_update")
        accesses.append(TargetAccess(node_id=stmt["id"], kind=_stmt_kind(stmt), type="write", access_roles=roles))

    for edge in index.incoming_edges(signal_id, "reads"):
        stmt = index.maybe_node(edge.get("from", ""))
        if not stmt:
            continue
        role = str(edge.get("attrs", {}).get("read_role", "")).lower()
        kind = _stmt_kind(stmt)
        if role == "case_selector" or kind == "case_branch":
            accesses.append(TargetAccess(node_id=stmt["id"], kind=kind, type="control", access_roles=["case_use"]))
        elif role == "condition" or kind == "condition":
            accesses.append(TargetAccess(node_id=stmt["id"], kind=kind, type="control", access_roles=["condition_use"]))
        else:
            accesses.append(TargetAccess(node_id=stmt["id"], kind=kind, type="read", access_roles=["register_read"]))

    if evidence.is_output_port(signal_id).present:
        node = index.node(signal_id)
        accesses.append(TargetAccess(node_id=signal_id, kind="output_port", type="output", access_roles=["output_drive"]))

    for connected in index.signal_connected_to(signal_id):
        accesses.append(
            TargetAccess(
                node_id=connected["id"],
                kind="connects",
                type="control",
                access_roles=["cross_module_connect"],
            )
        )

    return _dedupe_accesses(accesses)[: config.max_accesses_per_target]


def _stmt_kind(stmt: dict) -> str:
    return str(stmt.get("attrs", {}).get("kind") or stmt.get("name", "").split(":", 1)[0])


def _dedupe_accesses(accesses: list[TargetAccess]) -> list[TargetAccess]:
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    result: list[TargetAccess] = []
    for access in accesses:
        key = (access.node_id, access.type, tuple(access.access_roles))
        if key in seen:
            continue
        seen.add(key)
        result.append(access)
    return result
