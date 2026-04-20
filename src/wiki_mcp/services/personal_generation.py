from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from wiki_mcp.adapters.llm.gateway import LLMGateway
from wiki_mcp.schemas.rendered_artifact import RenderedArtifact
from wiki_mcp.schemas.scope_ref import ScopeRef


class PersonalDocumentGenerationService:
    """Run Personal raw-to-wiki generation and wiki link operations."""

    document_marker = "stratawiki:personal_document"

    def __init__(
        self,
        *,
        llm_gateway: LLMGateway,
        personal_repository: Any,
        rendering_repository: Any,
        fact_repository: Any,
        interpretation_repository: Any,
        snapshot_repository: Any,
        profile_context_repository: Any,
    ) -> None:
        self.llm_gateway = llm_gateway
        self.personal_repository = personal_repository
        self.rendering_repository = rendering_repository
        self.fact_repository = fact_repository
        self.interpretation_repository = interpretation_repository
        self.snapshot_repository = snapshot_repository
        self.profile_context_repository = profile_context_repository

    def summarize_personal_document_to_wiki(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        source_document_ref: dict[str, Any],
        profile_version: str,
        model_profile: str,
        save_target: dict[str, Any],
        summary_style: str,
    ) -> dict[str, Any]:
        return self._generate_personal_document_to_wiki(
            operation="summarize",
            domain=domain,
            scope_ref=scope_ref,
            source_document_ref=source_document_ref,
            profile_version=profile_version,
            model_profile=model_profile,
            save_target=save_target,
            instruction_value=summary_style,
        )

    def rewrite_personal_document_to_wiki(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        source_document_ref: dict[str, Any],
        profile_version: str,
        model_profile: str,
        save_target: dict[str, Any],
        rewrite_goal: str,
    ) -> dict[str, Any]:
        return self._generate_personal_document_to_wiki(
            operation="rewrite",
            domain=domain,
            scope_ref=scope_ref,
            source_document_ref=source_document_ref,
            profile_version=profile_version,
            model_profile=model_profile,
            save_target=save_target,
            instruction_value=rewrite_goal,
        )

    def structure_personal_document_to_wiki(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        source_document_ref: dict[str, Any],
        profile_version: str,
        model_profile: str,
        save_target: dict[str, Any],
        structure_template: str,
    ) -> dict[str, Any]:
        return self._generate_personal_document_to_wiki(
            operation="structure",
            domain=domain,
            scope_ref=scope_ref,
            source_document_ref=source_document_ref,
            profile_version=profile_version,
            model_profile=model_profile,
            save_target=save_target,
            instruction_value=structure_template,
        )

    def suggest_personal_wiki_links(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        wiki_document_id: str,
        wiki_document_version: int,
        profile_version: str,
        model_profile: str,
        max_suggestions: int,
    ) -> dict[str, Any]:
        self._require_profile_context(domain=domain, scope_ref=scope_ref, profile_version=profile_version)
        wiki_document = self._load_document(
            domain=domain,
            document_id=wiki_document_id,
            scope_ref=scope_ref,
        )
        if wiki_document["subspace"] != "wiki":
            raise ValueError("suggest_personal_wiki_links requires wiki_document_id to resolve to subspace 'wiki'.")
        if wiki_document["version"] != wiki_document_version:
            raise ValueError(
                f"wiki_document_version does not match the current stored version. Current version is {wiki_document['version']}."
            )

        query_text = "\n".join(
            part
            for part in (
                wiki_document.get("title"),
                wiki_document.get("summary"),
                wiki_document.get("body_markdown"),
            )
            if isinstance(part, str) and part.strip()
        )
        query_tokens = self._tokenize(query_text)
        existing_anchor_keys = {
            (anchor["layer"], anchor["id"])
            for anchor in wiki_document.get("anchors", [])
        }
        suggestions: list[dict[str, Any]] = []
        source_document_ref = wiki_document.get("source_document_ref")
        if isinstance(source_document_ref, dict):
            try:
                source_document = self._load_document(
                    domain=domain,
                    document_id=str(source_document_ref["document_id"]),
                    scope_ref=scope_ref,
                )
            except KeyError:
                source_document = None
            if source_document is not None:
                for anchor in source_document.get("anchors", []):
                    key = (anchor["layer"], anchor["id"])
                    if key in existing_anchor_keys:
                        continue
                    suggestions.append(
                        {
                            "layer": anchor["layer"],
                            "id": anchor["id"],
                            "reason": "preserved from the raw source document",
                            "confidence": 0.98,
                        }
                    )
                    existing_anchor_keys.add(key)

        shared_scope = {"scope": "shared"}
        interpretation_records = self.interpretation_repository.search_for_retrieval(
            domain=domain,
            scope_ref=shared_scope,
            query_text=query_text,
            query_tokens=query_tokens,
            limit=max(max_suggestions, 1),
        )
        for record in interpretation_records:
            key = ("interpretation", str(record["id"]))
            if key in existing_anchor_keys:
                continue
            suggestions.append(
                {
                    "layer": "interpretation",
                    "id": record["id"],
                    "reason": "wiki text matches shared interpretation context",
                    "confidence": 0.74,
                }
            )
            existing_anchor_keys.add(key)
            if len(suggestions) >= max_suggestions:
                break

        if len(suggestions) < max_suggestions:
            fact_records = self.fact_repository.search_for_retrieval(
                domain=domain,
                scope_ref=shared_scope,
                query_text=query_text,
                query_tokens=query_tokens,
                limit=max(max_suggestions, 1),
            )
            for record in fact_records:
                key = ("fact", str(record["id"]))
                if key in existing_anchor_keys:
                    continue
                suggestions.append(
                    {
                        "layer": "fact",
                        "id": record["id"],
                        "reason": "wiki text matches shared fact context",
                        "confidence": 0.7,
                    }
                )
                existing_anchor_keys.add(key)
                if len(suggestions) >= max_suggestions:
                    break

        return {
            "status": "ok",
            "wiki_document_id": wiki_document_id,
            "wiki_document_version": wiki_document_version,
            "model_profile": model_profile,
            "suggestions": suggestions[:max_suggestions],
        }

    def attach_personal_wiki_links(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        wiki_document_id: str,
        wiki_document_version: int,
        attachments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        wiki_document = self._load_document(
            domain=domain,
            document_id=wiki_document_id,
            scope_ref=scope_ref,
        )
        if wiki_document["subspace"] != "wiki":
            raise ValueError("attach_personal_wiki_links requires wiki_document_id to resolve to subspace 'wiki'.")
        if wiki_document["version"] != wiki_document_version:
            raise ValueError(
                f"wiki_document_version does not match the current stored version. Current version is {wiki_document['version']}."
            )
        normalized_attachments = self._normalize_attachments(attachments)
        self._validate_shared_attachments(normalized_attachments)

        merged_anchors = self._dedupe_anchors(
            [*wiki_document.get("anchors", []), *normalized_attachments]
        )
        updated_document = dict(wiki_document)
        updated_document["version"] = wiki_document["version"] + 1
        updated_document["anchors"] = merged_anchors
        updated_document["updated_at"] = self._now_iso()
        self._persist_document(updated_document)
        return {
            "status": "ok",
            "wiki_document_id": wiki_document_id,
            "wiki_document_version": updated_document["version"],
            "attached": normalized_attachments,
        }

    def _generate_personal_document_to_wiki(
        self,
        *,
        operation: str,
        domain: str,
        scope_ref: ScopeRef,
        source_document_ref: dict[str, Any],
        profile_version: str,
        model_profile: str,
        save_target: dict[str, Any],
        instruction_value: str,
    ) -> dict[str, Any]:
        self._require_profile_context(domain=domain, scope_ref=scope_ref, profile_version=profile_version)
        source_document = self._load_document(
            domain=domain,
            document_id=self._required_string(source_document_ref, "document_id"),
            scope_ref=scope_ref,
        )
        if source_document["subspace"] != "raw":
            raise ValueError("source_document_ref.document_id must resolve to subspace 'raw'.")
        source_version = self._required_int(source_document_ref, "version")
        if source_document["version"] != source_version:
            raise ValueError(
                f"source_document_ref.version does not match the current stored version. Current version is {source_document['version']}."
            )

        declared_subspace = self._required_string(source_document_ref, "subspace")
        if declared_subspace != "raw":
            raise ValueError("source_document_ref.subspace must equal 'raw'.")

        save_target_subspace = self._required_string(save_target, "subspace")
        if save_target_subspace != "wiki":
            raise ValueError("save_target.subspace must equal 'wiki'.")

        snapshot_ref = self._current_snapshot_ref(domain=domain, profile_version=profile_version)
        generation = self._run_generation(
            operation=operation,
            source_document=source_document,
            snapshot_ref=snapshot_ref,
            model_profile=model_profile,
            instruction_value=instruction_value,
        )
        target_document_id = save_target.get("document_id")
        if target_document_id is None:
            document_id = self._new_document_id(subspace="wiki")
            version = 1
            body_path = self._body_path(scope_ref=scope_ref, subspace="wiki", title=generation["title"])
            existing_anchors: list[dict[str, str]] = []
        else:
            if not isinstance(target_document_id, str) or not target_document_id.strip():
                raise ValueError("save_target.document_id must be a non-empty string when provided.")
            target_document = self._load_document(
                domain=domain,
                document_id=target_document_id,
                scope_ref=scope_ref,
            )
            if target_document["subspace"] != "wiki":
                raise ValueError("save_target.document_id must resolve to subspace 'wiki'.")
            target_version = self._required_int(save_target, "version")
            if target_document["version"] != target_version:
                raise ValueError(
                    f"save_target.version does not match the current stored version. Current version is {target_document['version']}."
                )
            document_id = target_document_id
            version = target_document["version"] + 1
            body_path = target_document["body_path"]
            existing_anchors = list(target_document.get("anchors", []))

        kind = "wiki_summary" if operation == "summarize" else "wiki_note"
        anchors = self._dedupe_anchors([*source_document.get("anchors", []), *existing_anchors])
        source_assets = source_document.get("asset_refs", [])
        provenance = {
            "source_ids": [
                f"personal_document:{source_document['document_id']}",
                *[f"personal_asset:{asset_id}" for asset_id in source_assets],
            ],
            "upstream_versions": {
                "fact_snapshot": snapshot_ref["fact_snapshot_id"],
                **(
                    {"interpretation_snapshot": snapshot_ref["interpretation_snapshot_id"]}
                    if snapshot_ref.get("interpretation_snapshot_id")
                    else {}
                ),
                "profile_version": profile_version,
                "source_document_version": str(source_version),
            },
            "generated_by": {
                "kind": "llm",
                "provider": generation["provider"],
                "model": generation["model"],
                "prompt_version": generation["prompt_version"],
            },
            "generated_at": self._now_iso(),
        }
        document = {
            "document_id": document_id,
            "domain": domain,
            "subspace": "wiki",
            "kind": kind,
            "version": version,
            "title": generation["title"],
            "summary": self._summarize_markdown(generation["body_markdown"]),
            "body_markdown": generation["body_markdown"],
            "body_path": body_path,
            "scope_ref": scope_ref,
            "snapshot_ref": snapshot_ref,
            "profile_version": profile_version,
            "status": "active",
            "schema_version": "personal_document.v1",
            "anchors": anchors,
            "asset_refs": [],
            "source_document_ref": {
                "document_id": source_document["document_id"],
                "subspace": "raw",
                "version": source_document["version"],
                "kind": source_document.get("document_kind") or source_document.get("kind") or "raw_document",
                "asset_refs": source_assets,
            },
            "generation": {
                "generation_id": self._new_generation_id(),
                "operation": operation,
            },
            "provenance": provenance,
            "created_at": self._now_iso(),
            "updated_at": self._now_iso(),
        }
        self._persist_document(document)
        return {
            "status": "ok",
            "document": self._document_response(document),
        }

    def _run_generation(
        self,
        *,
        operation: str,
        source_document: dict[str, Any],
        snapshot_ref: dict[str, Any],
        model_profile: str,
        instruction_value: str,
    ) -> dict[str, str]:
        request = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You transform Personal raw notes into Personal wiki markdown. "
                        "Do not invent facts. Preserve source intent and make the result readable."
                    ),
                },
                {
                    "role": "user",
                    "content": self._render_generation_prompt(
                        operation=operation,
                        source_document=source_document,
                        snapshot_ref=snapshot_ref,
                        instruction_value=instruction_value,
                    ),
                },
            ],
            "model_profile": model_profile,
            "prompt_id": f"personal.raw_to_wiki.{operation}",
            "prompt_version": f"personal.raw_to_wiki.{operation}.v1",
        }
        response = self.llm_gateway.generate_text(request)
        body_markdown = self._normalize_generated_markdown(response["content"], source_document["title"])
        title = self._title_from_markdown(body_markdown) or self._generated_title(
            operation=operation,
            source_title=source_document["title"],
        )
        return {
            "title": title,
            "body_markdown": body_markdown,
            "provider": response["metadata"]["provider"],
            "model": response["metadata"]["model"],
            "prompt_version": response["metadata"]["prompt_version"],
        }

    def _render_generation_prompt(
        self,
        *,
        operation: str,
        source_document: dict[str, Any],
        snapshot_ref: dict[str, Any],
        instruction_value: str,
    ) -> str:
        operation_hint = {
            "summarize": f"Summarize the raw source into a concise wiki artifact. Style: {instruction_value}.",
            "rewrite": f"Rewrite the raw source into clearer wiki prose. Goal: {instruction_value}.",
            "structure": f"Restructure the raw source into stable wiki sections. Template: {instruction_value}.",
        }[operation]
        return "\n\n".join(
            [
                f"Operation:\n{operation}",
                f"Instruction:\n{operation_hint}",
                "Source Document Ref:\n"
                + json.dumps(
                    {
                        "document_id": source_document["document_id"],
                        "subspace": source_document["subspace"],
                        "version": source_document["version"],
                        "kind": source_document.get("document_kind") or source_document.get("kind"),
                        "asset_refs": source_document.get("asset_refs", []),
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                    indent=2,
                ),
                "Snapshot Ref:\n"
                + json.dumps(snapshot_ref, ensure_ascii=True, sort_keys=True, indent=2),
                "Source Anchors:\n"
                + json.dumps(source_document.get("anchors", []), ensure_ascii=True, sort_keys=True, indent=2),
                f"Source Title:\n{source_document['title']}",
                f"Source Body:\n{source_document['body_markdown']}",
                (
                    "Return markdown only. Prefer a concise heading and sections that remain readable as a Personal wiki note."
                ),
            ]
        )

    def _load_document(
        self,
        *,
        domain: str,
        document_id: str,
        scope_ref: ScopeRef,
    ) -> dict[str, Any]:
        records = self.personal_repository.get_by_ids([document_id], scope_ref)
        if not records:
            raise KeyError(f"Unknown personal document: {document_id}")
        record = dict(records[0])
        if record.get("domain") != domain:
            raise KeyError(f"Unknown personal document: {document_id}")
        body_path = str(record["body_path"])
        raw_body = self.rendering_repository.read_body(path=body_path, scope_ref=scope_ref)
        if raw_body is None:
            raise KeyError(f"Personal document body was not found for {document_id}.")
        metadata, body_markdown = self._parse_document_body(raw_body)
        subspace = str(metadata.get("subspace") or self._infer_subspace(record))
        version = int(metadata.get("version") or record.get("version") or 1)
        asset_refs = metadata.get("asset_refs")
        if not isinstance(asset_refs, list):
            asset_refs = []
        anchors = metadata.get("anchors")
        if not isinstance(anchors, list):
            anchors = list(record.get("anchors", []))
        document = {
            "document_id": str(metadata.get("document_id") or record["id"]),
            "domain": domain,
            "subspace": subspace,
            "kind": str(record.get("kind") or "personal_document"),
            "document_kind": str(metadata.get("kind") or record.get("kind") or "personal_document"),
            "version": version,
            "title": str(metadata.get("title") or record.get("title") or record["id"]),
            "summary": str(metadata.get("summary") or record.get("summary") or ""),
            "body_markdown": body_markdown,
            "body_path": body_path,
            "scope_ref": dict(record["scope_ref"]),
            "snapshot_ref": dict(record.get("snapshot_ref") or {}),
            "profile_version": str(record.get("profile_version") or metadata.get("profile_version") or ""),
            "status": str(record.get("status") or "active"),
            "schema_version": str(record.get("schema_version") or "personal_document.v1"),
            "anchors": self._normalize_attachments(anchors),
            "asset_refs": [str(item) for item in asset_refs if isinstance(item, str)],
            "source_document_ref": metadata.get("source_document_ref"),
            "generation": metadata.get("generation"),
            "provenance": dict(record.get("provenance") or {}),
        }
        return document

    def _persist_document(self, document: dict[str, Any]) -> None:
        metadata = {
            "document_id": document["document_id"],
            "domain": document["domain"],
            "subspace": document["subspace"],
            "kind": document.get("document_kind") or document["kind"],
            "version": document["version"],
            "title": document["title"],
            "summary": document["summary"],
            "profile_version": document["profile_version"],
            "asset_refs": document.get("asset_refs", []),
            "anchors": document.get("anchors", []),
            **(
                {"source_document_ref": document["source_document_ref"]}
                if document.get("source_document_ref") is not None
                else {}
            ),
            **({"generation": document["generation"]} if document.get("generation") is not None else {}),
        }
        artifact: RenderedArtifact = {
            "domain": str(document["domain"]),
            "layer": "personal",
            "record_id": str(document["document_id"]),
            "path": str(document["body_path"]),
            "title": str(document["title"]),
            "body_markdown": self._render_document_body(metadata, str(document["body_markdown"])),
            "scope_ref": document["scope_ref"],
            "snapshot_ref": document["snapshot_ref"],
        }
        persisted_body_path = self.rendering_repository.write_artifact(artifact)
        self.personal_repository.save_record(
            {
                "id": document["document_id"],
                "layer": "personal",
                "domain": document["domain"],
                "kind": document["kind"],
                "title": document["title"],
                "summary": document["summary"] or self._summarize_markdown(document["body_markdown"]),
                "scope_ref": document["scope_ref"],
                "snapshot_ref": document["snapshot_ref"],
                "profile_version": document["profile_version"],
                "body_path": persisted_body_path,
                "anchors": document.get("anchors", []),
                "status": document["status"],
                "schema_version": document["schema_version"],
                "provenance": document["provenance"],
            }
        )

    def _render_document_body(self, metadata: dict[str, Any], body_markdown: str) -> str:
        return (
            f"<!-- {self.document_marker}\n"
            + json.dumps(metadata, ensure_ascii=True, indent=2, sort_keys=True)
            + "\n-->\n\n"
            + body_markdown.rstrip()
            + "\n"
        )

    def _parse_document_body(self, raw_body: str) -> tuple[dict[str, Any], str]:
        match = re.search(
            rf"<!--\s*{self.document_marker}\s*(\{{.*?\}})\s*-->",
            raw_body,
            re.DOTALL,
        )
        if match is None:
            return {}, raw_body.strip()
        try:
            metadata = json.loads(match.group(1))
        except json.JSONDecodeError:
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        return metadata, raw_body[match.end():].lstrip("\n").rstrip()

    def _document_response(self, document: dict[str, Any]) -> dict[str, Any]:
        return {
            "document_id": document["document_id"],
            "subspace": document["subspace"],
            "kind": document["kind"],
            "version": document["version"],
            "title": document["title"],
            "source_document_ref": document.get("source_document_ref"),
            "snapshot_ref": document["snapshot_ref"],
            "anchors": document.get("anchors", []),
            "generation": document.get("generation"),
            "provenance": document["provenance"],
        }

    def _require_profile_context(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        profile_version: str,
    ) -> None:
        profile = self.profile_context_repository.get_profile_context(
            domain,
            str(scope_ref["tenant_id"]),
            str(scope_ref["user_id"]),
        )
        if profile["profile_version"] != profile_version:
            raise ValueError("Requested profile_version does not match the current stored profile context.")

    def _current_snapshot_ref(self, *, domain: str, profile_version: str) -> dict[str, str]:
        snapshot_status = self.snapshot_repository.get_snapshot_status(domain=domain, layer=None)
        if snapshot_status is None:
            raise KeyError(f"No published snapshot status exists for domain {domain!r}.")
        layers = snapshot_status.get("layers")
        if not isinstance(layers, dict):
            raise KeyError(f"No published snapshot status exists for domain {domain!r}.")
        fact_status = layers.get("fact")
        if not isinstance(fact_status, dict) or not isinstance(fact_status.get("fact_snapshot_id"), str):
            raise KeyError(f"No fact snapshot status exists for domain {domain!r}.")
        snapshot_ref = {
            "fact_snapshot_id": fact_status["fact_snapshot_id"],
            "profile_version": profile_version,
        }
        interpretation_status = layers.get("interpretation")
        if isinstance(interpretation_status, dict):
            interpretation_snapshot_id = interpretation_status.get("interpretation_snapshot_id")
            if isinstance(interpretation_snapshot_id, str) and interpretation_snapshot_id:
                snapshot_ref["interpretation_snapshot_id"] = interpretation_snapshot_id
        return snapshot_ref

    def _validate_shared_attachments(self, attachments: list[dict[str, str]]) -> None:
        interpretation_ids = [item["id"] for item in attachments if item["layer"] == "interpretation"]
        fact_ids = [item["id"] for item in attachments if item["layer"] == "fact"]
        if interpretation_ids:
            resolved = self.interpretation_repository.get_by_ids(interpretation_ids, {"scope": "shared"})
            resolved_ids = {str(item["id"]) for item in resolved}
            missing = [item for item in interpretation_ids if item not in resolved_ids]
            if missing:
                raise KeyError(f"Unknown interpretation attachment target: {missing[0]}")
        if fact_ids:
            resolved = self.fact_repository.get_by_ids(fact_ids, {"scope": "shared"})
            resolved_ids = {str(item["id"]) for item in resolved}
            missing = [item for item in fact_ids if item not in resolved_ids]
            if missing:
                raise KeyError(f"Unknown fact attachment target: {missing[0]}")

    def _normalize_attachments(self, attachments: list[dict[str, Any]]) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for raw in attachments:
            if not isinstance(raw, dict):
                raise ValueError("attachments must contain objects only.")
            layer = self._required_string(raw, "layer")
            if layer not in {"interpretation", "fact"}:
                raise ValueError("attachments.layer must be one of ['interpretation', 'fact'].")
            normalized.append(
                {
                    "layer": layer,
                    "id": self._required_string(raw, "id"),
                }
            )
        return self._dedupe_anchors(normalized)

    def _dedupe_anchors(self, anchors: list[dict[str, str]]) -> list[dict[str, str]]:
        seen: set[tuple[str, str]] = set()
        deduped: list[dict[str, str]] = []
        for anchor in anchors:
            key = (anchor["layer"], anchor["id"])
            if key in seen:
                continue
            deduped.append(anchor)
            seen.add(key)
        return deduped

    def _normalize_generated_markdown(self, content: str, source_title: str) -> str:
        normalized = content.strip()
        if normalized:
            return normalized
        return f"# {source_title}\n\nNo generated wiki content was returned."

    def _title_from_markdown(self, body_markdown: str) -> str | None:
        for line in body_markdown.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
        return None

    def _generated_title(self, *, operation: str, source_title: str) -> str:
        suffix = {
            "summarize": "Summary",
            "rewrite": "Wiki Note",
            "structure": "Structured Note",
        }[operation]
        return f"{source_title} {suffix}".strip()

    def _summarize_markdown(self, body_markdown: str) -> str:
        text = re.sub(r"\s+", " ", body_markdown.replace("#", " ")).strip()
        if len(text) <= 180:
            return text
        return text[:177].rstrip() + "..."

    def _infer_subspace(self, record: dict[str, Any]) -> str:
        kind = str(record.get("kind") or "")
        if kind.startswith("wiki_") or kind == "query_answer":
            return "wiki"
        return "raw"

    def _required_string(self, payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} is required.")
        return value.strip()

    def _required_int(self, payload: dict[str, Any], key: str) -> int:
        value = payload.get(key)
        if not isinstance(value, int):
            raise ValueError(f"{key} must be an integer.")
        return value

    def _new_document_id(self, *, subspace: str) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return f"personal:{subspace}:{timestamp}:{uuid4().hex[:8]}"

    def _new_generation_id(self) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return f"pgen:{timestamp}:{uuid4().hex[:8]}"

    def _body_path(self, *, scope_ref: ScopeRef, subspace: str, title: str) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        slug = self._slug(title) or "personal-document"
        return f"wiki/users/{scope_ref['user_id']}/documents/{subspace}/{timestamp}-{slug}.md"

    def _slug(self, text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]

    def _tokenize(self, text: str) -> list[str]:
        return [token for token in text.lower().split() if token]

    def _now_iso(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
