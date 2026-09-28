from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphDiagnostics:
    source_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "source_files": self.source_files,
            "warnings": self.warnings,
            "stats": self.stats,
        }
