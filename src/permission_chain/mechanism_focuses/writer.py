from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import PermissionMechanismFocuses


def write_focus_outputs(
    output_dir: str | Path,
    focuses: PermissionMechanismFocuses,
    diagnostics: dict[str, Any],
) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "permission_mechanism_focuses.json").write_text(
        json.dumps(focuses.to_json_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "mechanism_focus_diagnostics.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
