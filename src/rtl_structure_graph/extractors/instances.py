from __future__ import annotations

import re
from dataclasses import dataclass, field

from rtl_structure_graph.extractors.modules import ModuleDef
from rtl_structure_graph.models import SourceLoc


INSTANCE_RE = re.compile(
    r"(?ms)^\s*(?P<module_type>[A-Za-z_][A-Za-z0-9_$]*)\s+"
    r"(?:(?P<parameter_text>#\s*\((?:[^()]|\([^()]*\))*\))\s*)?"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\s*\((?P<ports>.*?)\)\s*;"
)

SKIP_TYPES = {
    "always",
    "assign",
    "begin",
    "case",
    "else",
    "end",
    "endcase",
    "endgenerate",
    "for",
    "function",
    "generate",
    "genvar",
    "if",
    "initial",
    "input",
    "logic",
    "output",
    "priority",
    "property",
    "reg",
    "task",
    "unique",
    "wire",
    "assert",
}

SKIP_NAMES = {
    "always",
    "assert",
    "case",
    "for",
    "if",
    "property",
}


@dataclass(frozen=True)
class PortBinding:
    formal_port: str
    actual_expr: str


@dataclass(frozen=True)
class InstanceDef:
    name: str
    module_type: str
    parent_module: str
    loc: SourceLoc
    port_bindings: list[PortBinding] = field(default_factory=list)
    parameter_text: str | None = None


def extract_instances(module: ModuleDef, known_modules: set[str]) -> list[InstanceDef]:
    instances: list[InstanceDef] = []
    for match in INSTANCE_RE.finditer(module.body_text):
        module_type = match.group("module_type")
        instance_name = match.group("name")
        if module_type in SKIP_TYPES or instance_name in SKIP_NAMES:
            continue
        line = module.source.line_for_offset(module.body_start_offset + match.start())
        instances.append(
            InstanceDef(
                name=instance_name,
                module_type=module_type,
                parent_module=module.name,
                loc=SourceLoc(file=module.source.relative_path, line_start=line, line_end=line),
                port_bindings=_parse_port_bindings(match.group("ports")),
                parameter_text=match.group("parameter_text"),
            )
        )
    return instances


def _parse_port_bindings(text: str) -> list[PortBinding]:
    bindings: list[PortBinding] = []
    index = 0
    while index < len(text):
        dot = text.find(".", index)
        if dot == -1:
            break
        name_match = re.match(r"\.([A-Za-z_][A-Za-z0-9_$]*)", text[dot:])
        if not name_match:
            index = dot + 1
            continue
        formal = name_match.group(1)
        cursor = dot + len(name_match.group(0))
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor < len(text) and text[cursor] == "(":
            expr_start = cursor + 1
            depth = 1
            cursor += 1
            while cursor < len(text) and depth:
                if text[cursor] == "(":
                    depth += 1
                elif text[cursor] == ")":
                    depth -= 1
                cursor += 1
            actual = text[expr_start : cursor - 1].strip()
        else:
            actual = formal
        bindings.append(PortBinding(formal_port=formal, actual_expr=actual))
        index = cursor
    return bindings
