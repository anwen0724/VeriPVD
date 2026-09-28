from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from permission_chain.target_groups.graph_index import TargetGroupGraphIndex


@dataclass
class StatementObjectAccess:
    statement_id: str
    read_roles: dict[str, set[str]] = field(default_factory=dict)
    writes: set[str] = field(default_factory=set)
    raw_writes: set[str] = field(default_factory=set)
    guard_signature: tuple[str, ...] = ()

    @property
    def touched_objects(self) -> set[str]:
        return set(self.read_roles) | set(self.writes)


class MechanismFocusGraphIndex(TargetGroupGraphIndex):
    def statement_object_access(
        self,
        statement_id: str,
        object_by_signal: dict[str, str],
    ) -> StatementObjectAccess:
        access = StatementObjectAccess(statement_id=statement_id)
        statement = self.maybe_node(statement_id) or {}
        access.guard_signature = tuple(
            sorted(
                f"{item.get('file', '')}:{item.get('line_start', '')}:{item.get('role', '')}"
                for item in (statement.get("attrs") or {}).get("control_locs", []) or []
            )
        )
        for edge in self.outgoing_edges(statement_id):
            signal_id = str(edge.get("to", ""))
            if edge.get("type") == "writes":
                access.raw_writes.add(signal_id)
            object_id = object_by_signal.get(signal_id)
            if not object_id:
                continue
            if edge.get("type") == "writes":
                access.writes.add(object_id)
            elif edge.get("type") == "reads":
                role = str((edge.get("attrs") or {}).get("read_role", "rhs"))
                access.read_roles.setdefault(object_id, set()).add(role)
        return access

    def is_statement(self, node_id: str) -> bool:
        node = self.maybe_node(node_id)
        return bool(node and node.get("type") == "StmtSummary")
