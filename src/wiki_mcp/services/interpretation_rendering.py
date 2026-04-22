from __future__ import annotations

import json
import re

from wiki_mcp.schemas import (
    INTERPRETATION_STATUS_PUBLISHED,
    InterpretationRecord,
    RenderedArtifact,
    RenderedPage,
    ScopeRef,
    interpretation_payload,
    interpretation_support_links,
)
from wiki_mcp.services.interfaces.repositories import (
    InterpretationRepository,
    RenderingRepository,
)


class InterpretationRenderingService:
    """Render readable shared pages from published canonical interpretation records."""

    generic_template_version = "interpretation.shared.v2"
    rendered_page_marker = "stratawiki:rendered_page"

    def __init__(
        self,
        *,
        interpretation_repository: InterpretationRepository,
        rendering_repository: RenderingRepository,
    ) -> None:
        self.interpretation_repository = interpretation_repository
        self.rendering_repository = rendering_repository

    def render_shared_page(
        self,
        *,
        record_id: str,
        scope_ref: ScopeRef,
    ) -> RenderedPage | None:
        if scope_ref["scope"] != "shared":
            return None

        records = self.interpretation_repository.get_by_ids([record_id], scope_ref)
        if not records:
            return None

        record = records[0]
        page = self._build_shared_page(record, scope_ref)
        if page is None:
            return None
        artifact = self._build_artifact(page)
        self.rendering_repository.write_artifact(artifact)
        return page

    def replace_shared_page_atomically(
        self,
        *,
        record: InterpretationRecord,
        scope_ref: ScopeRef,
    ) -> dict[str, object] | None:
        page = self._build_shared_page(record, scope_ref)
        if page is None:
            return None
        artifact = self._build_artifact(page)
        receipt = self.rendering_repository.replace_artifact_atomically(artifact)
        return {"page": page, "receipt": receipt}

    def commit_shared_page_replacement(self, replacement: dict[str, object] | None) -> None:
        if replacement is None:
            return None
        receipt = replacement.get("receipt")
        if isinstance(receipt, dict):
            self.rendering_repository.commit_artifact_replacement(receipt)
        return None

    def rollback_shared_page_replacement(self, replacement: dict[str, object] | None) -> None:
        if replacement is None:
            return None
        receipt = replacement.get("receipt")
        if isinstance(receipt, dict):
            self.rendering_repository.rollback_artifact_replacement(receipt)
        return None

    def _build_shared_page(
        self,
        record: InterpretationRecord,
        scope_ref: ScopeRef,
    ) -> RenderedPage | None:
        if record["status"] != INTERPRETATION_STATUS_PUBLISHED:
            return None

        page_family = self._page_family(record)
        page_kind = self._page_kind(record)
        page_key = self._page_key(record)
        title = self._page_title(record)
        snapshot_ref = {
            "fact_snapshot_id": record["fact_snapshot_id"],
            **(
                {"interpretation_snapshot_id": record["interpretation_snapshot_id"]}
                if record.get("interpretation_snapshot_id")
                else {}
            ),
        }
        metadata = {
            "page_family": page_family,
            "page_key": page_key,
            "interpretation_ids": [record["id"]],
            "render_template_version": self.generic_template_version,
            **({"page_kind": page_kind} if page_kind != page_family else {}),
        }
        body_markdown = self._render_shared_body(record, metadata)
        path_parts = ["wiki/shared/interpretations", page_family]
        if page_kind != page_family:
            path_parts.append(page_kind)
        path_parts.append(f"{self._slug(page_key)}.md")
        path = "/".join(path_parts)
        page: RenderedPage = {
            "domain": record["domain"],
            "layer": "interpretation",
            "record_id": record["id"],
            "path": path,
            "title": title,
            "scope_ref": scope_ref,
            "snapshot_ref": snapshot_ref,
            "metadata": metadata,
            "body_markdown": body_markdown,
        }
        return page

    def _build_artifact(self, page: RenderedPage) -> RenderedArtifact:
        return {
            "domain": page["domain"],
            "layer": page["layer"],
            "record_id": page["record_id"],
            "path": page["path"],
            "title": page["title"],
            "body_markdown": self._artifact_markdown(page),
            "scope_ref": page["scope_ref"],
            "snapshot_ref": page["snapshot_ref"],
        }

    def _artifact_markdown(self, page: RenderedPage) -> str:
        metadata = {
            "domain": page["domain"],
            "layer": page["layer"],
            "record_id": page["record_id"],
            "path": page["path"],
            "title": page["title"],
            "scope_ref": page["scope_ref"],
            "snapshot_ref": page["snapshot_ref"],
            "metadata": page["metadata"],
        }
        return (
            f"<!-- {self.rendered_page_marker}\n"
            + json.dumps(metadata, ensure_ascii=True, indent=2, sort_keys=True)
            + "\n-->\n\n"
            + page["body_markdown"].rstrip()
            + "\n"
        )

    def _render_shared_body(
        self,
        record: InterpretationRecord,
        metadata: dict[str, object],
    ) -> str:
        payload = interpretation_payload(record)
        summary = str(payload.get("summary") or record.get("summary") or record.get("claim") or record["id"])
        claim = str(payload.get("claim") or record.get("claim") or summary)
        body = payload.get("body")
        body = dict(body) if isinstance(body, dict) else {}
        interpretation_snapshot = str(record.get("interpretation_snapshot_id") or "not_available")
        fact_snapshot = record["fact_snapshot_id"]
        support_lines = self._render_support_lines(record)
        body_lines = self._render_payload_body(body)
        return "\n".join(
            [
                f"# {self._page_title(record)}",
                "",
                f"Subject: `{record['subject_id']}`",
                "Family / Kind: "
                f"`{metadata['page_family']}` / `{metadata.get('page_kind', metadata['page_family'])}`",
                f"Interpretation IDs: `{', '.join(metadata['interpretation_ids'])}`",
                f"Interpretation Snapshot: `{interpretation_snapshot}`",
                f"Fact Snapshot: `{fact_snapshot}`",
                f"Render Template: `{metadata['render_template_version']}`",
                "",
                "## Summary",
                summary,
                "",
                "## Claim",
                claim,
                "",
                "## Payload",
                *body_lines,
                "",
                "## Support",
                *support_lines,
            ]
        )

    def _render_support_lines(self, record: InterpretationRecord) -> list[str]:
        support_links = interpretation_support_links(record)
        if not support_links:
            return ["- none"]

        lines: list[str] = []
        for item in support_links:
            if not isinstance(item, dict):
                continue
            target_layer = str(item.get("target_layer") or "support")
            target_id = str(item.get("target_id") or "unknown")
            weight = item.get("weight")
            role = item.get("role")
            fragments = [f"{target_layer}:{target_id}"]
            if isinstance(role, str) and role:
                fragments.append(f"role={role}")
            if isinstance(weight, (int, float)):
                fragments.append(f"weight={weight}")
            lines.append("- " + " ".join(fragments))
        return lines or ["- none"]

    def _render_payload_body(self, body: dict[str, object]) -> list[str]:
        if not body:
            return ["- none"]

        lines: list[str] = []
        for key, value in body.items():
            if isinstance(value, list):
                rendered = ", ".join(str(item) for item in value) if value else "none"
            elif isinstance(value, dict):
                rendered = json.dumps(value, ensure_ascii=True, sort_keys=True)
            else:
                rendered = str(value)
            lines.append(f"- {key}: {rendered}")
        return lines

    def _page_family(self, record: InterpretationRecord) -> str:
        render_hints = record.get("render_hints")
        if isinstance(render_hints, dict):
            page_family = render_hints.get("page_family")
            if isinstance(page_family, str) and page_family.strip():
                return page_family.strip()
        return str(record.get("family") or "interpretation")

    def _page_kind(self, record: InterpretationRecord) -> str:
        render_hints = record.get("render_hints")
        if isinstance(render_hints, dict):
            page_kind = render_hints.get("page_kind")
            if isinstance(page_kind, str) and page_kind.strip():
                return page_kind.strip()
        kind = record.get("kind")
        if isinstance(kind, str) and kind.strip():
            return kind.strip()
        return "default"

    def _page_key(self, record: InterpretationRecord) -> str:
        render_hints = record.get("render_hints")
        if isinstance(render_hints, dict):
            page_key = render_hints.get("page_key")
            if isinstance(page_key, str) and page_key.strip():
                return page_key.strip()
        return str(record.get("subject_id") or record["id"])

    def _page_title(self, record: InterpretationRecord) -> str:
        payload = interpretation_payload(record)
        title = payload.get("title") or record.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
        kind = self._page_kind(record)
        return f"{kind}: {record['subject_id']}"

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "page"
