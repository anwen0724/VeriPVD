from __future__ import annotations

from dataclasses import dataclass

from .graph_index import RtlGraphIndex


@dataclass(frozen=True)
class Evidence:
    present: bool
    mode: str


class EvidenceAnalyzer:
    def __init__(self, index: RtlGraphIndex):
        self.index = index

    def is_register(self, signal_id: str) -> Evidence:
        node = self.index.maybe_node(signal_id)
        if not node:
            return Evidence(False, "unavailable")
        if node.get("attrs", {}).get("kind") == "register":
            return Evidence(True, "explicit")
        if self.is_state_update_target(signal_id).present:
            return Evidence(True, "inferred")
        return Evidence(False, "unavailable")

    def is_state_update_target(self, signal_id: str) -> Evidence:
        for stmt in self.index.signal_written_by(signal_id):
            if self._stmt_kind(stmt) == "state_update":
                return Evidence(True, "explicit")
        return Evidence(False, "unavailable")

    def is_condition_used(self, signal_id: str) -> Evidence:
        for edge in self.index.incoming_edges(signal_id, "reads"):
            role = str(edge.get("attrs", {}).get("read_role", "")).lower()
            stmt = self.index.maybe_node(edge.get("from", ""))
            kind = self._stmt_kind(stmt) if stmt else ""
            if role in {"condition", "case_selector"} or kind in {"condition", "case_branch"}:
                return Evidence(True, "explicit")
        return Evidence(False, "unavailable")

    def is_output_port(self, signal_id: str) -> Evidence:
        node = self.index.maybe_node(signal_id)
        if not node:
            return Evidence(False, "unavailable")
        if node.get("attrs", {}).get("direction") == "output":
            return Evidence(True, "explicit")
        return Evidence(False, "unavailable")

    def is_port(self, signal_id: str) -> Evidence:
        node = self.index.maybe_node(signal_id)
        if not node:
            return Evidence(False, "unavailable")
        attrs = node.get("attrs", {})
        if attrs.get("kind") == "port" or attrs.get("direction") in {"input", "output", "inout"}:
            return Evidence(True, "explicit")
        return Evidence(False, "unavailable")

    def is_cross_module_connected(self, signal_id: str) -> Evidence:
        if self.index.signal_connected_to(signal_id):
            return Evidence(True, "explicit")
        return Evidence(False, "unavailable")

    def has_read_or_write(self, signal_id: str) -> Evidence:
        if self.index.signal_written_by(signal_id) or self.index.signal_read_by(signal_id):
            return Evidence(True, "explicit")
        return Evidence(False, "unavailable")

    def is_reset_related(self, signal_id: str) -> Evidence:
        node = self.index.maybe_node(signal_id)
        if not node:
            return Evidence(False, "unavailable")
        text = f"{node.get('name', '')} {self.index.module_name_for_signal(signal_id)} {node.get('loc', {}).get('file', '')}".lower()
        if not any(word in text for word in ("reset", "rst", "clear", "init", "default")):
            return Evidence(False, "unavailable")
        security_words = (
            "lock",
            "auth",
            "debug",
            "key",
            "secret",
            "valid",
            "state",
            "mode",
            "access",
            "cfg",
            "priv",
            "reglk",
            "acct",
            "rsa",
            "aes",
            "hmac",
            "sha",
            "crypto",
            "rng",
            "fuse",
        )
        if any(word in text for word in security_words):
            return Evidence(True, "inferred")
        if self._is_reset_controller_context(text):
            return Evidence(True, "inferred")
        return Evidence(False, "unavailable")

    def _stmt_kind(self, stmt: dict | None) -> str:
        if not stmt:
            return ""
        return str(stmt.get("attrs", {}).get("kind") or stmt.get("name", "").split(":", 1)[0])

    def _is_reset_controller_context(self, text: str) -> bool:
        return any(word in text for word in ("rst_wrapper", "rst_ctrl", "reset_controller", "reset_ctrl"))
