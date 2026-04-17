from __future__ import annotations

from typing import Any, Literal

from wiki_mcp.schemas.profile_context import ProfileContext
from wiki_mcp.schemas.retrieval_fact_summary import RetrievalFactSummary
from wiki_mcp.schemas.retrieval_interpretation_summary import (
    RetrievalInterpretationSummary,
)
from wiki_mcp.schemas.retrieval_match_explanation import RetrievalMatchExplanation
from wiki_mcp.schemas.retrieval_personal_summary import RetrievalPersonalSummary
from wiki_mcp.schemas.retrieval_result import RetrievalResult
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef
from wiki_mcp.services.interfaces.repositories import (
    FactRepository,
    InterpretationRepository,
    PersonalRepository,
)


class CuratedRetrievalService:
    """Repo-backed curated retrieval across Personal, Interpretation, and Fact.

    This service intentionally avoids legacy page-read-first behavior. It is a
    thin implementation of the current docs-defined default retrieval mode:
    `Personal -> Interpretation -> Fact`.
    """

    layer_order = ("personal", "interpretation", "fact")
    interpretation_public_statuses = {"published", "stale"}

    def __init__(
        self,
        *,
        fact_repository: FactRepository | None = None,
        interpretation_repository: InterpretationRepository | None = None,
        personal_repository: PersonalRepository | None = None,
        layer_result_limit: int = 5,
        evidence_fact_limit: int = 3,
    ) -> None:
        self.fact_repository = fact_repository
        self.interpretation_repository = interpretation_repository
        self.personal_repository = personal_repository
        self.layer_result_limit = layer_result_limit
        self.evidence_fact_limit = evidence_fact_limit

    def retrieve_for_query(
        self,
        domain: str,
        question: str,
        scope_ref: ScopeRef,
        profile_context: ProfileContext | None = None,
    ) -> RetrievalResult:
        normalized_question = question.strip()
        query_tokens = self._tokenize(question)
        if not normalized_question:
            return self._empty_result()

        personal_records = self._search_personal(
            domain=domain,
            question=normalized_question,
            query_tokens=query_tokens,
            scope_ref=scope_ref,
        )

        personal_anchor_interpretation_ids, personal_anchor_fact_ids = self._collect_personal_anchors(
            personal_records
        )
        interpretation_records, interpretation_source_by_id, interpretation_source = (
            self._resolve_interpretations(
                domain=domain,
                question=normalized_question,
                query_tokens=query_tokens,
                scope_ref=scope_ref,
                personal_anchor_interpretation_ids=personal_anchor_interpretation_ids,
            )
        )
        fact_records, fact_source_by_id, fact_source = self._resolve_facts(
            domain=domain,
            question=normalized_question,
            query_tokens=query_tokens,
            scope_ref=scope_ref,
            interpretation_records=interpretation_records,
            personal_anchor_fact_ids=personal_anchor_fact_ids,
        )
        personal_anchor_status = self._personal_anchor_status(
            personal_records=personal_records,
            anchor_interpretation_ids=personal_anchor_interpretation_ids,
            anchor_fact_ids=personal_anchor_fact_ids,
        )

        result: RetrievalResult = {
            "personal_ids": [record["id"] for record in personal_records],
            "interpretation_ids": [record["id"] for record in interpretation_records],
            "fact_ids": [record["id"] for record in fact_records],
            "personal_records": [self._map_personal_record(record) for record in personal_records],
            "interpretation_records": [
                self._map_interpretation_record(record)
                for record in interpretation_records
            ],
            "fact_records": [self._map_fact_record(record) for record in fact_records],
            "personal_explanations": self._build_explanations(
                layer="personal",
                records=personal_records,
                query_tokens=query_tokens,
                profile_context=profile_context,
            ),
            "interpretation_explanations": self._build_explanations(
                layer="interpretation",
                records=interpretation_records,
                query_tokens=query_tokens,
                profile_context=None,
                source_by_id=interpretation_source_by_id,
            ),
            "fact_explanations": self._build_explanations(
                layer="fact",
                records=fact_records,
                query_tokens=query_tokens,
                profile_context=None,
                source_by_id=fact_source_by_id,
            ),
            "retrieval_metadata": {
                "mode": "curated",
                "layer_order": list(self.layer_order),
                "backend": "repository",
                "personal_anchor_status": personal_anchor_status,
                "interpretation_source": interpretation_source,
                "fact_source": fact_source,
                "evidence_fact_limit": self.evidence_fact_limit,
            },
        }

        snapshot_ref = self._merge_snapshot_ref(
            personal_records=personal_records,
            interpretation_records=interpretation_records,
            fact_records=fact_records,
        )
        if snapshot_ref is not None:
            result["snapshot_ref"] = snapshot_ref

        return result

    def _empty_result(self) -> RetrievalResult:
        return {
            "personal_ids": [],
            "interpretation_ids": [],
            "fact_ids": [],
            "personal_records": [],
            "interpretation_records": [],
            "fact_records": [],
            "personal_explanations": [],
            "interpretation_explanations": [],
            "fact_explanations": [],
            "retrieval_metadata": {
                "mode": "curated",
                "layer_order": list(self.layer_order),
                "backend": "repository",
                "personal_anchor_status": "not_available",
                "interpretation_source": "none",
                "fact_source": "none",
                "evidence_fact_limit": self.evidence_fact_limit,
            },
        }

    def _search_personal(
        self,
        *,
        domain: str,
        question: str,
        query_tokens: list[str],
        scope_ref: ScopeRef,
    ) -> list[dict[str, Any]]:
        if self.personal_repository is None:
            return []
        return list(
            self.personal_repository.search_for_retrieval(
                domain=domain,
                scope_ref=scope_ref,
                query_text=question,
                query_tokens=query_tokens,
                limit=self.layer_result_limit,
            )
        )

    def _resolve_interpretations(
        self,
        *,
        domain: str,
        question: str,
        query_tokens: list[str],
        scope_ref: ScopeRef,
        personal_anchor_interpretation_ids: list[str],
    ) -> tuple[
        list[dict[str, Any]],
        dict[str, dict[str, Any]],
        Literal["personal_anchors", "search_fallback", "none"],
    ]:
        source_by_id: dict[str, dict[str, Any]] = {}
        records: list[dict[str, Any]] = []
        if personal_anchor_interpretation_ids:
            records = self._load_interpretations_by_ids(
                ids=personal_anchor_interpretation_ids[: self.layer_result_limit],
                scope_ref=scope_ref,
            )
            if records:
                for record in records:
                    source_by_id[record["id"]] = {
                        "match_type": "personal_anchor_expansion",
                        "matched_fields": ["body.anchors"],
                        "matched_token_count": 0,
                    }
                return records, source_by_id, "personal_anchors"

        records = self._search_interpretation(
            domain=domain,
            question=question,
            query_tokens=query_tokens,
            scope_ref=scope_ref,
        )
        for record in records:
            source_by_id[record["id"]] = {
                "match_type": "curated_repository_search",
                "matched_fields": self._matched_fields(record, query_tokens) or ["repository_search"],
                "matched_token_count": len(query_tokens),
            }
        source = "search_fallback" if records else "none"
        return records, source_by_id, source

    def _search_interpretation(
        self,
        *,
        domain: str,
        question: str,
        query_tokens: list[str],
        scope_ref: ScopeRef,
    ) -> list[dict[str, Any]]:
        if self.interpretation_repository is None:
            return []
        return list(
            self.interpretation_repository.search_for_retrieval(
                domain=domain,
                scope_ref=scope_ref,
                query_text=question,
                query_tokens=query_tokens,
                limit=self.layer_result_limit,
            )
        )

    def _load_interpretations_by_ids(
        self,
        *,
        ids: list[str],
        scope_ref: ScopeRef,
    ) -> list[dict[str, Any]]:
        if self.interpretation_repository is None or not ids:
            return []
        records = self.interpretation_repository.get_by_ids(ids, scope_ref)
        allowed_by_id = {
            record["id"]: record
            for record in records
            if record.get("status") in self.interpretation_public_statuses
        }
        return [allowed_by_id[record_id] for record_id in ids if record_id in allowed_by_id]

    def _resolve_facts(
        self,
        *,
        domain: str,
        question: str,
        query_tokens: list[str],
        scope_ref: ScopeRef,
        interpretation_records: list[dict[str, Any]],
        personal_anchor_fact_ids: list[str],
    ) -> tuple[
        list[dict[str, Any]],
        dict[str, dict[str, Any]],
        Literal["interpretation_evidence", "search_fallback", "mixed", "none"],
    ]:
        source_by_id: dict[str, dict[str, Any]] = {}
        evidence_fact_ids = self._collect_evidence_fact_ids(interpretation_records)
        anchored_fact_ids = [
            fact_id
            for fact_id in personal_anchor_fact_ids
            if fact_id not in evidence_fact_ids
        ]
        selected_fact_ids = (
            evidence_fact_ids[: self.evidence_fact_limit] + anchored_fact_ids
        )[: self.layer_result_limit]
        fact_records = self._load_facts_by_ids(ids=selected_fact_ids, scope_ref=scope_ref)

        loaded_fact_ids = {record["id"] for record in fact_records}
        fact_source: Literal["interpretation_evidence", "search_fallback", "mixed", "none"] = "none"

        for fact_id in selected_fact_ids:
            if fact_id not in loaded_fact_ids:
                continue
            if fact_id in evidence_fact_ids:
                source_by_id[fact_id] = {
                    "match_type": "interpretation_evidence",
                    "matched_fields": ["evidence.fact_id"],
                    "matched_token_count": 0,
                }
            else:
                source_by_id[fact_id] = {
                    "match_type": "personal_anchor_expansion",
                    "matched_fields": ["body.anchors"],
                    "matched_token_count": 0,
                }

        if fact_records and any(record["id"] in evidence_fact_ids for record in fact_records):
            fact_source = "interpretation_evidence"

        if not fact_records:
            fallback_records = self._search_fact(
                domain=domain,
                question=question,
                query_tokens=query_tokens,
                scope_ref=scope_ref,
                exclude_ids=[record["id"] for record in fact_records],
            )
            if fallback_records:
                for record in fallback_records:
                    source_by_id[record["id"]] = {
                        "match_type": "curated_repository_search",
                        "matched_fields": self._matched_fields(record, query_tokens)
                        or ["repository_search"],
                        "matched_token_count": len(query_tokens),
                    }
                fact_records.extend(fallback_records)
                if fact_source == "interpretation_evidence":
                    fact_source = "mixed"
                else:
                    fact_source = "search_fallback"

        if not fact_records:
            fact_source = "none"
        return fact_records[: self.layer_result_limit], source_by_id, fact_source

    def _search_fact(
        self,
        *,
        domain: str,
        question: str,
        query_tokens: list[str],
        scope_ref: ScopeRef,
        exclude_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if self.fact_repository is None:
            return []
        records = list(
            self.fact_repository.search_for_retrieval(
                domain=domain,
                scope_ref=scope_ref,
                query_text=question,
                query_tokens=query_tokens,
                limit=self.layer_result_limit,
            )
        )
        if not exclude_ids:
            return records
        excluded = set(exclude_ids)
        return [record for record in records if record["id"] not in excluded]

    def _load_facts_by_ids(
        self,
        *,
        ids: list[str],
        scope_ref: ScopeRef,
    ) -> list[dict[str, Any]]:
        if self.fact_repository is None or not ids:
            return []
        records = self.fact_repository.get_by_ids(ids, scope_ref)
        by_id = {record["id"]: record for record in records}
        return [by_id[record_id] for record_id in ids if record_id in by_id]

    def _map_personal_record(self, record: dict[str, Any]) -> RetrievalPersonalSummary:
        return {
            "id": record["id"],
            "domain": record["domain"],
            "kind": record["kind"],
            "title": record["title"],
            "summary": record["summary"],
            "snapshot_ref": record["snapshot_ref"],
        }

    def _map_interpretation_record(
        self,
        record: dict[str, Any],
    ) -> RetrievalInterpretationSummary:
        summary = None
        raw_summary = record.get("summary")
        if isinstance(raw_summary, str) and raw_summary.strip():
            summary = raw_summary.strip()
        else:
            body = record.get("body", {})
            if isinstance(body, dict):
                nested_summary = body.get("summary")
                if isinstance(nested_summary, str) and nested_summary.strip():
                    summary = nested_summary.strip()
        result: RetrievalInterpretationSummary = {
            "id": record["id"],
            "domain": record["domain"],
            **({"family": record["family"]} if record.get("family") else {}),
            "kind": record["kind"],
            "subject_type": record["subject_type"],
            "subject_id": record["subject_id"],
            "status": record["status"],
            "confidence": record["confidence"],
        }
        if record.get("title"):
            result["title"] = record["title"]
        if summary:
            result["summary"] = summary
        return result

    def _map_fact_record(self, record: dict[str, Any]) -> RetrievalFactSummary:
        attributes = record.get("attributes", {})
        title = None
        if isinstance(attributes, dict):
            for key in ("title", "name", "label", "summary"):
                value = attributes.get(key)
                if isinstance(value, str) and value.strip():
                    title = value.strip()
                    break

        result: RetrievalFactSummary = {
            "id": record["id"],
            "domain": record["domain"],
            "entity_type": record["entity_type"],
            "canonical_key": record["canonical_key"],
            "scope": record["scope"],
        }
        if title:
            result["title"] = title
        if record.get("fact_snapshot_id"):
            result["fact_snapshot_id"] = record["fact_snapshot_id"]
        return result

    def _build_explanations(
        self,
        *,
        layer: str,
        records: list[dict[str, Any]],
        query_tokens: list[str],
        profile_context: ProfileContext | None,
        source_by_id: dict[str, dict[str, Any]] | None = None,
    ) -> list[RetrievalMatchExplanation]:
        explanations: list[RetrievalMatchExplanation] = []
        for index, record in enumerate(records, start=1):
            source = (source_by_id or {}).get(record["id"], {})
            matched_fields = source.get("matched_fields")
            if not isinstance(matched_fields, list):
                matched_fields = self._matched_fields(record, query_tokens)
            explanations.append(
                {
                    "layer": layer,  # type: ignore[typeddict-item]
                    "record_id": record["id"],
                    "rank": index,
                    "score": max(len(matched_fields), 1),
                    "match_type": str(source.get("match_type") or "curated_repository_search"),
                    "matched_fields": matched_fields or ["repository_search"],
                    "matched_token_count": int(
                        source.get("matched_token_count", len(query_tokens))
                    ),
                    "profile_boost_applied": profile_context is not None and layer == "personal",
                    "has_rendered_page": False,
                }
            )
        return explanations

    def _matched_fields(
        self,
        record: dict[str, Any],
        query_tokens: list[str],
    ) -> list[str]:
        candidates: list[tuple[str, str]] = []
        for key in ("title", "summary", "kind", "entity_type", "canonical_key", "subject_id"):
            value = record.get(key)
            if isinstance(value, str):
                candidates.append((key, value.lower()))

        attributes = record.get("attributes")
        if isinstance(attributes, dict):
            for key in ("title", "name", "label", "summary", "description"):
                value = attributes.get(key)
                if isinstance(value, str):
                    candidates.append((f"attributes.{key}", value.lower()))

        matched: list[str] = []
        for field, haystack in candidates:
            if any(token in haystack for token in query_tokens):
                matched.append(field)
        return matched

    def _merge_snapshot_ref(
        self,
        *,
        personal_records: list[dict[str, Any]],
        interpretation_records: list[dict[str, Any]],
        fact_records: list[dict[str, Any]],
    ) -> SnapshotRef | None:
        merged: SnapshotRef = {}

        for record in personal_records:
            snapshot_ref = record.get("snapshot_ref")
            if isinstance(snapshot_ref, dict):
                if snapshot_ref.get("fact_snapshot_id") and not merged.get("fact_snapshot_id"):
                    merged["fact_snapshot_id"] = snapshot_ref["fact_snapshot_id"]
                if snapshot_ref.get("interpretation_snapshot_id") and not merged.get(
                    "interpretation_snapshot_id"
                ):
                    merged["interpretation_snapshot_id"] = snapshot_ref[
                        "interpretation_snapshot_id"
                    ]
                if snapshot_ref.get("profile_version") and not merged.get("profile_version"):
                    merged["profile_version"] = snapshot_ref["profile_version"]

        for record in interpretation_records:
            fact_snapshot_id = record.get("fact_snapshot_id")
            if fact_snapshot_id and not merged.get("fact_snapshot_id"):
                merged["fact_snapshot_id"] = fact_snapshot_id

        for record in fact_records:
            fact_snapshot_id = record.get("fact_snapshot_id")
            if fact_snapshot_id and not merged.get("fact_snapshot_id"):
                merged["fact_snapshot_id"] = fact_snapshot_id

        return merged or None

    def _collect_personal_anchors(
        self,
        records: list[dict[str, Any]],
    ) -> tuple[list[str], list[str]]:
        interpretation_ids: list[str] = []
        fact_ids: list[str] = []
        for record in records:
            body = record.get("body")
            if not isinstance(body, dict):
                continue
            interpretation_ids.extend(
                self._extract_anchor_ids(body.get("anchors"), expected_layer="interpretation")
            )
            interpretation_ids.extend(
                self._extract_string_list(body.get("interpretation_ids"))
            )
            fact_ids.extend(self._extract_anchor_ids(body.get("anchors"), expected_layer="fact"))
            fact_ids.extend(self._extract_string_list(body.get("fact_ids")))
        return self._dedupe(interpretation_ids), self._dedupe(fact_ids)

    def _collect_evidence_fact_ids(
        self,
        interpretation_records: list[dict[str, Any]],
    ) -> list[str]:
        scored_fact_ids: list[tuple[float, str]] = []
        for record in interpretation_records:
            evidence = record.get("evidence")
            if not isinstance(evidence, list):
                continue
            for item in evidence:
                if not isinstance(item, dict):
                    continue
                fact_id = item.get("fact_id")
                if not isinstance(fact_id, str) or not fact_id.strip():
                    continue
                weight = item.get("weight")
                score = float(weight) if isinstance(weight, (int, float)) else 0.0
                scored_fact_ids.append((score, fact_id))
        ordered_ids = [fact_id for _, fact_id in sorted(scored_fact_ids, reverse=True)]
        return self._dedupe(ordered_ids)

    def _extract_anchor_ids(
        self,
        value: Any,
        *,
        expected_layer: Literal["interpretation", "fact"],
    ) -> list[str]:
        if not isinstance(value, list):
            return []
        ids: list[str] = []
        for item in value:
            if isinstance(item, str):
                normalized = item.strip()
                if expected_layer == "interpretation" and normalized.startswith("interp"):
                    ids.append(normalized)
                if expected_layer == "fact" and normalized.startswith("fact"):
                    ids.append(normalized)
                continue
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            item_layer = item.get("layer")
            if isinstance(item_id, str) and item_id.strip():
                if item_layer == expected_layer:
                    ids.append(item_id.strip())
                    continue
                if expected_layer == "interpretation" and item_id.startswith("interp"):
                    ids.append(item_id.strip())
                if expected_layer == "fact" and item_id.startswith("fact"):
                    ids.append(item_id.strip())
        return ids

    def _extract_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    def _personal_anchor_status(
        self,
        *,
        personal_records: list[dict[str, Any]],
        anchor_interpretation_ids: list[str],
        anchor_fact_ids: list[str],
    ) -> Literal["present", "absent", "not_available"]:
        if not personal_records:
            return "not_available"
        if anchor_interpretation_ids or anchor_fact_ids:
            return "present"
        return "absent"

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped

    def _tokenize(self, question: str) -> list[str]:
        return [token for token in question.lower().split() if token]
