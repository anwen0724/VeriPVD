from __future__ import annotations

from collections import Counter

from .config import PermissionTargetConfig
from .graph_index import RtlGraphIndex
from .point_selector import CandidatePoint
from .schema import (
    PermissionCheckTarget,
    TargetAccess,
    TargetPoint,
    TargetSourceLoc,
)


def make_target(
    index: RtlGraphIndex,
    point: CandidatePoint,
    accesses: list[TargetAccess],
    sequence: int,
    config: PermissionTargetConfig,
) -> PermissionCheckTarget:
    source_locs: list[TargetSourceLoc] = []
    point_loc = index.source_loc(point.node_id)
    if point_loc:
        source_locs.append(_to_source_loc(point.node_id, point_loc, "point"))
    for access in accesses:
        loc = index.source_loc(access.node_id)
        if loc:
            source_locs.append(_to_source_loc(access.node_id, loc, "access"))
    source_locs = _dedupe_locs(source_locs)[: config.max_source_locs_per_target]
    return PermissionCheckTarget(
        target_id=f"target:{point.module}:{point.name}:{sequence}",
        point=TargetPoint(
            node_id=point.node_id,
            name=point.name,
            module=point.module,
            point_roles=list(point.point_roles),
        ),
        accesses=accesses,
        source_locs=source_locs,
    )


def count_roles(targets: list[PermissionCheckTarget]) -> tuple[dict[str, int], dict[str, int]]:
    point_counter: Counter[str] = Counter()
    access_counter: Counter[str] = Counter()
    for target in targets:
        point_counter.update(target.point.point_roles)
        for access in target.accesses:
            access_counter.update(access.access_roles)
    return dict(point_counter), dict(access_counter)


def _to_source_loc(node_id: str, loc: dict, role: str) -> TargetSourceLoc:
    return TargetSourceLoc(
        node_id=node_id,
        file=str(loc.get("file", "")),
        line_start=int(loc.get("line_start", 0)),
        line_end=int(loc.get("line_end", 0)),
        role=role,
    )


def _dedupe_locs(locs: list[TargetSourceLoc]) -> list[TargetSourceLoc]:
    seen: set[tuple[str, str]] = set()
    result: list[TargetSourceLoc] = []
    for loc in locs:
        key = (loc.node_id, loc.role)
        if key in seen:
            continue
        seen.add(key)
        result.append(loc)
    return result
