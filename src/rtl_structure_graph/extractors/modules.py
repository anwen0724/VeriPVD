from __future__ import annotations

import re
from dataclasses import dataclass

from rtl_structure_graph.models import SourceLoc
from rtl_structure_graph.scanner import RtlSource


MODULE_RE = re.compile(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b")


@dataclass(frozen=True)
class ModuleDef:
    name: str
    source: RtlSource
    loc: SourceLoc
    start_offset: int
    end_offset: int
    header_text: str
    body_text: str
    body_start_offset: int


def strip_comments_preserve_lines(text: str) -> str:
    result: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith("//", i):
            while i < len(text) and text[i] != "\n":
                result.append(" ")
                i += 1
            continue
        if text.startswith("/*", i):
            result.extend("  ")
            i += 2
            while i < len(text) and not text.startswith("*/", i):
                result.append("\n" if text[i] == "\n" else " ")
                i += 1
            if i < len(text):
                result.extend("  ")
                i += 2
            continue
        result.append(text[i])
        i += 1
    return "".join(result)


def extract_modules(source: RtlSource) -> list[ModuleDef]:
    clean = strip_comments_preserve_lines(source.text)
    modules: list[ModuleDef] = []
    for match in MODULE_RE.finditer(clean):
        name = match.group(1)
        end_match = re.search(r"\bendmodule\b", clean[match.end() :])
        if not end_match:
            continue
        end_start = match.end() + end_match.start()
        end_offset = match.end() + end_match.end()
        header_end = clean.find(";", match.end(), end_start)
        if header_end == -1:
            header_end = match.end()
        header_text = clean[match.start() : header_end + 1]
        body_start = header_end + 1
        body_text = clean[body_start:end_start]
        modules.append(
            ModuleDef(
                name=name,
                source=source,
                loc=SourceLoc(
                    file=source.relative_path,
                    line_start=source.line_for_offset(match.start()),
                    line_end=source.line_for_offset(end_offset),
                ),
                start_offset=match.start(),
                end_offset=end_offset,
                header_text=header_text,
                body_text=body_text,
                body_start_offset=body_start,
            )
        )
    return modules
