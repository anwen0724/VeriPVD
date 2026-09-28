from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


RTL_SUFFIXES = {".v", ".sv", ".vh"}


@dataclass(frozen=True)
class RtlSource:
    path: Path
    relative_path: str
    text: str

    def line_for_offset(self, offset: int) -> int:
        return self.text.count("\n", 0, max(offset, 0)) + 1


def scan_rtl_sources(repo_root: Path) -> list[RtlSource]:
    root = Path(repo_root)
    sources: list[RtlSource] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in RTL_SUFFIXES:
            continue
        relative_path = path.relative_to(root).as_posix()
        sources.append(
            RtlSource(
                path=path,
                relative_path=relative_path,
                text=path.read_text(encoding="utf-8", errors="ignore"),
            )
        )
    return sources
