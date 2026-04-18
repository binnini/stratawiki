from __future__ import annotations

import json
import re

from wiki_mcp.schemas import (
    INTERPRETATION_STATUS_PUBLISHED,
    InterpretationRecord,
    RenderedArtifact,
    RenderedPage,
    ScopeRef,
)
from wiki_mcp.services.interfaces.repositories import (
    InterpretationRepository,
    RenderingRepository,
)


class InterpretationRenderingService:
    """Render readable shared pages from published canonical interpretation records."""

    market_trend_template_version = "market_trend.shared.v1"
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
        if record["status"] != INTERPRETATION_STATUS_PUBLISHED:
            return None

        page_family = self._page_family(record)
        if page_family != "market_trend":
            return None

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
            "render_template_version": self.market_trend_template_version,
        }
        body_markdown = self._render_market_trend_body(record, metadata)
        path = f"wiki/shared/interpretations/{page_family}/{self._slug(page_key)}.md"
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
        artifact: RenderedArtifact = {
            "domain": page["domain"],
            "layer": page["layer"],
            "record_id": page["record_id"],
            "path": page["path"],
            "title": page["title"],
            "body_markdown": self._artifact_markdown(page),
            "scope_ref": page["scope_ref"],
            "snapshot_ref": page["snapshot_ref"],
        }
        self.rendering_repository.write_artifact(artifact)
        return page

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

    def _render_market_trend_body(
        self,
        record: InterpretationRecord,
        metadata: dict[str, object],
    ) -> str:
        summary = str(record.get("summary") or record.get("claim") or record["id"])
        claim = str(record.get("claim") or summary)
        interpretation_snapshot = str(record.get("interpretation_snapshot_id") or "not_available")
        fact_snapshot = record["fact_snapshot_id"]
        evidence_lines = self._render_evidence_lines(record)
        return "\n".join(
            [
                f"# {self._page_title(record)}",
                "",
                f"Segment: `{record['subject_id']}`",
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
                "## Evidence",
                *evidence_lines,
            ]
        )

    def _render_evidence_lines(self, record: InterpretationRecord) -> list[str]:
        evidence = record.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            return ["- none"]

        lines: list[str] = []
        for item in evidence:
            if not isinstance(item, dict):
                continue
            fact_id = str(item.get("fact_id") or "unknown")
            weight = item.get("weight")
            role = item.get("role")
            fragments = [fact_id]
            if isinstance(role, str) and role:
                fragments.append(f"role={role}")
            if isinstance(weight, (int, float)):
                fragments.append(f"weight={weight}")
            lines.append("- " + " ".join(fragments))
        return lines or ["- none"]

    def _page_family(self, record: InterpretationRecord) -> str:
        render_hints = record.get("render_hints")
        if isinstance(render_hints, dict):
            page_family = render_hints.get("page_family")
            if isinstance(page_family, str) and page_family.strip():
                return page_family.strip()
        return str(record.get("family") or "interpretation")

    def _page_key(self, record: InterpretationRecord) -> str:
        render_hints = record.get("render_hints")
        if isinstance(render_hints, dict):
            page_key = render_hints.get("page_key")
            if isinstance(page_key, str) and page_key.strip():
                return page_key.strip()
        return str(record.get("subject_id") or record["id"])

    def _page_title(self, record: InterpretationRecord) -> str:
        title = record.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
        return f"Market trend: {record['subject_id']}"

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "page"
