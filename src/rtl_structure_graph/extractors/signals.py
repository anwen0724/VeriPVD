from __future__ import annotations

import re
from dataclasses import dataclass, field

from rtl_structure_graph.extractors.modules import ModuleDef
from rtl_structure_graph.models import SourceLoc


DECL_KEYWORDS = {
    "bit",
    "input",
    "inout",
    "integer",
    "logic",
    "output",
    "reg",
    "signed",
    "wire",
}


@dataclass(frozen=True)
class SignalDef:
    name: str
    loc: SourceLoc
    attrs: dict[str, object] = field(default_factory=dict)


def extract_signals(module: ModuleDef) -> list[SignalDef]:
    signals: dict[str, SignalDef] = {}
    for decl_text, line in _header_port_decls(module):
        _add_decl_signals(signals, module, decl_text, line, default_kind="port")
    for match in re.finditer(r"(?m)^\s*(input|output|inout|wire|logic|reg)\b(.*?);", module.body_text):
        decl_text = match.group(0)
        kind = "port" if match.group(1) in {"input", "output", "inout"} else "internal"
        if match.group(1) == "reg":
            kind = "register"
        line = module.source.line_for_offset(module.body_start_offset + match.start())
        _add_decl_signals(signals, module, decl_text, line, default_kind=kind)
    return list(signals.values())


def _header_port_decls(module: ModuleDef) -> list[tuple[str, int]]:
    port_text = _between_first_parens(module.header_text)
    if not port_text:
        return []
    decls: list[tuple[str, int]] = []
    current_direction = None
    for part in _split_top_level_commas(port_text):
        stripped = part.strip()
        direction_match = re.search(r"\b(input|output|inout)\b", stripped)
        if direction_match:
            current_direction = direction_match.group(1)
        elif current_direction:
            stripped = f"{current_direction} {stripped}"
        if current_direction and stripped:
            line = module.loc.line_start + module.header_text.count("\n", 0, module.header_text.find(part))
            decls.append((stripped, line))
    return decls


def _add_decl_signals(
    signals: dict[str, SignalDef],
    module: ModuleDef,
    decl_text: str,
    line: int,
    default_kind: str,
) -> None:
    direction_match = re.search(r"\b(input|output|inout)\b", decl_text)
    base_type_match = re.search(r"\b(wire|logic|reg)\b", decl_text)
    kind = default_kind
    if base_type_match and base_type_match.group(1) == "reg":
        kind = "register"
    if direction_match:
        kind = "port"
    names = _decl_names(decl_text)
    for name in names:
        attrs = {
            "kind": kind,
            "decl_raw": " ".join(decl_text.split()),
        }
        if direction_match:
            attrs["direction"] = direction_match.group(1)
        if base_type_match:
            attrs["decl_type"] = base_type_match.group(1)
        signals[name] = SignalDef(
            name=name,
            loc=SourceLoc(file=module.source.relative_path, line_start=line, line_end=line),
            attrs=attrs,
        )


def _decl_names(decl_text: str) -> list[str]:
    text = re.sub(r"//.*", "", decl_text)
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = re.sub(r"=.*?(?=,|;|$)", " ", text)
    identifiers = re.findall(r"\b[A-Za-z_][A-Za-z0-9_$]*\b", text)
    return [item for item in identifiers if item not in DECL_KEYWORDS]


def _between_first_parens(text: str) -> str:
    start = text.find("(")
    if start == -1:
        return ""
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index]
    return ""


def _split_top_level_commas(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    bracket_depth = 0
    paren_depth = 0
    for index, char in enumerate(text):
        if char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(bracket_depth - 1, 0)
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(paren_depth - 1, 0)
        elif char == "," and bracket_depth == 0 and paren_depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts
