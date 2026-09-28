from __future__ import annotations

import re
from dataclasses import dataclass


IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)*")

KEYWORDS = {
    "always",
    "always_comb",
    "always_ff",
    "assign",
    "begin",
    "case",
    "default",
    "else",
    "end",
    "endcase",
    "if",
    "inout",
    "input",
    "logic",
    "negedge",
    "or",
    "output",
    "posedge",
    "reg",
    "wire",
}


@dataclass(frozen=True)
class SignalRef:
    base_signal: str
    raw: str
    selectors: list[str]


def extract_signal_refs(expr: str) -> list[SignalRef]:
    refs: list[SignalRef] = []
    seen: set[str] = set()
    for match in IDENT_RE.finditer(expr or ""):
        raw = match.group(0)
        if match.start() > 0 and expr[match.start() - 1] == "'":
            continue
        base = raw.split(".", 1)[0]
        if base in KEYWORDS or base in seen:
            continue
        selectors = re.findall(r"\[[^\]]+\]|\.[A-Za-z_][A-Za-z0-9_$]*", raw)
        refs.append(SignalRef(base_signal=base, raw=raw, selectors=selectors))
        seen.add(base)
    return refs
