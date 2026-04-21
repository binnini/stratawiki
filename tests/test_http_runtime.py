from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from wiki_mcp.http_runtime import dispatch_http_request
from wiki_mcp.services import (
    PersonalAssetConflictError,
    PersonalAssetNotFoundError,
    PersonalAssetRegistrationService,
    PersonalAssetValidationError,
    PersonalDocumentConflictError,
    PersonalDocumentNotFoundError,
    PersonalDocumentValidationError,
)
from wiki_mcp.tools import ToolDefinition


class FakePersonalDocumentService:
    def __init__(self, server: "FakeHttpServer") -> None:
        self._server = server

    def list_documents(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        subspace: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> dict[str, object]:
        items = [
            dict(document)
            for (doc_domain, doc_tenant_id, doc_user_id, _), document in self._server.personal_documents.items()
            if doc_domain == domain and doc_tenant_id == tenant_id and doc_user_id == user_id
        ]
        if status is None:
            status = "active"
        items = [item for item in items if item.get("status") == status]
        if subspace is not None:
            items = [item for item in items if item.get("subspace") == subspace]
        if kind is not None:
            items = [item for item in items if item.get("kind") == kind]
        items.sort(key=lambda item: (str(item.get("updated_at")), str(item["document_id"])), reverse=True)
        return {"status": "ok", "items": items[:limit]}

    def get_document(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        document_id: str,
    ) -> dict[str, object]:
        document = self._server.personal_documents.get((domain, tenant_id, user_id, document_id))
        if document is None:
            raise PersonalDocumentNotFoundError(
                f"Unknown Personal document: {document_id}",
                details={"resource": "personal_document", "document_id": document_id},
            )
        return {"status": "ok", "document": dict(document)}

    def create_document(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        profile_version: str,
        subspace: str,
        kind: str,
        title: str,
        body_markdown: str | None,
        asset_refs: list[str] | None,
        anchors: list[dict[str, str]] | None,
    ) -> dict[str, object]:
        if (domain, tenant_id, user_id) not in self._server.profile_contexts:
            raise PersonalDocumentValidationError(
                "Personal document writes require an existing stored profile context.",
                details={"domain": domain, "tenant_id": tenant_id, "user_id": user_id},
            )
        if not body_markdown and not asset_refs:
            raise PersonalDocumentValidationError(
                "Personal documents require body_markdown or non-empty asset_refs.",
                details={"invalid_fields": ["body_markdown", "asset_refs"]},
            )
        document_id = f"pdoc_{len(self._server.personal_documents) + 1}"
        document = {
            "document_id": document_id,
            "domain": domain,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "subspace": subspace,
            "kind": kind,
            "title": title,
            "body_markdown": body_markdown or "",
            "asset_refs": list(asset_refs or []),
            "anchors": list(anchors or []),
            "based_on": {
                "fact_snapshot_id": "fact_snap:seed",
                "interpretation_snapshot_id": "interp_snap:seed",
                "profile_version": profile_version,
            },
            "provenance": {"generated_by": {"kind": "user"}},
            "status": "active",
            "version": 1,
            "created_at": "2026-04-20T00:00:00Z",
            "updated_at": "2026-04-20T00:00:00Z",
        }
        self._server.personal_documents[(domain, tenant_id, user_id, document_id)] = document
        return {"status": "ok", "document": dict(document)}

    def update_document(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        document_id: str,
        profile_version: str,
        if_version: int,
        title: str | None = None,
        body_markdown: str | None = None,
        anchors: list[dict[str, str]] | None = None,
        asset_refs: list[str] | None = None,
        status: str | None = None,
    ) -> dict[str, object]:
        document = self._server.personal_documents.get((domain, tenant_id, user_id, document_id))
        if document is None:
            raise PersonalDocumentNotFoundError(
                f"Unknown Personal document: {document_id}",
                details={"resource": "personal_document", "document_id": document_id},
            )
        if document["status"] == "deleted":
            raise PersonalDocumentValidationError(
                "Deleted Personal documents cannot be updated.",
                details={"resource": "personal_document", "document_id": document_id},
            )
        if if_version != document["version"]:
            raise PersonalDocumentConflictError(
                "Personal document version mismatch.",
                details={
                    "resource": "personal_document",
                    "document_id": document_id,
                    "expected_version": if_version,
                    "current_version": document["version"],
                },
            )
        if title is None and body_markdown is None and anchors is None and asset_refs is None and status is None:
            raise PersonalDocumentValidationError(
                "update_personal_document requires at least one mutable field.",
                details={"invalid_fields": ["title", "body_markdown", "anchors", "asset_refs", "status"]},
            )
        if title is not None:
            document["title"] = title
        if body_markdown is not None:
            document["body_markdown"] = body_markdown
        if anchors is not None:
            document["anchors"] = list(anchors)
        if asset_refs is not None:
            document["asset_refs"] = list(asset_refs)
        if status is not None:
            document["status"] = status
        document["version"] += 1
        document["updated_at"] = "2026-04-20T00:05:00Z"
        return {"status": "ok", "document": dict(document)}

    def delete_document(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        document_id: str,
        if_version: int,
    ) -> dict[str, object]:
        document = self._server.personal_documents.get((domain, tenant_id, user_id, document_id))
        if document is None:
            raise PersonalDocumentNotFoundError(
                f"Unknown Personal document: {document_id}",
                details={"resource": "personal_document", "document_id": document_id},
            )
        if if_version != document["version"]:
            raise PersonalDocumentConflictError(
                "Personal document version mismatch.",
                details={
                    "resource": "personal_document",
                    "document_id": document_id,
                    "expected_version": if_version,
                    "current_version": document["version"],
                },
            )
        document["status"] = "deleted"
        document["version"] += 1
        document["updated_at"] = "2026-04-20T00:10:00Z"
        return {"status": "ok", "document": dict(document)}


class _FakeProfileContextRepository:
    def __init__(self, server: "FakeHttpServer") -> None:
        self.server = server

    def get_profile_context(self, domain: str, tenant_id: str, user_id: str) -> dict[str, object]:
        profile = self.server.profile_contexts.get((domain, tenant_id, user_id))
        if profile is None:
            raise KeyError("missing profile context")
        return profile


class _FakePersonalAssetRepository:
    def __init__(self, server: "FakeHttpServer") -> None:
        self.server = server
        self.records: dict[str, dict[str, object]] = {}
        self.identity_to_asset_id: dict[str, str] = {}

    def create_record(self, record: dict[str, object]) -> dict[str, object]:
        identity_key = str(record["identity_key"])
        existing_id = self.identity_to_asset_id.get(identity_key)
        if existing_id is not None:
            raise PersonalAssetConflictError(
                "Personal asset is already registered for this user scope.",
                details={"asset_id": existing_id},
            )
        asset_id = str(record["asset_id"])
        stored = dict(record)
        self.identity_to_asset_id[identity_key] = asset_id
        self.records[asset_id] = stored
        return stored


class FakeHttpServer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.bootstrap: Any | None = None
        self.profile_contexts: dict[tuple[str, str, str], dict[str, object]] = {}
        self.personal_documents: dict[tuple[str, str, str, str], dict[str, object]] = {}
        self.personal_assets: dict[tuple[str, str, str, str], dict[str, object]] = {}
        self.bootstrap = SimpleNamespace(
            personal_document_service=FakePersonalDocumentService(self),
            personal_asset_registration_service=PersonalAssetRegistrationService(
                asset_repository=_FakePersonalAssetRepository(self),
                profile_context_repository=_FakeProfileContextRepository(self),
            )
        )
        self._tools = [
            ToolDefinition(
                name="validate_domain_proposal_batch",
                group="fact",
                status="mvp",
                description="Validate one proposal batch.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["batch"],
                    "properties": {"batch": {"type": "object"}},
                },
            ),
            ToolDefinition(
                name="ingest_domain_proposal_batch",
                group="fact",
                status="mvp",
                description="Ingest one proposal batch.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["batch"],
                    "properties": {"batch": {"type": "object"}},
                },
            ),
            ToolDefinition(
                name="upsert_profile_context",
                group="personal",
                status="mvp",
                description="Upsert one profile context.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": [
                        "domain",
                        "tenant_id",
                        "user_id",
                        "profile_version",
                        "goals",
                        "preferences",
                        "attributes",
                    ],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="register_personal_asset",
                group="personal",
                status="mvp",
                description="Register one personal asset.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": [
                        "domain",
                        "tenant_id",
                        "user_id",
                        "asset_kind",
                        "media_type",
                        "filename",
                        "storage_ref",
                    ],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="query_personal_knowledge",
                group="personal",
                status="mvp",
                description="Run a Personal query.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": [
                        "domain",
                        "tenant_id",
                        "user_id",
                        "question",
                        "profile_version",
                        "model_profile",
                    ],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="list_personal_documents",
                group="personal",
                status="mvp",
                description="List Personal documents.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["domain", "tenant_id", "user_id"],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="get_personal_document",
                group="personal",
                status="mvp",
                description="Get one Personal document.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["domain", "tenant_id", "user_id", "document_id"],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="create_personal_document",
                group="personal",
                status="mvp",
                description="Create one Personal document.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["domain", "tenant_id", "user_id", "profile_version", "subspace", "kind", "title"],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="update_personal_document",
                group="personal",
                status="mvp",
                description="Update one Personal document.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["domain", "tenant_id", "user_id", "document_id", "profile_version", "if_version"],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="delete_personal_document",
                group="personal",
                status="mvp",
                description="Delete one Personal document.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["domain", "tenant_id", "user_id", "document_id", "if_version"],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="summarize_personal_document_to_wiki",
                group="personal",
                status="mvp",
                description="Summarize one Personal raw document into a Personal wiki document.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["domain", "tenant_id", "user_id", "source_document_ref", "profile_version", "model_profile", "save_target"],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="rewrite_personal_document_to_wiki",
                group="personal",
                status="mvp",
                description="Rewrite one Personal raw document into a Personal wiki document.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["domain", "tenant_id", "user_id", "source_document_ref", "profile_version", "model_profile", "save_target"],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="structure_personal_document_to_wiki",
                group="personal",
                status="mvp",
                description="Structure one Personal raw document into a Personal wiki document.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["domain", "tenant_id", "user_id", "source_document_ref", "profile_version", "model_profile", "save_target"],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="suggest_personal_wiki_links",
                group="personal",
                status="mvp",
                description="Suggest links for one Personal wiki document.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["domain", "tenant_id", "user_id", "wiki_document_id", "wiki_document_version", "profile_version", "model_profile"],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="attach_personal_wiki_links",
                group="personal",
                status="mvp",
                description="Attach links to one Personal wiki document.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["domain", "tenant_id", "user_id", "wiki_document_id", "wiki_document_version", "attachments"],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="build_interpretation_snapshot",
                group="interpretation",
                status="mvp",
                description="Build one interpretation snapshot.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["domain", "partition", "fact_ids"],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="get_snapshot_status",
                group="snapshot",
                status="mvp",
                description="Return snapshot pointers.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["domain"],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="get_cache_status",
                group="snapshot",
                status="mvp",
                description="Return cache status for one personal record.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["domain", "tenant_id", "user_id", "record_id"],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="get_job_status",
                group="operator",
                status="mvp",
                description="Return status for one queued background job.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["job_id"],
                    "properties": {"job_id": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="explain_result",
                group="operator",
                status="mvp",
                description="Explain one interpretation or personal result.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["domain", "result_id"],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="explode",
                group="admin",
                status="mvp",
                description="Raise an internal error.",
                entrypoint="server.call_tool",
                input_schema={"type": "object", "properties": {}},
            ),
        ]

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools)

    def export_tool_schemas(self) -> list[dict[str, object]]:
        return [tool.export_schema() for tool in self._tools]

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> dict[str, Any]:
        payload = dict(arguments or {})
        self.calls.append((name, payload))
        if name == "validate_domain_proposal_batch":
            batch = payload.get("batch")
            if not isinstance(batch, dict):
                raise ValueError("batch is required")
            return {
                "ok": True,
                "committed": False,
                "audit": {
                    "evaluated_pack_version": batch.get("pack_version") or "2026-04-18",
                },
            }
        if name == "ingest_domain_proposal_batch":
            batch = payload.get("batch")
            if not isinstance(batch, dict):
                raise ValueError("batch is required")
            return {
                "ok": True,
                "committed": True,
                "affected_fact_ids": ["fact:job_posting:EMP-1"],
                "audit": {
                    "evaluated_pack_version": batch.get("pack_version") or "2026-04-18",
                },
            }
        if name == "upsert_profile_context":
            domain = payload.get("domain")
            tenant_id = payload.get("tenant_id")
            user_id = payload.get("user_id")
            profile_version = payload.get("profile_version")
            if not isinstance(domain, str) or not domain.strip():
                raise ValueError("domain is required")
            if not isinstance(tenant_id, str) or not tenant_id.strip():
                raise ValueError("tenant_id is required")
            if not isinstance(user_id, str) or not user_id.strip():
                raise ValueError("user_id is required")
            if not isinstance(profile_version, str) or not profile_version.strip():
                raise ValueError("profile_version is required")
            record = dict(payload)
            self.profile_contexts[(domain, tenant_id, user_id)] = record
            return {"status": "ok", "profile_context": record}
        if name == "query_personal_knowledge":
            domain = payload.get("domain")
            tenant_id = payload.get("tenant_id")
            user_id = payload.get("user_id")
            profile_version = payload.get("profile_version")
            question = payload.get("question")
            model_profile = payload.get("model_profile")
            if not isinstance(domain, str) or not domain.strip():
                raise ValueError("domain is required")
            if not isinstance(tenant_id, str) or not tenant_id.strip():
                raise ValueError("tenant_id is required")
            if not isinstance(user_id, str) or not user_id.strip():
                raise ValueError("user_id is required")
            if not isinstance(profile_version, str) or not profile_version.strip():
                raise ValueError("profile_version is required")
            if not isinstance(question, str) or not question.strip():
                raise ValueError("question is required")
            if not isinstance(model_profile, str) or not model_profile.strip():
                raise ValueError("model_profile is required")
            profile = self.profile_contexts.get((domain, tenant_id, user_id))
            if profile is None:
                raise KeyError("No profile context found.")
            if profile.get("profile_version") != profile_version:
                raise ValueError("Requested profile_version does not match the current stored profile context.")
            return {
                "status": "ok",
                "answer_markdown": f"## Strategy\n\nAnswer for: {question}",
                "personal_records_used": [],
                "interpretation_records_used": [],
                "fact_records_used": [],
                "provenance": {
                    "model_profile": model_profile,
                    "profile_version": profile_version,
                },
            }
        if name == "create_personal_document":
            domain = payload.get("domain")
            tenant_id = payload.get("tenant_id")
            user_id = payload.get("user_id")
            profile_version = payload.get("profile_version")
            title = payload.get("title")
            if not all(isinstance(value, str) and value.strip() for value in (domain, tenant_id, user_id, profile_version, title)):
                raise ValueError("domain, tenant_id, user_id, profile_version, and title are required")
            profile = self.profile_contexts.get((domain, tenant_id, user_id))
            if profile is None:
                error = Exception("Personal document writes require an existing stored profile context.")
                error.code = "validation_error"  # type: ignore[attr-defined]
                error.status_code = 422  # type: ignore[attr-defined]
                error.details = {"domain": domain, "tenant_id": tenant_id, "user_id": user_id}  # type: ignore[attr-defined]
                raise error
            document_id = f"pdoc_{len(self.personal_documents) + 1}"
            document = {
                "document_id": document_id,
                "domain": domain,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "subspace": payload.get("subspace") or "raw",
                "kind": payload.get("kind") or "note",
                "title": title,
                "body_markdown": payload.get("body_markdown") or "",
                "asset_refs": list(payload.get("asset_refs") or []),
                "anchors": list(payload.get("anchors") or []),
                "based_on": {
                    "fact_snapshot_id": "fact_snap:seed",
                    "interpretation_snapshot_id": "interp_snap:seed",
                    "profile_version": profile_version,
                },
                "provenance": {"generated_by": {"kind": "user"}},
                "status": "active",
                "version": 1,
                "created_at": "2026-04-20T00:00:00Z",
                "updated_at": "2026-04-20T00:00:00Z",
            }
            self.personal_documents[(domain, tenant_id, user_id, document_id)] = document
            return {"status": "ok", "document": dict(document)}
        if name == "get_personal_document":
            key = (
                payload.get("domain"),
                payload.get("tenant_id"),
                payload.get("user_id"),
                payload.get("document_id"),
            )
            document = self.personal_documents.get(key)
            if document is None:
                raise KeyError("Unknown Personal document.")
            return {"status": "ok", "document": dict(document)}
        if name == "list_personal_documents":
            domain = payload.get("domain")
            tenant_id = payload.get("tenant_id")
            user_id = payload.get("user_id")
            items = [
                dict(document)
                for (doc_domain, doc_tenant_id, doc_user_id, _), document in self.personal_documents.items()
                if doc_domain == domain and doc_tenant_id == tenant_id and doc_user_id == user_id
            ]
            status = payload.get("status") or "active"
            subspace = payload.get("subspace")
            if isinstance(status, str):
                items = [item for item in items if item.get("status") == status]
            if isinstance(subspace, str):
                items = [item for item in items if item.get("subspace") == subspace]
            items.sort(key=lambda item: (str(item.get("updated_at")), str(item["document_id"])), reverse=True)
            return {"status": "ok", "items": items}
        if name == "update_personal_document":
            key = (
                payload.get("domain"),
                payload.get("tenant_id"),
                payload.get("user_id"),
                payload.get("document_id"),
            )
            document = self.personal_documents.get(key)
            if document is None:
                raise KeyError("Unknown Personal document.")
            if payload.get("if_version") != document["version"]:
                error = Exception("Personal document version mismatch.")
                error.code = "conflict"  # type: ignore[attr-defined]
                error.status_code = 409  # type: ignore[attr-defined]
                error.details = {  # type: ignore[attr-defined]
                    "resource": "personal_document",
                    "document_id": document["document_id"],
                    "expected_version": payload.get("if_version"),
                    "current_version": document["version"],
                }
                raise error
            for field in ("title", "body_markdown", "status"):
                if field in payload:
                    document[field] = payload[field]
            if "asset_refs" in payload:
                document["asset_refs"] = list(payload["asset_refs"])
            if "anchors" in payload:
                document["anchors"] = list(payload["anchors"])
            document["version"] += 1
            document["updated_at"] = "2026-04-20T00:05:00Z"
            return {"status": "ok", "document": dict(document)}
        if name == "delete_personal_document":
            key = (
                payload.get("domain"),
                payload.get("tenant_id"),
                payload.get("user_id"),
                payload.get("document_id"),
            )
            document = self.personal_documents.get(key)
            if document is None:
                raise KeyError("Unknown Personal document.")
            if payload.get("if_version") != document["version"]:
                error = Exception("Personal document version mismatch.")
                error.code = "conflict"  # type: ignore[attr-defined]
                error.status_code = 409  # type: ignore[attr-defined]
                error.details = {  # type: ignore[attr-defined]
                    "resource": "personal_document",
                    "document_id": document["document_id"],
                    "expected_version": payload.get("if_version"),
                    "current_version": document["version"],
                }
                raise error
            document["status"] = "deleted"
            document["version"] += 1
            document["updated_at"] = "2026-04-20T00:10:00Z"
            return {"status": "ok", "document": dict(document)}
        if name in {
            "summarize_personal_document_to_wiki",
            "rewrite_personal_document_to_wiki",
            "structure_personal_document_to_wiki",
        }:
            source_document_ref = payload.get("source_document_ref")
            if not isinstance(source_document_ref, dict):
                raise ValueError("source_document_ref is required")
            return {
                "status": "ok",
                "document": {
                    "document_id": "personal:wiki:1",
                    "subspace": "wiki",
                    "version": 1,
                    "source_document_ref": dict(source_document_ref),
                },
            }
        if name == "suggest_personal_wiki_links":
            return {
                "status": "ok",
                "wiki_document_id": payload.get("wiki_document_id"),
                "wiki_document_version": payload.get("wiki_document_version"),
                "suggestions": [{"layer": "fact", "id": "fact:job:1"}],
            }
        if name == "attach_personal_wiki_links":
            return {
                "status": "ok",
                "wiki_document_id": payload.get("wiki_document_id"),
                "wiki_document_version": int(payload.get("wiki_document_version") or 0) + 1,
                "attachments": list(payload.get("attachments") or []),
            }
        if name == "register_personal_asset":
            domain = payload.get("domain")
            tenant_id = payload.get("tenant_id")
            user_id = payload.get("user_id")
            storage_ref = payload.get("storage_ref")
            if not isinstance(domain, str) or not domain.strip():
                raise PersonalAssetValidationError("domain is required")
            if not isinstance(tenant_id, str) or not tenant_id.strip():
                raise PersonalAssetValidationError("tenant_id is required")
            if not isinstance(user_id, str) or not user_id.strip():
                raise PersonalAssetValidationError("user_id is required")
            if (domain, tenant_id, user_id) not in self.profile_contexts:
                raise PersonalAssetNotFoundError(
                    "Referenced user scope does not exist.",
                    details={"domain": domain, "tenant_id": tenant_id, "user_id": user_id},
                )
            if not isinstance(storage_ref, str) or "://" not in storage_ref:
                raise PersonalAssetValidationError(
                    "storage_ref must be an absolute opaque locator.",
                    details={"fields": [{"field": "storage_ref", "reason": "invalid_storage_ref"}]},
                )
            asset_key = (domain, tenant_id, user_id, storage_ref)
            if asset_key in self.personal_assets:
                existing = self.personal_assets[asset_key]
                raise PersonalAssetConflictError(
                    "Personal asset is already registered for this user scope.",
                    details={"asset_id": existing["asset_id"]},
                )
            record = {
                "asset_id": "passet_http_123",
                "domain": domain,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "asset_kind": payload.get("asset_kind"),
                "media_type": payload.get("media_type"),
                "filename": payload.get("filename"),
                "storage_ref": storage_ref,
                "status": "active",
                "extraction_status": "not_requested",
            }
            self.personal_assets[asset_key] = record
            return {"status": "ok", "asset_id": record["asset_id"], "asset": record}
        if name == "build_interpretation_snapshot":
            execution_mode = payload.get("execution_mode") or "inline"
            if execution_mode == "background":
                return {
                    "status": "queued",
                    "execution_mode": "background",
                    "job_id": "job-123",
                    "event_id": "job-123",
                    "event_type": "interpretation_snapshot_build_requested",
                }
            return {
                "status": "ok",
                "interpretation_snapshot": "interp_snap:seed",
                "records_created": 1,
                "records_updated": 0,
                "records_superseded": 0,
            }
        if name == "get_snapshot_status":
            domain = payload.get("domain")
            if not isinstance(domain, str) or not domain.strip():
                raise ValueError("domain is required")
            if isinstance(payload.get("partition"), dict):
                return {
                    "status": "ok",
                    "fact_snapshot": "fact_snap:seed",
                    "interpretation_snapshot": "interp_snap:seed",
                    "published_at": "2026-04-19T08:00:00Z",
                }
            return {
                "status": "ok",
                "fact_snapshot": "fact_snap:seed",
                "interpretation_snapshot": "interp_snap:seed",
                "layers": {
                    "fact": {
                        "layer": "fact",
                        "current_snapshot_id": "fact_snap:seed",
                        "fact_snapshot_id": "fact_snap:seed",
                    },
                    "interpretation": {
                        "layer": "interpretation",
                        "current_snapshot_id": "interp_snap:seed",
                        "fact_snapshot_id": "fact_snap:seed",
                        "interpretation_snapshot_id": "interp_snap:seed",
                    },
                },
            }
        if name == "get_cache_status":
            return {
                "status": "ok",
                "record_id": payload.get("record_id"),
                "cache_state": "fresh",
                "change_reason": "current_result",
            }
        if name == "get_job_status":
            job_id = payload.get("job_id")
            if not isinstance(job_id, str) or not job_id.strip():
                raise ValueError("job_id is required")
            if job_id != "job-123":
                raise KeyError(f"Unknown job: {job_id}")
            return {
                "status": "ok",
                "job": {
                    "job_id": "job-123",
                    "state": "pending",
                    "kind": "interpretation_build",
                    "event_type": "interpretation_snapshot_build_requested",
                    "aggregate_layer": "interpretation",
                    "aggregate_id": "recruiting:market_trend:backend-japan-midlevel",
                    "attempt_count": 0,
                    "available_at": "2026-04-19T08:00:00Z",
                    "claimed_at": None,
                    "processed_at": None,
                    "last_error": None,
                    "payload": {
                        "partition": {"family": "market_trend", "segment": "backend-japan-midlevel"},
                    },
                },
            }
        if name == "explain_result":
            layer = payload.get("layer")
            if layer == "personal":
                return {
                    "status": "ok",
                    "layer": "personal",
                    "explanation": {
                        "cache_state": "fresh",
                        "change_reason": "current_result",
                        "anchors": ["interp:published:1", "fact:job:1"],
                    },
                }
            return {
                "status": "ok",
                "layer": "interpretation",
                "explanation": {
                    "change_reason": "current_result",
                    "review_state": "published",
                    "anchors": ["fact:job:1"],
                },
            }
        if name == "explode":
            raise RuntimeError("boom")
        raise KeyError(f"Unknown tool: {name}")


class FakePersonalGenerationService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.documents: dict[str, dict[str, object]] = {
            "personal:wiki:1": {
                "document_id": "personal:wiki:1",
                "subspace": "wiki",
                "version": 3,
                "anchors": [
                    {"layer": "interpretation", "id": "interp:published:1"},
                    {"layer": "fact", "id": "fact:job:1"},
                ],
                "provenance": {"generated_by": {"kind": "llm"}},
            }
        }

    def summarize_personal_document_to_wiki(
        self,
        *,
        domain: str,
        scope_ref: dict[str, object],
        source_document_ref: dict[str, object],
        profile_version: str,
        model_profile: str,
        save_target: dict[str, object],
        summary_style: str,
    ) -> dict[str, object]:
        self.calls.append(
            (
                "summarize_personal_document_to_wiki",
                {
                    "domain": domain,
                    "scope_ref": dict(scope_ref),
                    "source_document_ref": dict(source_document_ref),
                    "profile_version": profile_version,
                    "model_profile": model_profile,
                    "save_target": dict(save_target),
                    "summary_style": summary_style,
                },
            )
        )
        document = {
            "document_id": "personal:wiki:generated",
            "domain": domain,
            "subspace": "wiki",
            "version": 1,
            "source_document_ref": dict(source_document_ref),
            "provenance": {
                "generated_by": {"kind": "llm"},
                "source_ids": ["personal_document:personal:raw:1"],
            },
        }
        self.documents[document["document_id"]] = document
        return {"status": "ok", "document": document}

    def rewrite_personal_document_to_wiki(
        self,
        *,
        domain: str,
        scope_ref: dict[str, object],
        source_document_ref: dict[str, object],
        profile_version: str,
        model_profile: str,
        save_target: dict[str, object],
        rewrite_goal: str,
    ) -> dict[str, object]:
        self.calls.append(
            (
                "rewrite_personal_document_to_wiki",
                {
                    "domain": domain,
                    "scope_ref": dict(scope_ref),
                    "source_document_ref": dict(source_document_ref),
                    "profile_version": profile_version,
                    "model_profile": model_profile,
                    "save_target": dict(save_target),
                    "rewrite_goal": rewrite_goal,
                },
            )
        )
        document = {
            "document_id": "personal:wiki:generated",
            "domain": domain,
            "subspace": "wiki",
            "version": 1,
            "source_document_ref": dict(source_document_ref),
            "provenance": {"generated_by": {"kind": "llm"}},
        }
        self.documents[document["document_id"]] = document
        return {"status": "ok", "document": document}

    def structure_personal_document_to_wiki(
        self,
        *,
        domain: str,
        scope_ref: dict[str, object],
        source_document_ref: dict[str, object],
        profile_version: str,
        model_profile: str,
        save_target: dict[str, object],
        structure_template: str,
    ) -> dict[str, object]:
        self.calls.append(
            (
                "structure_personal_document_to_wiki",
                {
                    "domain": domain,
                    "scope_ref": dict(scope_ref),
                    "source_document_ref": dict(source_document_ref),
                    "profile_version": profile_version,
                    "model_profile": model_profile,
                    "save_target": dict(save_target),
                    "structure_template": structure_template,
                },
            )
        )
        document = {
            "document_id": "personal:wiki:generated",
            "domain": domain,
            "subspace": "wiki",
            "version": 1,
            "source_document_ref": dict(source_document_ref),
            "provenance": {"generated_by": {"kind": "llm"}},
        }
        self.documents[document["document_id"]] = document
        return {"status": "ok", "document": document}

    def suggest_personal_wiki_links(
        self,
        *,
        domain: str,
        scope_ref: dict[str, object],
        wiki_document_id: str,
        wiki_document_version: int,
        profile_version: str,
        model_profile: str,
        max_suggestions: int,
    ) -> dict[str, object]:
        self.calls.append(
            (
                "suggest_personal_wiki_links",
                {
                    "domain": domain,
                    "scope_ref": dict(scope_ref),
                    "wiki_document_id": wiki_document_id,
                    "wiki_document_version": wiki_document_version,
                    "profile_version": profile_version,
                    "model_profile": model_profile,
                    "max_suggestions": max_suggestions,
                },
            )
        )
        document = self.documents.get(wiki_document_id)
        if document is None:
            raise KeyError("Unknown Personal wiki document.")
        if wiki_document_version != document["version"]:
            raise ValueError(
                f"wiki_document_version does not match the current stored version. Current version is {document['version']}."
            )
        return {
            "status": "ok",
            "wiki_document_id": wiki_document_id,
            "wiki_document_version": wiki_document_version,
            "suggestions": [{"layer": "fact", "id": "fact:job:1"}],
        }

    def attach_personal_wiki_links(
        self,
        *,
        domain: str,
        scope_ref: dict[str, object],
        wiki_document_id: str,
        wiki_document_version: int,
        attachments: list[dict[str, object]],
    ) -> dict[str, object]:
        self.calls.append(
            (
                "attach_personal_wiki_links",
                {
                    "domain": domain,
                    "scope_ref": dict(scope_ref),
                    "wiki_document_id": wiki_document_id,
                    "wiki_document_version": wiki_document_version,
                    "attachments": [dict(item) for item in attachments],
                },
            )
        )
        document = self.documents.get(wiki_document_id)
        if document is None:
            raise KeyError("Unknown Personal wiki document.")
        if wiki_document_version != document["version"]:
            raise ValueError(
                f"wiki_document_version does not match the current stored version. Current version is {document['version']}."
            )
        document["anchors"] = [*document.get("anchors", []), *attachments]
        document["version"] = int(document["version"]) + 1
        return {
            "status": "ok",
            "wiki_document_id": wiki_document_id,
            "wiki_document_version": document["version"],
            "attached": [dict(item) for item in attachments],
        }


def test_http_runtime_health_and_readiness_return_success_envelopes() -> None:
    fake_server = FakeHttpServer()

    health = dispatch_http_request(
        fake_server,
        method="GET",
        path="/healthz",
        headers={"X-Request-Id": "req-health"},
        body=b"",
    )
    ready = dispatch_http_request(
        fake_server,
        method="GET",
        path="/readyz",
        headers={"X-Request-Id": "req-ready"},
        body=b"",
        ready_payload={"status": "ok", "bootstrap_tables_checked": True},
    )

    assert health.status_code == 200
    assert health.payload["ok"] is True
    assert health.payload["request_id"] == "req-health"
    assert health.payload["result"]["runtime"] == "stratawiki-http"
    assert health.headers["X-Request-Id"] == "req-health"

    assert ready.status_code == 200
    assert ready.payload["ok"] is True
    assert ready.payload["request_id"] == "req-ready"
    assert ready.payload["result"]["status"] == "ready"
    assert ready.payload["result"]["checks"]["bootstrap_tables_checked"] is True


def test_http_runtime_lists_tools_and_shows_one_tool() -> None:
    fake_server = FakeHttpServer()

    list_response = dispatch_http_request(
        fake_server,
        method="GET",
        path="/api/v1/tools",
        headers={},
        body=b"",
    )
    show_response = dispatch_http_request(
        fake_server,
        method="GET",
        path="/api/v1/tools/get_snapshot_status",
        headers={},
        body=b"",
    )

    assert list_response.status_code == 200
    assert list_response.payload["ok"] is True
    tool_names = [tool["name"] for tool in list_response.payload["result"]]
    assert "get_snapshot_status" in tool_names

    assert show_response.status_code == 200
    assert show_response.payload["ok"] is True
    assert show_response.payload["result"]["name"] == "get_snapshot_status"


def test_http_runtime_executes_tool_call_and_propagates_request_id() -> None:
    fake_server = FakeHttpServer()

    response = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/tool-calls",
        headers={"X-Request-Id": "req-123"},
        body=b'{"name":"get_snapshot_status","arguments":{"domain":"recruiting"}}',
    )

    assert response.status_code == 200
    assert response.payload["ok"] is True
    assert response.payload["request_id"] == "req-123"
    assert response.payload["result"]["status"] == "ok"
    assert response.payload["result"]["fact_snapshot"] == "fact_snap:seed"
    assert response.payload["result"]["interpretation_snapshot"] == "interp_snap:seed"
    assert response.headers["X-Request-Id"] == "req-123"
    assert fake_server.calls == [("get_snapshot_status", {"domain": "recruiting"})]


def test_http_runtime_submits_and_polls_commands() -> None:
    fake_server = FakeHttpServer()

    submitted = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/commands",
        headers={"X-Request-Id": "req-command", "Idempotency-Key": "cmd-key-1"},
        body=b'{"name":"get_snapshot_status","arguments":{"domain":"recruiting"}}',
    )
    command_id = submitted.payload["result"]["command_id"]
    fetched = dispatch_http_request(
        fake_server,
        method="GET",
        path=f"/api/v1/commands/{command_id}",
        headers={"X-Request-Id": "req-command-status"},
        body=b"",
    )
    repeated = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/commands",
        headers={"X-Request-Id": "req-command-retry", "Idempotency-Key": "cmd-key-1"},
        body=b'{"name":"get_snapshot_status","arguments":{"domain":"recruiting"}}',
    )
    queued = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/commands",
        headers={"X-Request-Id": "req-command-queued"},
        body=(
            b'{"name":"build_interpretation_snapshot","arguments":{"domain":"recruiting",'
            b'"partition":{"family":"market_trends","segment":"backend-japan-midlevel"},'
            b'"fact_ids":["fact:job:1"],"fact_snapshot":"fact_snap:seed","model_profile":"balanced_default",'
            b'"publish":true,"execution_mode":"background"}}'
        ),
    )

    assert submitted.status_code == 201
    assert submitted.payload["ok"] is True
    assert submitted.payload["request_id"] == "req-command"
    assert submitted.payload["result"]["state"] == "succeeded"
    assert submitted.payload["result"]["terminal"] is True
    assert submitted.payload["result"]["result"]["status"] == "ok"
    assert submitted.headers["Location"] == f"/api/v1/commands/{command_id}"

    assert fetched.status_code == 200
    assert fetched.payload["result"]["command"]["command_id"] == command_id
    assert fetched.payload["result"]["command"]["state"] == "succeeded"
    assert fetched.payload["result"]["command"]["request"]["name"] == "get_snapshot_status"

    assert repeated.status_code == 201
    assert repeated.payload["result"]["command_id"] == command_id

    assert queued.status_code == 202
    assert queued.payload["result"]["state"] == "queued"
    assert queued.payload["result"]["terminal"] is False
    assert queued.payload["result"]["job"]["job_id"] == "job-123"
    assert queued.headers["Retry-After"] == "1"


def test_http_runtime_normalizes_command_failures() -> None:
    fake_server = FakeHttpServer()

    failed = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/commands",
        headers={"X-Request-Id": "req-command-failed"},
        body=b'{"name":"explode","arguments":{}}',
    )
    command_id = failed.payload["result"]["command_id"]
    fetched = dispatch_http_request(
        fake_server,
        method="GET",
        path=f"/api/v1/commands/{command_id}",
        headers={},
        body=b"",
    )

    assert failed.status_code == 201
    assert failed.payload["result"]["state"] == "failed"
    assert failed.payload["result"]["terminal"] is True
    assert failed.payload["result"]["retryable"] is True
    assert failed.payload["result"]["error"]["code"] == "internal_error"
    assert fetched.payload["result"]["command"]["state"] == "failed"
    assert fetched.payload["result"]["command"]["retryable"] is True


def test_http_runtime_exposes_domain_proposal_validate_and_ingest_endpoints() -> None:
    fake_server = FakeHttpServer()
    payload = b'{"batch":{"batch_id":"jobs-wiki-batch-001","domain":"recruiting","producer":"jobs-wiki","pack_version":"2026-04-18","facts":[],"relations":[]}}'

    validate_response = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/domain-proposals/validate",
        headers={"X-Request-Id": "req-validate"},
        body=payload,
    )
    ingest_response = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/domain-proposals/ingest",
        headers={"X-Request-Id": "req-ingest"},
        body=payload,
    )

    assert validate_response.status_code == 200
    assert validate_response.payload["ok"] is True
    assert validate_response.payload["request_id"] == "req-validate"
    assert validate_response.payload["result"]["committed"] is False
    assert validate_response.payload["result"]["audit"]["evaluated_pack_version"] == "2026-04-18"

    assert ingest_response.status_code == 200
    assert ingest_response.payload["ok"] is True
    assert ingest_response.payload["request_id"] == "req-ingest"
    assert ingest_response.payload["result"]["committed"] is True
    assert "fact:job_posting:EMP-1" in ingest_response.payload["result"]["affected_fact_ids"]

    assert fake_server.calls == [
        (
            "validate_domain_proposal_batch",
            {
                "batch": {
                    "batch_id": "jobs-wiki-batch-001",
                    "domain": "recruiting",
                    "producer": "jobs-wiki",
                    "pack_version": "2026-04-18",
                    "facts": [],
                    "relations": [],
                }
            },
        ),
        (
            "ingest_domain_proposal_batch",
            {
                "batch": {
                    "batch_id": "jobs-wiki-batch-001",
                    "domain": "recruiting",
                    "producer": "jobs-wiki",
                    "pack_version": "2026-04-18",
                    "facts": [],
                    "relations": [],
                }
            },
        ),
    ]


def test_http_runtime_exposes_profile_upsert_and_personal_query_endpoints() -> None:
    fake_server = FakeHttpServer()

    upsert_response = dispatch_http_request(
        fake_server,
        method="PUT",
        path="/api/v1/profile-contexts/tenant-1/user-1",
        headers={"X-Request-Id": "req-profile"},
        body=(
            b'{"domain":"recruiting","profile_version":"profile:v1","goals":["find backend roles"],'
            b'"preferences":{"location":"jp"},"attributes":{"level":"mid"}}'
        ),
    )
    query_response = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/personal-queries",
        headers={"X-Request-Id": "req-query"},
        body=(
            b'{"domain":"recruiting","tenant_id":"tenant-1","user_id":"user-1",'
            b'"question":"What should I do next?","profile_version":"profile:v1",'
            b'"model_profile":"balanced_default","save":false}'
        ),
    )

    assert upsert_response.status_code == 200
    assert upsert_response.payload["ok"] is True
    assert upsert_response.payload["request_id"] == "req-profile"
    profile = upsert_response.payload["result"]["profile_context"]
    assert profile["tenant_id"] == "tenant-1"
    assert profile["user_id"] == "user-1"

    assert query_response.status_code == 200
    assert query_response.payload["ok"] is True
    assert query_response.payload["request_id"] == "req-query"
    assert "## Strategy" in query_response.payload["result"]["answer_markdown"]
    assert query_response.payload["result"]["provenance"]["profile_version"] == "profile:v1"


def test_http_runtime_personal_query_maps_missing_profile_and_profile_mismatch() -> None:
    fake_server = FakeHttpServer()

    missing_profile = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/personal-queries",
        headers={},
        body=(
            b'{"domain":"recruiting","tenant_id":"tenant-1","user_id":"user-1",'
            b'"question":"What should I do next?","profile_version":"profile:v1",'
            b'"model_profile":"balanced_default"}'
        ),
    )

    fake_server.profile_contexts[("recruiting", "tenant-1", "user-1")] = {
        "domain": "recruiting",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "profile_version": "profile:v2",
        "goals": [],
        "preferences": {},
        "attributes": {},
    }

    mismatched_profile = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/personal-queries",
        headers={},
        body=(
            b'{"domain":"recruiting","tenant_id":"tenant-1","user_id":"user-1",'
            b'"question":"What should I do next?","profile_version":"profile:v1",'
            b'"model_profile":"balanced_default"}'
        ),
    )

    assert missing_profile.status_code == 404
    assert missing_profile.payload["ok"] is False
    assert missing_profile.payload["error"]["code"] == "not_found"

    assert mismatched_profile.status_code == 422
    assert mismatched_profile.payload["ok"] is False
    assert mismatched_profile.payload["error"]["code"] == "validation_error"


def test_http_runtime_exposes_personal_raw_to_wiki_action_endpoints() -> None:
    fake_server = FakeHttpServer()
    fake_server.bootstrap = type(
        "Bootstrap",
        (),
        {"personal_document_generation_service": FakePersonalGenerationService()},
    )()

    summarize_response = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/users/tenant-1/user-1/personal-documents/personal%3Araw%3A1/summarize-wiki",
        headers={"X-Request-Id": "req-summarize"},
        body=(
            b'{"domain":"recruiting","profile_version":"profile:v1","model_profile":"balanced_default",'
            b'"source_document_ref":{"subspace":"raw","version":4,"kind":"raw_document","asset_refs":["asset:1"]},'
            b'"save_target":{"subspace":"wiki"},"summary_style":"concise"}'
        ),
    )
    rewrite_response = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/users/tenant-1/user-1/personal-documents/personal%3Araw%3A2/rewrite-wiki",
        headers={"X-Request-Id": "req-rewrite"},
        body=(
            b'{"domain":"recruiting","profile_version":"profile:v1","model_profile":"balanced_default",'
            b'"source_document_ref":{"subspace":"raw","version":2},"save_target":{"document_id":"personal:wiki:1","version":3},'
            b'"rewrite_goal":"job-prep"}'
        ),
    )
    structure_response = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/users/tenant-1/user-1/personal-documents/personal%3Araw%3A3/structure-wiki",
        headers={"X-Request-Id": "req-structure"},
        body=(
            b'{"domain":"recruiting","profile_version":"profile:v1","model_profile":"balanced_default",'
            b'"source_document_ref":{"subspace":"raw","version":1},"save_target":{"subspace":"wiki"},'
            b'"structure_template":"outline"}'
        ),
    )
    suggest_response = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/users/tenant-1/user-1/personal-documents/personal%3Awiki%3A1/suggest-links",
        headers={"X-Request-Id": "req-suggest"},
        body=(
            b'{"domain":"recruiting","profile_version":"profile:v1","model_profile":"balanced_default",'
            b'"wiki_document_version":3,"max_suggestions":5}'
        ),
    )
    invalid_response = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/users/tenant-1/user-1/personal-documents/personal%3Awiki%3A1/suggest-links",
        headers={"X-Request-Id": "req-invalid"},
        body=(
            b'{"domain":"recruiting","profile_version":"profile:v1","model_profile":"balanced_default",'
            b'"wiki_document_version":"three"}'
        ),
    )
    attach_response = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/users/tenant-1/user-1/personal-documents/personal%3Awiki%3A1/attach-links",
        headers={"X-Request-Id": "req-attach"},
        body=(
            b'{"domain":"recruiting","wiki_document_version":3,'
            b'"attachments":[{"layer":"fact","id":"fact:job:1"}]}'
        ),
    )
    conflict_response = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/users/tenant-1/user-1/personal-documents/personal%3Awiki%3A1/attach-links",
        headers={"X-Request-Id": "req-conflict"},
        body=(
            b'{"domain":"recruiting","wiki_document_version":3,'
            b'"attachments":[{"layer":"fact","id":"fact:job:2"}]}'
        ),
    )

    assert summarize_response.status_code == 200
    assert summarize_response.payload["result"]["document"]["source_document_ref"]["document_id"] == "personal:raw:1"
    assert summarize_response.payload["result"]["document"]["source_document_ref"]["subspace"] == "raw"

    assert rewrite_response.status_code == 200
    assert rewrite_response.payload["result"]["document"]["source_document_ref"]["document_id"] == "personal:raw:2"

    assert structure_response.status_code == 200
    assert structure_response.payload["result"]["document"]["source_document_ref"]["document_id"] == "personal:raw:3"

    assert suggest_response.status_code == 200
    assert suggest_response.payload["result"]["wiki_document_id"] == "personal:wiki:1"
    assert suggest_response.payload["result"]["wiki_document_version"] == 3

    assert invalid_response.status_code == 422
    assert invalid_response.payload["ok"] is False
    assert invalid_response.payload["error"]["code"] == "validation_error"

    assert attach_response.status_code == 200
    assert attach_response.payload["result"]["wiki_document_version"] == 4

    assert conflict_response.status_code == 422
    assert conflict_response.payload["ok"] is False
    assert conflict_response.payload["error"]["code"] == "validation_error"

    service = fake_server.bootstrap.personal_document_generation_service
    assert service.calls == [
        (
            "summarize_personal_document_to_wiki",
            {
                "domain": "recruiting",
                "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
                "source_document_ref": {
                    "document_id": "personal:raw:1",
                    "subspace": "raw",
                    "version": 4,
                    "kind": "raw_document",
                    "asset_refs": ["asset:1"],
                },
                "profile_version": "profile:v1",
                "model_profile": "balanced_default",
                "save_target": {"subspace": "wiki"},
                "summary_style": "concise",
            },
        ),
        (
            "rewrite_personal_document_to_wiki",
            {
                "domain": "recruiting",
                "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
                "source_document_ref": {
                    "document_id": "personal:raw:2",
                    "subspace": "raw",
                    "version": 2,
                },
                "profile_version": "profile:v1",
                "model_profile": "balanced_default",
                "save_target": {"document_id": "personal:wiki:1", "version": 3, "subspace": "wiki"},
                "rewrite_goal": "job-prep",
            },
        ),
        (
            "structure_personal_document_to_wiki",
            {
                "domain": "recruiting",
                "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
                "source_document_ref": {
                    "document_id": "personal:raw:3",
                    "subspace": "raw",
                    "version": 1,
                },
                "profile_version": "profile:v1",
                "model_profile": "balanced_default",
                "save_target": {"subspace": "wiki"},
                "structure_template": "outline",
            },
        ),
        (
            "suggest_personal_wiki_links",
            {
                "domain": "recruiting",
                "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
                "wiki_document_id": "personal:wiki:1",
                "wiki_document_version": 3,
                "profile_version": "profile:v1",
                "model_profile": "balanced_default",
                "max_suggestions": 5,
            },
        ),
        (
            "attach_personal_wiki_links",
            {
                "domain": "recruiting",
                "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
                "wiki_document_id": "personal:wiki:1",
                "wiki_document_version": 3,
                "attachments": [{"layer": "fact", "id": "fact:job:1"}],
            },
        ),
        (
            "attach_personal_wiki_links",
            {
                "domain": "recruiting",
                "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
                "wiki_document_id": "personal:wiki:1",
                "wiki_document_version": 3,
                "attachments": [{"layer": "fact", "id": "fact:job:2"}],
            },
        ),
    ]
    assert fake_server.calls == []


def test_http_runtime_exposes_personal_document_crud_endpoints() -> None:
    fake_server = FakeHttpServer()
    fake_server.profile_contexts[("recruiting", "tenant-1", "user-1")] = {
        "domain": "recruiting",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "profile_version": "profile:v1",
        "goals": [],
        "preferences": {},
        "attributes": {},
    }

    created = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/users/tenant-1/user-1/personal-documents",
        headers={},
        body=(
            b'{"domain":"recruiting","profile_version":"profile:v1","subspace":"raw","kind":"note",'
            b'"title":"Interview prep","body_markdown":"## Prep"}'
        ),
    )
    document_id = created.payload["result"]["document"]["document_id"]
    fetched = dispatch_http_request(
        fake_server,
        method="GET",
        path=f"/api/v1/users/tenant-1/user-1/personal-documents/{document_id}?domain=recruiting",
        headers={},
        body=b"",
    )
    listed = dispatch_http_request(
        fake_server,
        method="GET",
        path="/api/v1/users/tenant-1/user-1/personal-documents?domain=recruiting",
        headers={},
        body=b"",
    )
    updated = dispatch_http_request(
        fake_server,
        method="PATCH",
        path=f"/api/v1/users/tenant-1/user-1/personal-documents/{document_id}",
        headers={},
        body=b'{"domain":"recruiting","profile_version":"profile:v1","if_version":1,"asset_refs":["asset:1"]}',
    )
    deleted = dispatch_http_request(
        fake_server,
        method="DELETE",
        path=f"/api/v1/users/tenant-1/user-1/personal-documents/{document_id}",
        headers={},
        body=b'{"domain":"recruiting","if_version":2}',
    )
    deleted_list = dispatch_http_request(
        fake_server,
        method="GET",
        path="/api/v1/users/tenant-1/user-1/personal-documents?domain=recruiting&status=deleted",
        headers={},
        body=b"",
    )

    assert created.status_code == 200
    assert created.payload["result"]["document"]["version"] == 1
    assert fetched.payload["result"]["document"]["document_id"] == document_id
    assert listed.payload["result"]["items"][0]["document_id"] == document_id
    assert updated.payload["result"]["document"]["version"] == 2
    assert updated.payload["result"]["document"]["asset_refs"] == ["asset:1"]
    assert deleted.payload["result"]["document"]["status"] == "deleted"
    assert deleted.payload["result"]["document"]["version"] == 3
    assert deleted_list.payload["result"]["items"][0]["document_id"] == document_id
    assert fake_server.calls == []


def test_http_runtime_maps_personal_document_conflicts_to_409() -> None:
    fake_server = FakeHttpServer()
    fake_server.profile_contexts[("recruiting", "tenant-1", "user-1")] = {
        "domain": "recruiting",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "profile_version": "profile:v1",
        "goals": [],
        "preferences": {},
        "attributes": {},
    }
    created = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/users/tenant-1/user-1/personal-documents",
        headers={},
        body=(
            b'{"domain":"recruiting","profile_version":"profile:v1","subspace":"raw","kind":"note",'
            b'"title":"Interview prep","body_markdown":"## Prep"}'
        ),
    )
    document_id = created.payload["result"]["document"]["document_id"]

    conflict = dispatch_http_request(
        fake_server,
        method="PATCH",
        path=f"/api/v1/users/tenant-1/user-1/personal-documents/{document_id}",
        headers={},
        body=b'{"domain":"recruiting","profile_version":"profile:v1","if_version":999,"title":"stale"}',
    )

    assert conflict.status_code == 409
    assert conflict.payload["ok"] is False
    assert conflict.payload["error"]["code"] == "conflict"
    assert conflict.payload["error"]["details"]["current_version"] == 1


def test_http_runtime_maps_missing_personal_documents_to_404() -> None:
    fake_server = FakeHttpServer()

    missing_get = dispatch_http_request(
        fake_server,
        method="GET",
        path="/api/v1/users/tenant-1/user-1/personal-documents/pdoc_missing?domain=recruiting",
        headers={},
        body=b"",
    )
    missing_delete = dispatch_http_request(
        fake_server,
        method="DELETE",
        path="/api/v1/users/tenant-1/user-1/personal-documents/pdoc_missing",
        headers={},
        body=b'{"domain":"recruiting","if_version":1}',
    )

    assert missing_get.status_code == 404
    assert missing_get.payload["ok"] is False
    assert missing_get.payload["error"]["code"] == "not_found"
    assert missing_delete.status_code == 404
    assert missing_delete.payload["ok"] is False
    assert missing_delete.payload["error"]["code"] == "not_found"


def test_http_runtime_exposes_interpretation_build_and_operator_status_endpoints() -> None:
    fake_server = FakeHttpServer()

    queued_build = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/interpretation-builds",
        headers={"X-Request-Id": "req-build"},
        body=(
            b'{"domain":"recruiting","partition":{"family":"market_trends","segment":"backend-japan-midlevel"},'
            b'"fact_ids":["fact:job:1"],"fact_snapshot":"fact_snap:seed","model_profile":"balanced_default",'
            b'"publish":true,"execution_mode":"background"}'
        ),
    )
    job_status = dispatch_http_request(
        fake_server,
        method="GET",
        path="/api/v1/jobs/job-123",
        headers={},
        body=b"",
    )
    snapshot_status = dispatch_http_request(
        fake_server,
        method="GET",
        path="/api/v1/snapshot-status?domain=recruiting",
        headers={},
        body=b"",
    )
    cache_status = dispatch_http_request(
        fake_server,
        method="GET",
        path="/api/v1/cache-status/personal%3A1?domain=recruiting&tenant_id=tenant-1&user_id=user-1",
        headers={},
        body=b"",
    )
    explanation = dispatch_http_request(
        fake_server,
        method="GET",
        path="/api/v1/explanations/personal/personal%3A1?domain=recruiting&tenant_id=tenant-1&user_id=user-1",
        headers={},
        body=b"",
    )

    assert queued_build.status_code == 202
    assert queued_build.payload["ok"] is True
    assert queued_build.payload["request_id"] == "req-build"
    assert queued_build.payload["result"]["job_id"] == "job-123"

    assert job_status.status_code == 200
    assert job_status.payload["result"]["job"]["kind"] == "interpretation_build"
    assert job_status.payload["result"]["job"]["state"] == "pending"

    assert snapshot_status.status_code == 200
    assert snapshot_status.payload["result"]["fact_snapshot"] == "fact_snap:seed"
    assert snapshot_status.payload["result"]["layers"]["interpretation"]["interpretation_snapshot_id"] == "interp_snap:seed"

    assert cache_status.status_code == 200
    assert cache_status.payload["result"]["cache_state"] == "fresh"
    assert cache_status.payload["result"]["record_id"] == "personal:1"

    assert explanation.status_code == 200
    assert explanation.payload["result"]["layer"] == "personal"
    assert explanation.payload["result"]["explanation"]["change_reason"] == "current_result"


def test_http_runtime_requires_bearer_token_when_configured() -> None:
    fake_server = FakeHttpServer()

    unauthorized = dispatch_http_request(
        fake_server,
        method="GET",
        path="/api/v1/tools",
        headers={},
        body=b"",
        auth_token="secret-token",
    )
    authorized = dispatch_http_request(
        fake_server,
        method="GET",
        path="/api/v1/tools",
        headers={"Authorization": "Bearer secret-token"},
        body=b"",
        auth_token="secret-token",
    )
    health = dispatch_http_request(
        fake_server,
        method="GET",
        path="/healthz",
        headers={},
        body=b"",
        auth_token="secret-token",
    )

    assert unauthorized.status_code == 401
    assert unauthorized.payload["ok"] is False
    assert unauthorized.payload["error"]["code"] == "unauthorized"
    assert unauthorized.headers["WWW-Authenticate"] == "Bearer"

    assert authorized.status_code == 200
    assert authorized.payload["ok"] is True

    assert health.status_code == 200
    assert health.payload["ok"] is True


def test_http_runtime_maps_validation_and_lookup_errors() -> None:
    fake_server = FakeHttpServer()

    invalid = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/tool-calls",
        headers={},
        body=b'{"name":"get_snapshot_status","arguments":{}}',
    )
    missing = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/tool-calls",
        headers={},
        body=b'{"name":"unknown_tool","arguments":{}}',
    )

    assert invalid.status_code == 422
    assert invalid.payload["ok"] is False
    assert invalid.payload["error"]["code"] == "validation_error"

    assert missing.status_code == 404
    assert missing.payload["ok"] is False
    assert missing.payload["error"]["code"] == "not_found"


def test_http_runtime_registers_personal_asset_and_normalizes_errors() -> None:
    fake_server = FakeHttpServer()
    fake_server.profile_contexts[("recruiting", "tenant-a", "user-42")] = {
        "domain": "recruiting",
        "tenant_id": "tenant-a",
        "user_id": "user-42",
        "profile_version": "profile:v1",
    }

    success = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/users/tenant-a/user-42/personal-assets",
        headers={},
        body=(
            b'{"domain":"recruiting","asset_kind":"file","media_type":"application/pdf",'
            b'"filename":"resume.pdf","storage_ref":"s3://bucket/resume.pdf"}'
        ),
    )
    conflict = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/users/tenant-a/user-42/personal-assets",
        headers={},
        body=(
            b'{"domain":"recruiting","asset_kind":"file","media_type":"application/pdf",'
            b'"filename":"resume.pdf","storage_ref":"s3://bucket/resume.pdf"}'
        ),
    )
    invalid = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/users/tenant-a/user-42/personal-assets",
        headers={},
        body=(
            b'{"domain":"recruiting","asset_kind":"file","media_type":"application/pdf",'
            b'"filename":"resume.pdf","storage_ref":"relative/path.pdf"}'
        ),
    )
    missing_scope = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/users/tenant-a/user-404/personal-assets",
        headers={},
        body=(
            b'{"domain":"recruiting","asset_kind":"file","media_type":"application/pdf",'
            b'"filename":"resume.pdf","storage_ref":"s3://bucket/missing.pdf"}'
        ),
    )

    assert success.status_code == 200
    assert success.payload["result"]["asset_id"].startswith("passet_")
    assert success.payload["result"]["asset"]["asset_id"] == success.payload["result"]["asset_id"]
    assert success.payload["result"]["asset"]["tenant_id"] == "tenant-a"
    assert success.payload["result"]["asset"]["user_id"] == "user-42"
    assert fake_server.calls == []

    assert conflict.status_code == 409
    assert conflict.payload["error"]["code"] == "conflict"
    assert conflict.payload["error"]["details"]["asset_id"] == success.payload["result"]["asset_id"]

    assert invalid.status_code == 422
    assert invalid.payload["error"]["code"] == "validation_error"

    assert missing_scope.status_code == 404
    assert missing_scope.payload["error"]["code"] == "not_found"


def test_http_runtime_maps_internal_errors_and_method_mismatch() -> None:
    fake_server = FakeHttpServer()

    internal = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/tool-calls",
        headers={},
        body=b'{"name":"explode","arguments":{}}',
    )
    wrong_method = dispatch_http_request(
        fake_server,
        method="POST",
        path="/healthz",
        headers={},
        body=b"",
    )

    assert internal.status_code == 500
    assert internal.payload["ok"] is False
    assert internal.payload["error"]["code"] == "internal_error"

    assert wrong_method.status_code == 405
    assert wrong_method.payload["ok"] is False
    assert wrong_method.payload["error"]["code"] == "method_not_allowed"
    assert wrong_method.headers["Allow"] == "GET"
