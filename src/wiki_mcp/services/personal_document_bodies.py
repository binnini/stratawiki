from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from wiki_mcp.schemas.rendered_artifact import RenderedArtifact
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef

@dataclass(frozen=True, slots=True)
class PersonalDocumentBodyReadResult:
    body_markdown: str


@dataclass(slots=True)
class PersonalDocumentBodyStore:
    rendering_repository: Any

    def read_body(
        self,
        *,
        path: str,
        scope_ref: ScopeRef,
    ) -> PersonalDocumentBodyReadResult:
        raw_body = self.rendering_repository.read_body(path=path, scope_ref=scope_ref)
        return self.parse_body(raw_body)

    def write_body(
        self,
        *,
        domain: str,
        record_id: str,
        path: str,
        title: str,
        body_markdown: str,
        scope_ref: ScopeRef,
        snapshot_ref: SnapshotRef,
    ) -> str:
        return self.rendering_repository.write_artifact(
            self._artifact(
                domain=domain,
                record_id=record_id,
                path=path,
                title=title,
                body_markdown=body_markdown,
                scope_ref=scope_ref,
                snapshot_ref=snapshot_ref,
            )
        )

    def replace_body_atomically(
        self,
        *,
        domain: str,
        record_id: str,
        path: str,
        title: str,
        body_markdown: str,
        scope_ref: ScopeRef,
        snapshot_ref: SnapshotRef,
    ) -> dict[str, object]:
        return self.rendering_repository.replace_artifact_atomically(
            self._artifact(
                domain=domain,
                record_id=record_id,
                path=path,
                title=title,
                body_markdown=body_markdown,
                scope_ref=scope_ref,
                snapshot_ref=snapshot_ref,
            )
        )

    def commit_body_write(self, receipt: dict[str, object]) -> None:
        self.rendering_repository.commit_artifact_replacement(receipt)

    def rollback_body_write(self, receipt: dict[str, object]) -> None:
        self.rendering_repository.rollback_artifact_replacement(receipt)

    def content_hash(self, body_markdown: str) -> str:
        return hashlib.sha256(self.render_body(body_markdown).encode("utf-8")).hexdigest()

    def render_body(self, body_markdown: str) -> str:
        normalized_body = body_markdown.rstrip("\n")
        if normalized_body:
            return normalized_body + "\n"
        return ""

    def parse_body(self, raw_body: str | None) -> PersonalDocumentBodyReadResult:
        if not isinstance(raw_body, str) or not raw_body.strip():
            return PersonalDocumentBodyReadResult(body_markdown="")
        return PersonalDocumentBodyReadResult(body_markdown=raw_body.rstrip("\n"))

    def _artifact(
        self,
        *,
        domain: str,
        record_id: str,
        path: str,
        title: str,
        body_markdown: str,
        scope_ref: ScopeRef,
        snapshot_ref: SnapshotRef,
    ) -> RenderedArtifact:
        return {
            "domain": domain,
            "layer": "personal",
            "record_id": record_id,
            "path": path,
            "title": title,
            "body_markdown": self.render_body(body_markdown),
            "scope_ref": scope_ref,
            "snapshot_ref": snapshot_ref,
        }
