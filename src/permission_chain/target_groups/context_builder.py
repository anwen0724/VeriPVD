from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import PermissionTargetGroupConfig
from .graph_index import TargetGroupGraphIndex
from .schema import PermissionTargetGroup


@dataclass(frozen=True)
class _Span:
    file: str
    line_start: int
    line_end: int
    node_ids: tuple[str, ...] = ()
    edge_ids: tuple[str, ...] = ()
    statement_ids: tuple[str, ...] = ()


def build_target_group_contexts(
    graph_id: str,
    groups: list[PermissionTargetGroup],
    index: TargetGroupGraphIndex,
    repo_root: str | Path,
    config: PermissionTargetGroupConfig,
) -> dict[str, Any]:
    return {
        "graph_id": graph_id,
        "schema_version": config.schema_version,
        "groups": [_build_group_context(group, index, Path(repo_root), config) for group in groups],
    }


def _build_group_context(
    group: PermissionTargetGroup,
    index: TargetGroupGraphIndex,
    repo_root: Path,
    config: PermissionTargetGroupConfig,
) -> dict[str, Any]:
    member_node_ids = sorted(
        {str(member.get("point", {}).get("node_id", "")) for member in group.members if member.get("point", {}).get("node_id")}
    )
    edge_map: dict[str, dict[str, Any]] = {}
    node_ids = set(member_node_ids)
    for node_id in member_node_ids:
        for edge in index.adjacent_relation_edges(node_id):
            edge_id = str(edge.get("id", ""))
            edge_map[edge_id] = edge
            node_ids.update([str(edge.get("from", "")), str(edge.get("to", ""))])
            via_instance = str((edge.get("attrs") or {}).get("via_instance", ""))
            if via_instance:
                node_ids.add(via_instance)
    kept_edges = [edge_map[key] for key in sorted(edge_map)[: config.max_neighborhood_edges_per_group]]
    kept_node_ids = set(member_node_ids)
    for edge in kept_edges:
        kept_node_ids.update([str(edge.get("from", "")), str(edge.get("to", ""))])
        via_instance = str((edge.get("attrs") or {}).get("via_instance", ""))
        if via_instance:
            kept_node_ids.add(via_instance)
    nodes = [summary for node_id in sorted(kept_node_ids) if (summary := index.formal_node_summary(node_id))]
    spans = _collect_spans(group, index)
    snippets = _extract_snippets(spans, repo_root, config)
    return {
        "target_group_id": group.target_group_id,
        "representative_target_id": group.representative_target_id,
        "members": group.members,
        "equivalence_evidence": [item.to_json_dict() for item in group.equivalence_evidence],
        "related_evidence": [item.to_json_dict() for item in group.related_evidence],
        "neighborhood": {
            "nodes": nodes,
            "edges": [index.formal_edge_summary(edge) for edge in kept_edges],
        },
        "source_snippets": snippets,
    }


def _collect_spans(group: PermissionTargetGroup, index: TargetGroupGraphIndex) -> list[_Span]:
    spans: list[_Span] = []
    for member in group.members:
        for loc in member.get("source_locs", []) or []:
            spans.append(
                _Span(
                    file=str(loc.get("file", "")),
                    line_start=int(loc.get("line_start", 0)),
                    line_end=int(loc.get("line_end", 0)),
                    node_ids=(str(loc.get("node_id", "")),),
                )
            )
    for evidence in [*group.equivalence_evidence, *group.related_evidence]:
        for statement_id in evidence.statement_ids:
            loc = index.source_loc(statement_id)
            if loc:
                spans.append(
                    _Span(
                        file=str(loc.get("file", "")),
                        line_start=int(loc.get("line_start", 0)),
                        line_end=int(loc.get("line_end", 0)),
                        node_ids=tuple(evidence.node_ids),
                        edge_ids=tuple(evidence.edge_ids),
                        statement_ids=(statement_id,),
                    )
                )
        for edge_id in evidence.edge_ids:
            edge = index.edges_by_id.get(edge_id) or {}
            via_instance = str((edge.get("attrs") or {}).get("via_instance", ""))
            loc = index.source_loc(via_instance) if via_instance else None
            if loc:
                spans.append(
                    _Span(
                        file=str(loc.get("file", "")),
                        line_start=int(loc.get("line_start", 0)),
                        line_end=int(loc.get("line_end", 0)),
                        node_ids=tuple(evidence.node_ids),
                        edge_ids=(edge_id,),
                    )
                )
    valid = [span for span in spans if span.file and span.line_start > 0 and span.line_end >= span.line_start]
    return _merge_spans(valid)


def _merge_spans(spans: list[_Span]) -> list[_Span]:
    merged: list[_Span] = []
    for span in sorted(spans, key=lambda item: (item.file, item.line_start, item.line_end)):
        if not merged or merged[-1].file != span.file or span.line_start > merged[-1].line_end + 1:
            merged.append(span)
            continue
        previous = merged[-1]
        merged[-1] = _Span(
            file=previous.file,
            line_start=min(previous.line_start, span.line_start),
            line_end=max(previous.line_end, span.line_end),
            node_ids=tuple(sorted(set(previous.node_ids + span.node_ids))),
            edge_ids=tuple(sorted(set(previous.edge_ids + span.edge_ids))),
            statement_ids=tuple(sorted(set(previous.statement_ids + span.statement_ids))),
        )
    return merged


def _extract_snippets(
    spans: list[_Span],
    repo_root: Path,
    config: PermissionTargetGroupConfig,
) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    total_chars = 0
    file_cache: dict[str, list[str] | None] = {}
    for span in spans:
        if span.file not in file_cache:
            path = repo_root / span.file
            file_cache[span.file] = path.read_text(encoding="utf-8", errors="ignore").splitlines() if path.exists() else None
        lines = file_cache[span.file]
        if lines is None:
            continue
        start = max(1, span.line_start - config.snippet_context_lines)
        end = min(len(lines), span.line_end + config.snippet_context_lines)
        code = "\n".join(lines[start - 1 : end])
        if total_chars + len(code) > config.max_source_chars_per_group:
            remaining = config.max_source_chars_per_group - total_chars
            if remaining <= 0:
                break
            code = code[:remaining]
        snippets.append(
            {
                "snippet_id": f"GROUP-SNIP-{len(snippets) + 1:04d}",
                "file": span.file,
                "line_start": start,
                "line_end": end,
                "node_ids": list(span.node_ids),
                "edge_ids": list(span.edge_ids),
                "statement_ids": list(span.statement_ids),
                "code": code,
            }
        )
        total_chars += len(code)
    return snippets
