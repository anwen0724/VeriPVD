from __future__ import annotations

import re
from dataclasses import dataclass, field

from rtl_structure_graph.extractors.expressions import SignalRef, extract_signal_refs
from rtl_structure_graph.extractors.modules import ModuleDef
from rtl_structure_graph.models import SourceLoc


@dataclass(frozen=True)
class StatementDef:
    kind: str
    loc: SourceLoc
    attrs: dict[str, object] = field(default_factory=dict)
    read_refs: list[tuple[SignalRef, str]] = field(default_factory=list)
    write_refs: list[SignalRef] = field(default_factory=list)


@dataclass(frozen=True)
class _ControlRef:
    expression: str
    role: str
    start: int
    end: int


@dataclass(frozen=True)
class _ScopedAssignment:
    start: int
    end: int
    lhs_raw: str
    op: str
    rhs_raw: str
    controls: tuple[_ControlRef, ...] = ()


def extract_statements(module: ModuleDef) -> list[StatementDef]:
    statements: list[StatementDef] = []
    statements.extend(_extract_continuous_assigns(module))
    statements.extend(_extract_always_assigns(module))
    return statements


def _extract_continuous_assigns(module: ModuleDef) -> list[StatementDef]:
    results: list[StatementDef] = []
    for match in re.finditer(r"(?ms)\bassign\s+(.+?)\s*=\s*(.+?)\s*;", module.body_text):
        lhs_raw = match.group(1).strip()
        rhs_raw = match.group(2).strip()
        line = module.source.line_for_offset(module.body_start_offset + match.start())
        results.append(
            StatementDef(
                kind="continuous_assign",
                loc=SourceLoc(file=module.source.relative_path, line_start=line, line_end=line),
                attrs={
                    "kind": "continuous_assign",
                    "lhs_raw": lhs_raw,
                    "rhs_raw": rhs_raw,
                },
                read_refs=[(ref, "rhs") for ref in extract_signal_refs(rhs_raw)],
                write_refs=extract_signal_refs(lhs_raw),
            )
        )
    return results


def _extract_always_assigns(module: ModuleDef) -> list[StatementDef]:
    results: list[StatementDef] = []
    for block_start, block_end, header, block_text in _iter_always_blocks(module.body_text):
        temporal = "posedge" in header or "negedge" in header or "always_ff" in header
        assignments = _ProceduralParser(block_text, start=len(header)).parse()
        for assignment in assignments:
            lhs_raw = assignment.lhs_raw
            op = assignment.op
            rhs_raw = assignment.rhs_raw
            kind = "state_update" if temporal or op == "<=" else "procedural_assign"
            line = module.source.line_for_offset(module.body_start_offset + block_start + assignment.start)
            line_end = module.source.line_for_offset(module.body_start_offset + block_start + assignment.end)
            read_refs = [(ref, "rhs") for ref in extract_signal_refs(rhs_raw)]
            conditions = [control for control in assignment.controls if control.role == "condition"]
            case_selectors = [control for control in assignment.controls if control.role == "case_selector"]
            for control in assignment.controls:
                read_refs.extend((ref, control.role) for ref in extract_signal_refs(control.expression))
            read_refs = _dedupe_read_refs(read_refs)
            results.append(
                StatementDef(
                    kind=kind,
                    loc=SourceLoc(file=module.source.relative_path, line_start=line, line_end=line_end),
                    attrs={
                        "kind": kind,
                        "assignment_op": op,
                        "lhs_raw": lhs_raw,
                        "rhs_raw": rhs_raw,
                        "conditions": [" ".join(item.expression.split()) for item in conditions],
                        "case_selectors": [" ".join(item.expression.split()) for item in case_selectors],
                        "control_locs": [
                            {
                                "file": module.source.relative_path,
                                "line_start": module.source.line_for_offset(
                                    module.body_start_offset + block_start + control.start
                                ),
                                "line_end": module.source.line_for_offset(
                                    module.body_start_offset + block_start + control.end
                                ),
                                "role": control.role,
                            }
                            for control in assignment.controls
                        ],
                    },
                    read_refs=read_refs,
                    write_refs=extract_signal_refs(lhs_raw),
                )
            )
    return results


class _ProceduralParser:
    def __init__(self, text: str, start: int = 0):
        self.text = text
        self.length = len(text)
        self.start = start
        self.assignments: list[_ScopedAssignment] = []

    def parse(self) -> list[_ScopedAssignment]:
        self._parse_sequence(self.start, (), (), end_keywords=set())
        return sorted(self.assignments, key=lambda item: (item.start, item.end, item.lhs_raw))

    def _parse_sequence(
        self,
        pos: int,
        conditions: tuple[_ControlRef, ...],
        selectors: tuple[_ControlRef, ...],
        end_keywords: set[str],
    ) -> int:
        while pos < self.length:
            pos = self._skip_space(pos)
            keyword = self._keyword_at(pos)
            if keyword in end_keywords:
                return pos
            next_pos = self._parse_statement(pos, conditions, selectors)
            pos = next_pos if next_pos > pos else pos + 1
        return pos

    def _parse_statement(
        self,
        pos: int,
        conditions: tuple[_ControlRef, ...],
        selectors: tuple[_ControlRef, ...],
    ) -> int:
        pos = self._skip_space(pos)
        keyword = self._keyword_at(pos)
        if keyword in {"unique", "unique0", "priority"}:
            return self._parse_statement(self._after_keyword(pos, keyword), conditions, selectors)
        if keyword == "begin":
            body_start = self._after_keyword(pos, keyword)
            body_start = self._skip_optional_block_label(body_start)
            end_pos = self._parse_sequence(body_start, conditions, selectors, {"end"})
            if self._keyword_at(end_pos) == "end":
                end_pos = self._after_keyword(end_pos, "end")
                end_pos = self._skip_optional_block_label(end_pos)
            return end_pos
        if keyword == "if":
            return self._parse_if(pos, conditions, selectors)
        if keyword in {"case", "casex", "casez"}:
            return self._parse_case(pos, keyword, conditions, selectors)
        if keyword in {"for", "while", "repeat", "foreach"}:
            cursor = self._after_keyword(pos, keyword)
            _, _, cursor = self._parenthesized(cursor)
            return self._parse_statement(cursor, conditions, selectors)
        if keyword in {"end", "endcase", "else"}:
            return pos
        return self._parse_simple_statement(pos, conditions + selectors)

    def _parse_if(
        self,
        pos: int,
        conditions: tuple[_ControlRef, ...],
        selectors: tuple[_ControlRef, ...],
    ) -> int:
        cursor = self._after_keyword(pos, "if")
        expression, expr_start, cursor = self._parenthesized(cursor)
        if expression is None:
            return self._parse_simple_statement(pos, conditions + selectors)
        control = _ControlRef(expression, "condition", pos, max(pos, cursor - 1))
        cursor = self._parse_statement(cursor, conditions + (control,), selectors)
        cursor = self._skip_space(cursor)
        if self._keyword_at(cursor) == "else":
            cursor = self._parse_statement(self._after_keyword(cursor, "else"), conditions + (control,), selectors)
        return cursor

    def _parse_case(
        self,
        pos: int,
        keyword: str,
        conditions: tuple[_ControlRef, ...],
        selectors: tuple[_ControlRef, ...],
    ) -> int:
        cursor = self._after_keyword(pos, keyword)
        expression, expr_start, cursor = self._parenthesized(cursor)
        if expression is None:
            return self._parse_simple_statement(pos, conditions + selectors)
        selector = _ControlRef(expression, "case_selector", pos, max(pos, cursor - 1))
        while cursor < self.length:
            cursor = self._skip_space(cursor)
            if self._keyword_at(cursor) == "endcase":
                return self._after_keyword(cursor, "endcase")
            colon = self._find_case_item_colon(cursor)
            if colon < 0:
                return cursor
            cursor = self._parse_statement(colon + 1, conditions, selectors + (selector,))
        return cursor

    def _parse_simple_statement(self, pos: int, controls: tuple[_ControlRef, ...]) -> int:
        end = self._find_statement_end(pos)
        if end < 0:
            end = self.length - 1
        raw = self.text[pos : end + 1]
        match = re.search(
            r"(?ms)([A-Za-z_][A-Za-z0-9_$]*(?:\[[^\]]+\])?)\s*(<=|=(?!=))\s*(.+?)\s*;\s*$",
            raw,
        )
        if match:
            self.assignments.append(
                _ScopedAssignment(
                    start=pos + match.start(),
                    end=pos + match.end() - 1,
                    lhs_raw=match.group(1).strip(),
                    op=match.group(2),
                    rhs_raw=match.group(3).strip(),
                    controls=controls,
                )
            )
        return min(self.length, end + 1)

    def _parenthesized(self, pos: int) -> tuple[str | None, int, int]:
        pos = self._skip_space(pos)
        if pos >= self.length or self.text[pos] != "(":
            return None, pos, pos
        end = self._matching_delimiter(pos, "(", ")")
        if end < 0:
            return None, pos, pos
        return self.text[pos + 1 : end], pos + 1, end + 1

    def _find_case_item_colon(self, pos: int) -> int:
        stack: list[str] = []
        pairs = {")": "(", "]": "[", "}": "{"}
        cursor = pos
        while cursor < self.length:
            keyword = self._keyword_at(cursor)
            if not stack and keyword == "endcase":
                return -1
            char = self.text[cursor]
            if char in "([{":
                stack.append(char)
            elif char in ")]}":
                if stack and stack[-1] == pairs[char]:
                    stack.pop()
            elif char == ":" and not stack:
                return cursor
            cursor += 1
        return -1

    def _find_statement_end(self, pos: int) -> int:
        stack: list[str] = []
        pairs = {")": "(", "]": "[", "}": "{"}
        cursor = pos
        while cursor < self.length:
            char = self.text[cursor]
            if char in "([{":
                stack.append(char)
            elif char in ")]}":
                if stack and stack[-1] == pairs[char]:
                    stack.pop()
            elif char == ";" and not stack:
                return cursor
            cursor += 1
        return -1

    def _matching_delimiter(self, pos: int, opening: str, closing: str) -> int:
        depth = 0
        cursor = pos
        while cursor < self.length:
            char = self.text[cursor]
            if char == opening:
                depth += 1
            elif char == closing:
                depth -= 1
                if depth == 0:
                    return cursor
            cursor += 1
        return -1

    def _skip_space(self, pos: int) -> int:
        while pos < self.length and self.text[pos].isspace():
            pos += 1
        return pos

    def _keyword_at(self, pos: int) -> str:
        match = re.match(r"[A-Za-z_][A-Za-z0-9_$]*", self.text[pos:])
        return match.group(0) if match else ""

    def _after_keyword(self, pos: int, keyword: str) -> int:
        return pos + len(keyword)

    def _skip_optional_block_label(self, pos: int) -> int:
        cursor = self._skip_space(pos)
        if cursor < self.length and self.text[cursor] == ":":
            cursor += 1
            cursor = self._skip_space(cursor)
            match = re.match(r"[A-Za-z_][A-Za-z0-9_$]*", self.text[cursor:])
            if match:
                cursor += len(match.group(0))
        return cursor


def _dedupe_read_refs(items: list[tuple[SignalRef, str]]) -> list[tuple[SignalRef, str]]:
    unique: dict[tuple[str, str], tuple[SignalRef, str]] = {}
    for ref, role in items:
        unique[(ref.base_signal, role)] = (ref, role)
    return [unique[key] for key in sorted(unique)]


def _iter_always_blocks(text: str) -> list[tuple[int, int, str, str]]:
    blocks: list[tuple[int, int, str, str]] = []
    for match in re.finditer(r"\balways(?:_[A-Za-z0-9_]+)?\s*(?:@\s*\([^;]*?\))?", text):
        start = match.start()
        next_match = re.search(r"\balways(?:_[A-Za-z0-9_]+)?\b|\bendmodule\b", text[match.end() :])
        end = len(text) if not next_match else match.end() + next_match.start()
        block = text[start:end]
        blocks.append((start, end, match.group(0), block))
    return blocks
