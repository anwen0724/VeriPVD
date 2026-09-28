from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .candidate_builder import build_untrimmed_candidates
from .config import PermissionTargetGroupConfig
from .context_builder import build_target_group_contexts
from .diagnostics import build_group_diagnostics
from .equivalence import build_equivalence
from .graph_index import TargetGroupGraphIndex
from .grouping import build_target_groups
from .relations import build_related_relations
from .schema import PermissionTargetGroups
from .writer import write_target_group_outputs


def build_permission_target_groups(
    graph_path: str | Path,
    repo_root: str | Path,
    output_dir: str | Path,
    config: PermissionTargetGroupConfig | None = None,
) -> dict[str, Any]:
    cfg = config or PermissionTargetGroupConfig()
    graph_doc = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    index = TargetGroupGraphIndex.from_json_dict(graph_doc)
    candidates = build_untrimmed_candidates(index, cfg)
    equivalence = build_equivalence(index, candidates)
    relations = build_related_relations(index, equivalence)
    groups = build_target_groups(equivalence, relations, cfg)
    formal_groups = PermissionTargetGroups(index.graph_id, groups, schema_version=cfg.schema_version)
    contexts = build_target_group_contexts(index.graph_id, groups, index, repo_root, cfg)
    diagnostics = build_group_diagnostics(index.graph_id, candidates, equivalence, relations, groups)
    if not diagnostics.candidate_conservation_ok:
        raise ValueError("Target grouping failed candidate conservation")
    paths = write_target_group_outputs(output_dir, formal_groups, contexts, diagnostics)
    return {
        "graph_id": index.graph_id,
        "raw_candidate_count": len(candidates),
        "equivalence_object_count": len(equivalence.candidate_roots),
        "target_group_count": len(groups),
        "related_group_count": diagnostics.related_group_count,
        "source_snippet_count": sum(len(group.get("source_snippets", [])) for group in contexts["groups"]),
        "groups_path": str(paths[0]),
        "contexts_path": str(paths[1]),
        "diagnostics_path": str(paths[2]),
        "output_dir": str(output_dir),
    }
