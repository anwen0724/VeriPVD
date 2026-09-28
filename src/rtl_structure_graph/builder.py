from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rtl_structure_graph import ids
from rtl_structure_graph.diagnostics import GraphDiagnostics
from rtl_structure_graph.extractors.expressions import extract_signal_refs
from rtl_structure_graph.extractors.instances import InstanceDef, extract_instances
from rtl_structure_graph.extractors.modules import ModuleDef, extract_modules
from rtl_structure_graph.extractors.signals import SignalDef, extract_signals
from rtl_structure_graph.extractors.statements import StatementDef, extract_statements
from rtl_structure_graph.models import GraphEdge, GraphNode, RtlGraph, SourceLoc
from rtl_structure_graph.scanner import scan_rtl_sources


@dataclass(frozen=True)
class BuildResult:
    graph: RtlGraph
    diagnostics: GraphDiagnostics


def build_rtl_structure_graph(repo_root: str | Path, graph_id: str | None = None) -> BuildResult:
    root = Path(repo_root)
    graph = RtlGraph(graph_id=graph_id or root.name)
    diagnostics = GraphDiagnostics()
    sources = scan_rtl_sources(root)
    diagnostics.source_files = [source.relative_path for source in sources]
    modules: list[ModuleDef] = []
    for source in sources:
        modules.extend(extract_modules(source))
    known_modules = {module.name for module in modules}
    module_by_name = {module.name: module for module in modules}

    for module in modules:
        graph.add_node(
            GraphNode(
                id=ids.module_id(module.name),
                type="Module",
                scope=None,
                name=module.name,
                loc=module.loc,
                attrs={"header_raw": " ".join(module.header_text.split())},
            )
        )

    signal_defs: dict[str, dict[str, SignalDef]] = {}
    for module in modules:
        signal_defs[module.name] = {}
        for signal in extract_signals(module):
            signal_defs[module.name][signal.name] = signal
            _upsert_signal(graph, module.name, signal)

    instances: list[InstanceDef] = []
    for module in modules:
        for instance in extract_instances(module, known_modules):
            instances.append(instance)
            graph.add_node(
                GraphNode(
                    id=ids.instance_id(instance.parent_module, instance.name),
                    type="Instance",
                    scope=ids.module_id(instance.parent_module),
                    name=instance.name,
                    loc=instance.loc,
                    attrs={
                        "module_type": instance.module_type,
                        "resolved_module": (
                            ids.module_id(instance.module_type)
                            if instance.module_type in known_modules
                            else None
                        ),
                        "unresolved": instance.module_type not in known_modules,
                        "parameter_bindings_raw": instance.parameter_text,
                        "parameter_text": instance.parameter_text,
                    },
                )
            )

    edge_number = 1
    edge_number = _add_connect_edges(graph, diagnostics, instances, signal_defs, module_by_name, edge_number)
    edge_number = _add_statement_nodes_and_edges(graph, modules, signal_defs, edge_number)

    diagnostics.stats = {
        "source_files": len(sources),
        "modules": len([node for node in graph.nodes if node.type == "Module"]),
        "instances": len([node for node in graph.nodes if node.type == "Instance"]),
        "signals": len([node for node in graph.nodes if node.type == "Signal"]),
        "statements": len([node for node in graph.nodes if node.type == "StmtSummary"]),
        "edges": len(graph.edges),
    }
    return BuildResult(graph=graph, diagnostics=diagnostics)


def _add_connect_edges(
    graph: RtlGraph,
    diagnostics: GraphDiagnostics,
    instances: list[InstanceDef],
    signal_defs: dict[str, dict[str, SignalDef]],
    module_by_name: dict[str, ModuleDef],
    edge_number: int,
) -> int:
    for instance in instances:
        child_module = module_by_name.get(instance.module_type)
        if not child_module:
            diagnostics.add_warning(
                f"Unresolved instance {instance.parent_module}.{instance.name}: {instance.module_type}"
            )
            continue
        for binding in instance.port_bindings:
            actual_refs = extract_signal_refs(binding.actual_expr)
            if not actual_refs:
                continue
            actual_name = actual_refs[0].base_signal
            parent_signal = _ensure_signal(graph, instance.parent_module, actual_name, instance.loc, signal_defs)
            child_signal = _ensure_signal(graph, child_module.name, binding.formal_port, child_module.loc, signal_defs)
            child_node = graph.get_node(child_signal)
            direction = (child_node.attrs.get("direction") if child_node else None) or "unknown"
            if direction == "output":
                from_id, to_id = child_signal, parent_signal
            else:
                from_id, to_id = parent_signal, child_signal
            graph.add_edge(
                GraphEdge(
                    id=ids.edge_id("connects", edge_number),
                    type="connects",
                    from_id=from_id,
                    to_id=to_id,
                    attrs={
                        "via_instance": ids.instance_id(instance.parent_module, instance.name),
                        "formal_port": binding.formal_port,
                        "formal_port_direction": direction,
                        "actual_expr": binding.actual_expr,
                        "actual_base_signal": actual_name,
                        "direction": "child_to_parent" if direction == "output" else "parent_to_child",
                    },
                )
            )
            edge_number += 1
    return edge_number


def _add_statement_nodes_and_edges(
    graph: RtlGraph,
    modules: list[ModuleDef],
    signal_defs: dict[str, dict[str, SignalDef]],
    edge_number: int,
) -> int:
    for module in modules:
        for statement in extract_statements(module):
            statement_id = ids.stmt_id(module.name, statement.loc.line_start, statement.kind)
            graph.add_node(
                GraphNode(
                    id=statement_id,
                    type="StmtSummary",
                    scope=ids.module_id(module.name),
                    name=f"{statement.kind}:{statement.loc.line_start}",
                    loc=statement.loc,
                    attrs=statement.attrs,
                )
            )
            for ref in statement.write_refs:
                signal = _ensure_signal(graph, module.name, ref.base_signal, statement.loc, signal_defs)
                if statement.kind == "state_update":
                    _mark_signal_register(graph, signal)
                graph.add_edge(
                    GraphEdge(
                        id=ids.edge_id("writes", edge_number),
                        type="writes",
                        from_id=statement_id,
                        to_id=signal,
                        attrs={"lhs_raw": ref.raw},
                    )
                )
                edge_number += 1
            seen_reads: set[tuple[str, str]] = set()
            for ref, role in statement.read_refs:
                signal = _ensure_signal(graph, module.name, ref.base_signal, statement.loc, signal_defs)
                key = (signal, role)
                if key in seen_reads:
                    continue
                seen_reads.add(key)
                graph.add_edge(
                    GraphEdge(
                        id=ids.edge_id("reads", edge_number),
                        type="reads",
                        from_id=statement_id,
                        to_id=signal,
                        attrs={"read_role": role, "raw_expr": ref.raw, "selectors": ref.selectors},
                    )
                )
                edge_number += 1
    return edge_number


def _upsert_signal(graph: RtlGraph, module_name: str, signal: SignalDef) -> str:
    node_id = ids.signal_id(module_name, signal.name)
    existing = graph.get_node(node_id)
    if existing:
        attrs = dict(existing.attrs)
        attrs.update(signal.attrs)
        graph.replace_node(
            GraphNode(
                id=existing.id,
                type=existing.type,
                scope=existing.scope,
                name=existing.name,
                loc=existing.loc,
                attrs=attrs,
            )
        )
        return node_id
    graph.add_node(
        GraphNode(
            id=node_id,
            type="Signal",
            scope=ids.module_id(module_name),
            name=signal.name,
            loc=signal.loc,
            attrs=signal.attrs,
        )
    )
    return node_id


def _ensure_signal(
    graph: RtlGraph,
    module_name: str,
    signal_name: str,
    fallback_loc: SourceLoc,
    signal_defs: dict[str, dict[str, SignalDef]],
) -> str:
    existing = graph.get_node(ids.signal_id(module_name, signal_name))
    if existing:
        return existing.id
    signal = SignalDef(
        name=signal_name,
        loc=fallback_loc,
        attrs={"kind": "implicit", "decl_raw": None},
    )
    signal_defs.setdefault(module_name, {})[signal_name] = signal
    return _upsert_signal(graph, module_name, signal)


def _mark_signal_register(graph: RtlGraph, signal_id: str) -> None:
    node = graph.get_node(signal_id)
    if not node:
        return
    attrs = dict(node.attrs)
    attrs["kind"] = "register"
    graph.replace_node(
        GraphNode(
            id=node.id,
            type=node.type,
            scope=node.scope,
            name=node.name,
            loc=node.loc,
            attrs=attrs,
        )
    )
