from __future__ import annotations

from dataclasses import dataclass, field

from .evidence import EvidenceAnalyzer
from .graph_index import RtlGraphIndex
from .keyword_rules import match_rules, normalized_text


@dataclass(frozen=True)
class CandidatePoint:
    node_id: str
    name: str
    module: str
    point_roles: list[str]
    matched_rules: list[str]
    evidence_modes: dict[str, str] = field(default_factory=dict)


PURE_RESET_CLOCK = {"clk", "clock", "rst_n", "reset_n", "rst", "reset"}
WEAK_HANDSHAKE = {"valid", "ready", "done", "busy"}
TEMPORARY_NAMES = {"tmp", "temp", "next", "n", "mux_out"}
PLAIN_DATA = {"data", "rdata", "wdata"}
ACCESS_ONLY_NAMES = {"we", "wen", "wr", "rd", "read", "write", "psel", "sel", "enable", "en"}


def select_candidate_points(index: RtlGraphIndex) -> list[CandidatePoint]:
    evidence = EvidenceAnalyzer(index)
    candidates: list[CandidatePoint] = []
    for signal in index.signal_nodes():
        node_id = signal["id"]
        name = signal.get("name", "")
        module = index.module_name_for_signal(node_id)
        text = normalized_text(name)
        context_text = normalized_text(module, signal.get("loc", {}).get("file", ""))
        if _is_implicit_constant_like(signal):
            continue
        if _is_excluded_name(name, context_text):
            continue
        matches = match_rules(text)
        if _is_crypto_resource_point(name, context_text):
            matches.extend(match for match in match_rules("rsa") if match.rule_id == "R5")
        if _is_reset_controller_control(name, context_text):
            matches.extend(match for match in match_rules("rst") if match.rule_id == "R3")
        if not matches:
            continue

        modes: dict[str, str] = {}
        structural_roles: set[str] = set()
        if evidence.is_register(node_id).present:
            modes["register"] = evidence.is_register(node_id).mode
            structural_roles.add("register")
        if evidence.is_state_update_target(node_id).present:
            modes["state_update_target"] = evidence.is_state_update_target(node_id).mode
            structural_roles.add("state_update_target")
        if evidence.is_output_port(node_id).present:
            modes["output_port"] = evidence.is_output_port(node_id).mode
            structural_roles.add("output_port")
        if evidence.is_condition_used(node_id).present:
            modes["condition_used"] = evidence.is_condition_used(node_id).mode
            structural_roles.add("control_like")
        if evidence.is_cross_module_connected(node_id).present:
            modes["cross_module_connect"] = evidence.is_cross_module_connected(node_id).mode
        if evidence.is_port(node_id).present:
            modes["port"] = evidence.is_port(node_id).mode
        if evidence.has_read_or_write(node_id).present:
            modes["read_or_write"] = evidence.has_read_or_write(node_id).mode
        if evidence.is_reset_related(node_id).present:
            modes["reset_related"] = evidence.is_reset_related(node_id).mode

        if not modes:
            continue
        if _is_weak_without_security_context(name, f"{text} {context_text}"):
            continue

        roles = set(structural_roles)
        rules: list[str] = []
        matched_rule_ids = {match.rule_id for match in matches}
        for match in matches:
            if match.rule_id == "R3" and "reset_related" not in modes:
                continue
            if match.rule_id == "R8" and "cross_module_connect" not in modes:
                continue
            if match.rule_id == "R4" and "R2" in matched_rule_ids:
                continue
            if match.rule_id == "R7" and not _has_dma_pmp_context(text, context_text):
                continue
            rules.append(match.rule_id)
            roles.update(match.roles)
        if not rules:
            continue
        candidates.append(
            CandidatePoint(
                node_id=node_id,
                name=name,
                module=module,
                point_roles=sorted(roles),
                matched_rules=sorted(set(rules)),
                evidence_modes=modes,
            )
        )
    return sorted(candidates, key=lambda point: (point.module, point.name, point.node_id))


def _is_excluded_name(name: str, context_text: str) -> bool:
    lowered = name.lower()
    if _is_crypto_resource_context(context_text) and lowered in PLAIN_DATA:
        return False
    return (
        lowered in PURE_RESET_CLOCK
        or lowered in TEMPORARY_NAMES
        or lowered in PLAIN_DATA
        or lowered in ACCESS_ONLY_NAMES
    )


def _is_weak_without_security_context(name: str, text: str) -> bool:
    lowered = name.lower()
    if lowered not in WEAK_HANDSHAKE:
        return False
    security_words = ("debug", "jtag", "crypto", "dma", "pmp", "lock", "auth", "priv", "key", "fuse", "csr", "mmio")
    return not any(word in text for word in security_words)


def _is_implicit_constant_like(signal: dict) -> bool:
    attrs = signal.get("attrs", {})
    if attrs.get("kind") != "implicit" or attrs.get("decl_raw") is not None:
        return False
    name = str(signal.get("name", ""))
    if name.startswith(("DBG_", "STATE_", "CMD_", "REG_")):
        return True
    letters = [char for char in name if char.isalpha()]
    return bool(letters) and all(char.isupper() for char in letters) and "_" in name


def _has_dma_pmp_context(text: str, context_text: str) -> bool:
    combined = f"{text} {context_text}"
    return any(word in combined for word in ("dma", "pmp", "range_check", "pmp_check", "bounds"))


def _is_reset_controller_control(name: str, context_text: str) -> bool:
    lowered = name.lower()
    reset_context = any(word in context_text for word in ("rst_wrapper", "rst_ctrl", "reset_controller", "reset_ctrl"))
    reset_control_names = {"start", "rst_id", "rst_mem", "reset_id", "reset_mem"}
    return reset_context and (lowered in reset_control_names or lowered.startswith("rst_"))


def _is_crypto_resource_point(name: str, context_text: str) -> bool:
    if not _is_crypto_resource_context(context_text):
        return False
    lowered = name.lower()
    resource_words = (
        "msg",
        "message",
        "rdata",
        "wdata",
        "data",
        "result",
        "out",
        "prime",
        "encry",
        "decry",
        "encrypt",
        "decrypt",
        "cipher",
        "plain",
        "hash",
        "digest",
        "nonce",
        "seed",
    )
    return any(word in lowered for word in resource_words)


def _is_crypto_resource_context(context_text: str) -> bool:
    return any(word in context_text for word in ("rsa", "aes", "hmac", "sha", "crypto", "rng", "fuse"))
