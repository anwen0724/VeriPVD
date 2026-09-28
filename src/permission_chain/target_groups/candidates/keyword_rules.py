from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuleMatch:
    rule_id: str
    roles: tuple[str, ...]


RULES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "R1": (
        ("debug", "dbg", "jtag", "dmi", "tap", "test", "scan", "sba", "halt", "resume", "auth", "password", "pass", "unlock"),
        ("auth_state", "debug_interface", "external_access", "test_access"),
    ),
    "R2": (
        ("lock", "locked", "reglk", "lck", "sticky", "write_once", "protect", "protected", "wr_protect"),
        ("lock_state", "write_protection"),
    ),
    "R3": (
        ("reset", "rst", "clear", "init", "default"),
        ("lifecycle_state", "reset_sensitive_state", "state_residue_risk"),
    ),
    "R4": (
        (
            "csr",
            "regfile",
            "mmio",
            "apb",
            "axi",
            "ahb",
            "cfg",
            "config",
            "ctrl",
            "control",
            "status",
            "mask",
            "pending",
            "clint",
            "plic",
            "uart",
            "gpio",
            "rom",
            "bootrom",
        ),
        ("csr_register", "mmio_register", "peripheral_register", "register_interface", "resource_like"),
    ),
    "R5": (
        ("key", "secret", "fuse", "aes", "hmac", "sha", "rsa", "crypto", "rng", "random", "plaintext", "ciphertext", "hash", "digest"),
        ("crypto_state", "fuse_data", "protected_data", "secret_state"),
    ),
    "R6": (
        ("addr_hit", "region_match", "range", "decode", "grant", "allow", "deny", "access_allowed", "slave_sel", "bridge", "fabric", "interconnect"),
        ("address_decode", "bus_bridge", "fabric_access", "protected_range"),
    ),
    "R7": (
        ("dma", "pmp", "bounds", "bound", "len", "length", "range_check", "pmp_check", "permit", "start", "end"),
        ("bounds_check", "dma_control", "pmp_check", "transaction_permission"),
    ),
    "R8": (
        ("wrapper", "bridge", "adapter", "top", "peripheral", "reglk", "acct", "lock", "auth", "debug", "access", "allow", "grant", "protect", "secure", "priv", "key", "fuse"),
        ("connection_mediation", "cross_module_control", "wrapper_mediation"),
    ),
    "R9": (
        ("priv", "privilege", "mode", "user", "supervisor", "machine", "secure", "nonsecure", "mstatus", "satp", "tvm"),
        ("mode_control", "privilege_state", "secure_state"),
    ),
}


def normalized_text(*parts: object) -> str:
    return " ".join(str(part or "").lower() for part in parts)


def match_rules(text: str) -> list[RuleMatch]:
    lowered = text.lower()
    matches: list[RuleMatch] = []
    for rule_id, (keywords, roles) in RULES.items():
        if any(keyword in lowered for keyword in keywords):
            matches.append(RuleMatch(rule_id=rule_id, roles=roles))
    return matches
