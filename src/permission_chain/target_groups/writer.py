from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .diagnostics import TargetGroupDiagnostics
from .schema import PermissionTargetGroups, assert_no_forbidden_group_keys


def write_target_group_outputs(
    output_dir: str | Path,
    groups: PermissionTargetGroups,
    contexts: dict[str, Any],
    diagnostics: TargetGroupDiagnostics,
) -> tuple[Path, Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    groups_path = out / "permission_target_groups.json"
    contexts_path = out / "permission_target_group_contexts.json"
    diagnostics_path = out / "target_group_diagnostics.json"
    groups_payload = groups.to_json_dict()
    assert_no_forbidden_group_keys(groups_payload)
    _write_json(groups_path, groups_payload)
    _write_json(contexts_path, contexts)
    _write_json(diagnostics_path, diagnostics.to_json_dict())
    return groups_path, contexts_path, diagnostics_path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
