"""Markdown-file memory store.

Each entry is a markdown file: YAML frontmatter (system, scope, category, tags,
timestamps, source, review status) over a free-text body. The files are the
single source of truth — humans and agents edit them, and git review curates
changes, so there is no locking or conflict resolution. Last write to a file
wins.

Layout keeps scopes in separate directories so visibility is a matter of which
directories an agent reads:

    <root>/<system>/workspace/
    <root>/<system>/workflow/<workflow-name>/
    <root>/<system>/agent/<agent-type>/

The namespace segment isolates one workflow or agent type from another.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import yaml

from geartrain.memory.guardrail import scan_for_secrets
from geartrain.memory.store import (
    MemoryRecord,
    MemoryScope,
    MemorySystem,
    ScopeSpec,
    WriteResult,
)

_FORGOTTEN = "forgotten"
_ACTIVE = "active"


class MarkdownMemoryStore:
    """File-backed :class:`~geartrain.memory.store.MemoryStore`.

    *root* is the memory directory; system and scope subdirectories are created
    on demand. Set ``guardrail=False`` only in tests that need to bypass secret
    detection.
    """

    def __init__(self, root: str | Path, *, guardrail: bool = True) -> None:
        self.root = Path(root)
        self.guardrail = guardrail

    # --- write ------------------------------------------------------------

    def write(
        self,
        *,
        system: MemorySystem,
        scope: MemoryScope,
        content: str,
        namespace: str = "",
        category: str = "",
        tags: Sequence[str] = (),
        source_run: str = "",
        source_node: str = "",
        source_agent: str = "",
    ) -> WriteResult:
        review_status = "unreviewed"
        if self.guardrail:
            scan = scan_for_secrets(content)
            if not scan.ok:
                return WriteResult(
                    status="rejected",
                    scope=scope,
                    system=system,
                    namespace=namespace,
                    review_status=review_status,
                    source_run=source_run,
                    source_node=source_node,
                    source_agent=source_agent,
                    guardrail=scan.to_dict(),
                    error="secret pattern detected: "
                    + ", ".join(scan.findings),
                )

        now = _now()
        directory = self._dir(system, scope, namespace)
        directory.mkdir(parents=True, exist_ok=True)
        path = self._unique_path(directory, category or content)

        frontmatter = {
            "system": system.value,
            "scope": scope.value,
            "namespace": namespace,
            "category": category,
            "tags": list(tags),
            "created_at": now,
            "updated_at": now,
            "status": _ACTIVE,
            "review_status": review_status,
            "source_run": source_run,
            "source_node": source_node,
            "source_agent": source_agent,
        }
        path.write_text(_render(frontmatter, content), encoding="utf-8")

        return WriteResult(
            status="ok",
            scope=scope,
            system=system,
            path=str(path),
            namespace=namespace,
            review_status=review_status,
            source_run=source_run,
            source_node=source_node,
            source_agent=source_agent,
            guardrail={"ok": True, "findings": []},
        )

    # --- read / list ------------------------------------------------------

    def read(
        self,
        query: str,
        *,
        system: MemorySystem,
        scopes: Sequence[ScopeSpec],
        limit: int = 10,
    ) -> list[MemoryRecord]:
        terms = _terms(query)
        scored: list[MemoryRecord] = []
        for spec in scopes:
            for record in self._iter_records(system, spec.scope, spec.namespace):
                record.score = _score(record, terms)
                if not terms or record.score > 0:
                    scored.append(record)
        scored.sort(
            key=lambda r: (r.score, r.updated_at or datetime.min), reverse=True
        )
        return scored[:limit]

    def list_entries(
        self,
        *,
        system: MemorySystem,
        scope: MemoryScope,
        namespace: str = "",
        include_forgotten: bool = False,
    ) -> list[MemoryRecord]:
        records = self._iter_records(
            system, scope, namespace, include_forgotten=include_forgotten
        )
        records.sort(key=lambda r: r.updated_at or datetime.min, reverse=True)
        return records

    # --- update / forget --------------------------------------------------

    def update(
        self,
        path: str,
        *,
        content: str,
        category: str | None = None,
        tags: Sequence[str] | None = None,
    ) -> WriteResult:
        p = Path(path)
        frontmatter, _ = _parse_file(p)  # raises if missing/malformed

        if self.guardrail:
            scan = scan_for_secrets(content)
            if not scan.ok:
                return WriteResult(
                    status="rejected",
                    path=path,
                    scope=_scope_of(frontmatter),
                    system=_system_of(frontmatter),
                    namespace=frontmatter.get("namespace", ""),
                    guardrail=scan.to_dict(),
                    error="secret pattern detected: "
                    + ", ".join(scan.findings),
                )

        if category is not None:
            frontmatter["category"] = category
        if tags is not None:
            frontmatter["tags"] = list(tags)
        frontmatter["updated_at"] = _now()
        p.write_text(_render(frontmatter, content), encoding="utf-8")

        return WriteResult(
            status="ok",
            path=path,
            scope=_scope_of(frontmatter),
            system=_system_of(frontmatter),
            namespace=frontmatter.get("namespace", ""),
            review_status=frontmatter.get("review_status", "unreviewed"),
            source_run=frontmatter.get("source_run", ""),
            source_node=frontmatter.get("source_node", ""),
            source_agent=frontmatter.get("source_agent", ""),
            guardrail={"ok": True, "findings": []},
        )

    def forget(self, path: str) -> bool:
        p = Path(path)
        if not p.exists():
            return False
        frontmatter, body = _parse_file(p)
        frontmatter["status"] = _FORGOTTEN
        frontmatter["updated_at"] = _now()
        p.write_text(_render(frontmatter, body), encoding="utf-8")
        return True

    # --- internals --------------------------------------------------------

    def _dir(
        self, system: MemorySystem, scope: MemoryScope, namespace: str
    ) -> Path:
        base = self.root / system.value
        if scope == MemoryScope.WORKSPACE:
            return base / "workspace"
        if scope == MemoryScope.WORKFLOW:
            return base / "workflow" / (namespace or "_shared")
        if scope == MemoryScope.AGENT_LEVEL:
            return base / "agent" / (namespace or "_shared")
        raise ValueError(
            f"scope {scope.value!r} is not persisted by the markdown store; "
            "agent_instance memory lives in run state"
        )

    def _iter_records(
        self,
        system: MemorySystem,
        scope: MemoryScope,
        namespace: str,
        *,
        include_forgotten: bool = False,
    ) -> list[MemoryRecord]:
        directory = self._dir(system, scope, namespace)
        if not directory.is_dir():
            return []
        records: list[MemoryRecord] = []
        for md in sorted(directory.glob("*.md")):
            try:
                frontmatter, body = _parse_file(md)
            except ValueError:
                continue
            if (
                not include_forgotten
                and frontmatter.get("status") == _FORGOTTEN
            ):
                continue
            records.append(_to_record(md, frontmatter, body))
        return records

    @staticmethod
    def _unique_path(directory: Path, seed: str) -> Path:
        slug = _slugify(seed) or "entry"
        candidate = directory / f"{slug}.md"
        if not candidate.exists():
            return candidate
        return directory / f"{slug}-{uuid.uuid4().hex[:8]}.md"


# --- frontmatter helpers ----------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _render(frontmatter: dict, body: str) -> str:
    fm = yaml.safe_dump(frontmatter, sort_keys=False, default_flow_style=False)
    return f"---\n{fm}---\n\n{body.rstrip()}\n"


def _parse_file(path: Path) -> tuple[dict, str]:
    """Split a memory file into (frontmatter dict, body). Raises on bad shape."""
    text = path.read_text(encoding="utf-8")
    if not text.lstrip().startswith("---"):
        raise ValueError(f"no YAML frontmatter found in {path}")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"incomplete YAML frontmatter in {path}")
    data = yaml.safe_load(parts[1])
    if not isinstance(data, dict):
        raise ValueError(f"expected a YAML mapping in frontmatter of {path}")
    return data, parts[2].lstrip("\n")


def _to_record(path: Path, frontmatter: dict, body: str) -> MemoryRecord:
    return MemoryRecord(
        path=str(path),
        system=_system_of(frontmatter),
        scope=_scope_of(frontmatter),
        content=body.strip(),
        category=frontmatter.get("category", "") or "",
        tags=list(frontmatter.get("tags", []) or []),
        namespace=frontmatter.get("namespace", "") or "",
        created_at=_as_datetime(frontmatter.get("created_at")),
        updated_at=_as_datetime(frontmatter.get("updated_at")),
        status=frontmatter.get("status", _ACTIVE) or _ACTIVE,
        review_status=frontmatter.get("review_status", "unreviewed")
        or "unreviewed",
        source_run=frontmatter.get("source_run", "") or "",
        source_node=frontmatter.get("source_node", "") or "",
        source_agent=frontmatter.get("source_agent", "") or "",
    )


def _system_of(frontmatter: dict) -> MemorySystem:
    return MemorySystem(frontmatter["system"])


def _scope_of(frontmatter: dict) -> MemoryScope:
    return MemoryScope(frontmatter["scope"])


def _as_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


# --- ranking ----------------------------------------------------------------


def _terms(query: str) -> list[str]:
    return [t for t in re.split(r"\W+", query.lower()) if t]


def _score(record: MemoryRecord, terms: list[str]) -> float:
    if not terms:
        return 0.0
    haystack = " ".join(
        [record.content, record.category, " ".join(record.tags)]
    ).lower()
    score = 0.0
    for term in terms:
        occurrences = haystack.count(term)
        if occurrences:
            # Category and tag hits are worth more than body hits.
            weight = 3.0 if term in record.category.lower() else 1.0
            weight = max(
                weight,
                2.0 if term in " ".join(record.tags).lower() else weight,
            )
            score += occurrences * weight
    return score


def _slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text[:48]
