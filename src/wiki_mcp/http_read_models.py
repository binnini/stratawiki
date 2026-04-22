from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any

from wiki_mcp.schemas.scope_ref import ScopeRef


_CLOSE_SOON_DAYS = 7
_DAY_SECONDS = 24 * 60 * 60
_KST_OFFSET_HOURS = 9
_OPPORTUNITY_ID_PREFIX = "opp_"


def _compact_object(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: entry_value
        for key, entry_value in value.items()
        if entry_value is not None
    }


def _trim_text(value: object, max_length: int = 160) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.replace("&#xd;", " ")
    normalized = " ".join(normalized.split()).strip()
    if not normalized:
        return None
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 1].rstrip()}…"


def _encode_opportunity_id(canonical_key: str) -> str:
    encoded = base64.urlsafe_b64encode(canonical_key.encode("utf-8")).decode("ascii")
    return f"{_OPPORTUNITY_ID_PREFIX}{encoded.rstrip('=')}"


def decode_opportunity_id(opportunity_id: str) -> str | None:
    if not isinstance(opportunity_id, str) or not opportunity_id.startswith(_OPPORTUNITY_ID_PREFIX):
        return None
    encoded = opportunity_id[len(_OPPORTUNITY_ID_PREFIX) :]
    if not encoded:
        return None
    padding = "=" * ((4 - len(encoded) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode(f"{encoded}{padding}").decode("utf-8")
    except Exception:
        return None
    return decoded if decoded.startswith("job_posting:") else None


def format_opportunity_cursor(offset: int) -> str:
    return f"cursor_{offset:03d}"


def parse_opportunity_cursor(cursor: str | None) -> int | None:
    if cursor is None:
        return None
    if not isinstance(cursor, str) or not cursor.startswith("cursor_"):
        raise ValueError("cursor must use the 'cursor_<number>' format.")
    offset = cursor.removeprefix("cursor_")
    if not offset.isdigit():
        raise ValueError("cursor must use the 'cursor_<number>' format.")
    return int(offset)


def _parse_compact_date(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, str) or len(value) != 8 or not value.isdigit():
        return None
    year = int(value[:4])
    month = int(value[4:6])
    day = int(value[6:8])
    try:
        datetime(year, month, day)
    except ValueError:
        return None
    return year, month, day


def _format_kst_datetime(date_parts: tuple[int, int, int] | None, *, end_of_day: bool = False) -> str | None:
    if date_parts is None:
        return None
    year, month, day = date_parts
    clock = "23:59:59" if end_of_day else "09:00:00"
    return f"{year:04d}-{month:02d}-{day:02d}T{clock}+09:00"


def _format_kst_end_of_day_utc_iso(date_parts: tuple[int, int, int] | None) -> str | None:
    if date_parts is None:
        return None
    year, month, day = date_parts
    return datetime(year, month, day, 14, 59, 59, tzinfo=UTC).isoformat().replace("+00:00", "Z")


def _compute_closing_in_days(date_parts: tuple[int, int, int] | None, now: datetime) -> int | None:
    if date_parts is None:
        return None
    close_day = datetime(date_parts[0], date_parts[1], date_parts[2], tzinfo=UTC)
    kst_now = now.astimezone(UTC).timestamp() + (_KST_OFFSET_HOURS * 60 * 60)
    kst_date = datetime.fromtimestamp(kst_now, tz=UTC)
    current_day = datetime(kst_date.year, kst_date.month, kst_date.day, tzinfo=UTC)
    return round((close_day - current_day).total_seconds() / _DAY_SECONDS)


def _derive_status(closing_in_days: int | None) -> str:
    if closing_in_days is None:
        return "unknown"
    if closing_in_days < 0:
        return "closed"
    if closing_in_days <= _CLOSE_SOON_DAYS:
        return "closing_soon"
    return "open"


def _derive_urgency_label(status: str, closing_in_days: int | None) -> str | None:
    if status == "closed":
        return "Closed"
    if closing_in_days is None:
        return None
    return f"D-{closing_in_days}"


def _create_projection_sync(snapshot_status: dict[str, Any] | None, fallback_version: str | None) -> dict[str, Any]:
    if snapshot_status and (
        snapshot_status.get("fact_snapshot_id") or snapshot_status.get("current_snapshot_id")
    ):
        version = (
            snapshot_status.get("current_snapshot_id")
            or snapshot_status.get("fact_snapshot_id")
            or fallback_version
        )
        visible_at = snapshot_status.get("published_at") or snapshot_status.get("updated_at")
        if snapshot_status.get("has_pending_outbox"):
            return _compact_object(
                {
                    "visibility": "pending",
                    "version": version,
                    "visibleAt": visible_at,
                }
            )
        if not snapshot_status.get("published_at"):
            return _compact_object(
                {
                    "visibility": "partial",
                    "version": version,
                    "visibleAt": visible_at,
                }
            )
        return _compact_object(
            {
                "visibility": "applied",
                "version": version,
                "visibleAt": visible_at,
            }
        )
    if fallback_version:
        return {
            "visibility": "unknown",
            "version": fallback_version,
        }
    return {
        "visibility": "stale",
    }


def _get_role_label(role_record: dict[str, Any] | None) -> str | None:
    if role_record is None:
        return None
    attributes = role_record.get("attributes") or {}
    return (
        _trim_text(attributes.get("display_name"), 240)
        or _trim_text(attributes.get("normalized_name"), 240)
        or _trim_text(attributes.get("source_code"), 240)
    )


def _build_description_markdown(
    attributes: dict[str, Any],
    company_record: dict[str, Any] | None,
    role_labels: list[str],
) -> str:
    sections: list[str] = []
    summary = _trim_text(attributes.get("summary"), 500)
    if summary:
        sections.append(summary)

    company_attributes = (company_record or {}).get("attributes") or {}
    company_description = _trim_text(company_attributes.get("description"), 800)
    if company_description:
        sections.append(f"## Company\n{company_description}")

    if role_labels:
        sections.append(f"## Roles\n- {'\n- '.join(role_labels)}")

    requirements_text = _trim_text(attributes.get("requirements_text"), 1200)
    if requirements_text:
        sections.append(f"## Requirements\n{requirements_text}")

    selection_process_text = _trim_text(attributes.get("selection_process_text"), 1200)
    if selection_process_text:
        sections.append(f"## Selection Process\n{selection_process_text}")

    return "\n\n".join(section for section in sections if section)


def _build_analysis(
    *,
    attributes: dict[str, Any],
    company_record: dict[str, Any] | None,
    role_labels: list[str],
    status: str,
) -> dict[str, Any]:
    fit_score = min(
        95,
        45
        + (10 if attributes.get("summary") else 0)
        + (15 if attributes.get("requirements_text") else 0)
        + (10 if attributes.get("selection_process_text") else 0)
        + (10 if company_record else 0)
        + min(len(role_labels) * 3, 12)
        + (-5 if status == "closed" else 0),
    )
    strengths_summary = (
        f"Structured role and company evidence is available for {' / '.join(role_labels[:2])}."
        if role_labels
        else "Structured company and source evidence is available from the current WorkNet snapshot."
    )
    return {
        "fitScore": fit_score,
        "strengthsSummary": strengths_summary,
        "riskSummary": "Personal profile context is not provisioned in StrataWiki yet, so this fit remains source-only.",
    }


def _build_evidence(
    *,
    source_id: str,
    source_url: str | None,
    summary: object,
    requirements_text: object,
    fact_snapshot_id: str | None,
) -> list[dict[str, Any]]:
    return [
        _compact_object(
            {
                "evidenceId": f"evidence:worknet:{source_id}",
                "kind": "fact",
                "label": "Imported WorkNet opportunity record",
                "excerpt": _trim_text(summary, 240) or _trim_text(requirements_text, 240),
                "provenance": _compact_object(
                    {
                        "connector": "worknet",
                        "sourceId": source_id,
                        "sourceUrl": source_url,
                        "factSnapshotId": fact_snapshot_id,
                    }
                ),
            }
        )
    ]


def _compare_opportunities(left: dict[str, Any], right: dict[str, Any]) -> tuple[Any, ...]:
    left_priority = {
        "closing_soon": 0,
        "open": 1,
        "unknown": 2,
        "closed": 3,
    }.get(str(left.get("status")), 4)
    right_priority = {
        "closing_soon": 0,
        "open": 1,
        "unknown": 2,
        "closed": 3,
    }.get(str(right.get("status")), 4)
    return (
        left_priority,
        left.get("closingInDays") if left.get("closingInDays") is not None else 10**9,
        str(left.get("title") or ""),
        right_priority,
    )


def _build_provenance(*, domain: str, scope: str, sync: dict[str, Any]) -> dict[str, Any]:
    return _compact_object(
        {
            "authority": "stratawiki-http",
            "domain": domain,
            "scope": scope,
            "factSnapshotId": sync.get("version"),
        }
    )


def _normalize_scope_ref(scope: str) -> ScopeRef:
    return {"scope": scope}


def _load_projection(
    *,
    bootstrap: Any,
    domain: str,
    scope: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    fact_repository = getattr(bootstrap, "fact_repository", None)
    snapshot_repository = getattr(bootstrap, "snapshot_repository", None)
    if fact_repository is None or snapshot_repository is None:
        raise ValueError("Fact and snapshot repositories must be configured for HTTP read models.")

    scope_ref = _normalize_scope_ref(scope)
    postings = fact_repository.list_records(
        domain=domain,
        scope_ref=scope_ref,
        entity_type="job_posting",
        statuses=["active"],
        limit=1000,
    )
    companies = fact_repository.list_records(
        domain=domain,
        scope_ref=scope_ref,
        entity_type="company",
        statuses=["active"],
        limit=1000,
    )
    roles = fact_repository.list_records(
        domain=domain,
        scope_ref=scope_ref,
        entity_type="role",
        statuses=["active"],
        limit=1000,
    )
    relations = fact_repository.list_relations(
        domain=domain,
        scope_ref=scope_ref,
        relation_types=["posted_by", "for_role"],
        limit=5000,
    )
    snapshot_status = snapshot_repository.get_snapshot_status(domain=domain, layer="fact")
    current_snapshot_id = None if snapshot_status is None else snapshot_status.get("current_snapshot_id")
    outbox_repository = getattr(bootstrap, "outbox_repository", None)
    if (
        snapshot_status is not None
        and current_snapshot_id
        and "has_pending_outbox" not in snapshot_status
        and outbox_repository is not None
        and hasattr(outbox_repository, "has_pending_events_for_aggregate")
    ):
        snapshot_status = dict(snapshot_status)
        snapshot_status["has_pending_outbox"] = bool(
            outbox_repository.has_pending_events_for_aggregate(
                aggregate_layer="fact",
                aggregate_id=str(current_snapshot_id),
            )
        )

    company_by_key = {record["canonical_key"]: record for record in companies}
    role_by_key = {record["canonical_key"]: record for record in roles}
    company_key_by_posting_key: dict[str, str] = {}
    role_keys_by_posting_key: dict[str, list[str]] = {}

    for relation in relations:
        if relation["relation_type"] == "posted_by":
            company_key_by_posting_key[relation["from_canonical_key"]] = relation["to_canonical_key"]
            continue
        if relation["relation_type"] == "for_role":
            role_keys_by_posting_key.setdefault(relation["from_canonical_key"], []).append(
                relation["to_canonical_key"]
            )

    resolved_now = now or datetime.now(UTC)
    opportunity_items: list[dict[str, Any]] = []

    for posting_record in postings:
        canonical_key = posting_record["canonical_key"]
        source_id = canonical_key.split(":", 1)[1] if ":" in canonical_key else canonical_key
        attributes = posting_record.get("attributes") or {}
        company_record = company_by_key.get(company_key_by_posting_key.get(canonical_key, ""))
        role_labels = [
            label
            for label in (
                _get_role_label(role_by_key.get(role_key))
                for role_key in role_keys_by_posting_key.get(canonical_key, [])
            )
            if label
        ]
        closes_at_date = _parse_compact_date(attributes.get("closes_at"))
        closing_in_days = _compute_closing_in_days(closes_at_date, resolved_now)
        status = _derive_status(closing_in_days)
        company_attributes = (company_record or {}).get("attributes") or {}
        opportunity_items.append(
            _compact_object(
                {
                    "opportunityId": _encode_opportunity_id(canonical_key),
                    "objectId": canonical_key,
                    "canonicalKey": canonical_key,
                    "title": attributes.get("title") or canonical_key,
                    "companyName": company_attributes.get("name"),
                    "roleLabels": role_labels,
                    "summary": _trim_text(attributes.get("summary"), 280)
                    or attributes.get("title")
                    or canonical_key,
                    "employmentType": _trim_text(attributes.get("employment_type"), 120),
                    "opensAt": _format_kst_datetime(_parse_compact_date(attributes.get("opens_at"))),
                    "closesAt": _format_kst_datetime(closes_at_date, end_of_day=True),
                    "status": status,
                    "urgencyLabel": _derive_urgency_label(status, closing_in_days),
                    "closingInDays": closing_in_days,
                    "whyMatched": (
                        f"Role taxonomy captured: {', '.join(role_labels[:2])}"
                        if role_labels
                        else _trim_text(attributes.get("requirements_text"), 120)
                        or "Imported from the live WorkNet recruiting snapshot."
                    ),
                    "sourceLabel": "worknet",
                    "source": _compact_object(
                        {
                            "provider": "worknet",
                            "sourceId": source_id,
                            "sourceUrl": attributes.get("source_url"),
                        }
                    ),
                    "company": _compact_object(
                        {
                            "objectId": company_record["canonical_key"] if company_record else None,
                            "name": company_attributes.get("name"),
                            "summary": _trim_text(company_attributes.get("summary"), 200)
                            or _trim_text(company_attributes.get("description"), 200),
                            "homepageUrl": company_attributes.get("homepage_url"),
                            "mainBusiness": company_attributes.get("main_business"),
                        }
                    )
                    if company_record
                    else None,
                    "roles": [
                        {
                            "objectId": role_key,
                            "label": label,
                        }
                        for role_key, label in (
                            (role_key, _get_role_label(role_by_key.get(role_key)))
                            for role_key in role_keys_by_posting_key.get(canonical_key, [])
                        )
                        if label
                    ],
                    "qualification": _compact_object(
                        {
                            "locationText": _trim_text(attributes.get("location_text"), 240),
                            "requirementsText": _trim_text(attributes.get("requirements_text"), 1200),
                            "selectionProcessText": _trim_text(attributes.get("selection_process_text"), 1200),
                        }
                    ),
                    "analysis": _build_analysis(
                        attributes=attributes,
                        company_record=company_record,
                        role_labels=role_labels,
                        status=status,
                    ),
                    "descriptionMarkdown": _build_description_markdown(
                        attributes,
                        company_record,
                        role_labels,
                    ),
                    "evidence": _build_evidence(
                        source_id=source_id,
                        source_url=attributes.get("source_url"),
                        summary=attributes.get("summary"),
                        requirements_text=attributes.get("requirements_text"),
                        fact_snapshot_id=posting_record.get("fact_snapshot_id"),
                    ),
                    "calendarStartsAt": _format_kst_end_of_day_utc_iso(closes_at_date),
                    "factSnapshotId": posting_record.get("fact_snapshot_id"),
                    "updatedAt": posting_record.get("updated_at"),
                }
            )
        )

    opportunity_items.sort(
        key=lambda item: (
            {"closing_soon": 0, "open": 1, "unknown": 2, "closed": 3}.get(str(item.get("status")), 4),
            item.get("closingInDays") if item.get("closingInDays") is not None else 10**9,
            str(item.get("title") or ""),
        )
    )
    opportunity_by_id = {
        item["opportunityId"]: item
        for item in opportunity_items
    }
    fallback_version = opportunity_items[0].get("factSnapshotId") if opportunity_items else None
    sync = _create_projection_sync(snapshot_status, fallback_version)
    company_names = list(dict.fromkeys(item["companyName"] for item in opportunity_items if item.get("companyName")))
    role_labels = list(
        dict.fromkeys(label for item in opportunity_items for label in item.get("roleLabels", []) if label)
    )

    return {
        "sync": sync,
        "opportunityItems": opportunity_items,
        "opportunityById": opportunity_by_id,
        "companyNames": company_names,
        "roleLabels": role_labels,
    }


def build_workspace_summary_payload(
    *,
    bootstrap: Any,
    domain: str,
    scope: str,
    profile_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    read_model = _load_projection(bootstrap=bootstrap, domain=domain, scope=scope, now=now)
    recommended_opportunities = [
        item for item in read_model["opportunityItems"] if item.get("status") != "closed"
    ][:3]
    highlighted_opportunity = (
        recommended_opportunities[0] if recommended_opportunities else (read_model["opportunityItems"][0] if read_model["opportunityItems"] else None)
    )
    return {
        "profileSnapshot": {
            "targetRole": (
                f"Profile {profile_id} pending context hydration"
                if profile_id
                else "Profile context pending"
            ),
            "experience": "Personal profile context is not provisioned in StrataWiki yet.",
            "education": "N/A",
            "location": (
                ((highlighted_opportunity or {}).get("qualification") or {}).get("locationText")
                or "Multiple locations in current recruiting snapshot"
            ),
            "domain": domain,
            "skills": read_model["roleLabels"][:4],
            "sourceSummary": [
                f"{len(read_model['opportunityItems'])} ingested opportunities",
                f"{len(read_model['companyNames'])} companies",
                f"{len(read_model['roleLabels'])} role signals",
            ],
        },
        "recommendedOpportunities": recommended_opportunities,
        "marketBrief": {
            "signals": [
                f"{len(read_model['opportunityItems'])} live recruiting opportunities are visible in the current snapshot.",
                (
                    f"Latest fact snapshot published at {read_model['sync'].get('visibleAt')}."
                    if read_model["sync"].get("visibleAt")
                    else "No published fact snapshot metadata is currently available."
                ),
            ],
            "risingSkills": read_model["roleLabels"][:3],
            "notableCompanies": read_model["companyNames"][:3],
        },
        "skillsGap": {
            "strong": [
                "Canonical opportunity ingestion is live.",
                "Company and role joins are available for current postings.",
            ],
            "requested": read_model["roleLabels"][:3],
            "recommendedToStrengthen": [
                "Provision personal profile context",
                "Publish interpretation snapshots",
                "Enable evidence-backed fit scoring",
            ],
        },
        "actionQueue": [
            _compact_object(
                {
                    "actionId": f"action_review_{index + 1}_{item['opportunityId']}",
                    "label": f"Review {item['title']}",
                    "description": (
                        f"{item['companyName']} closes on {item['urgencyLabel']}."
                        if item.get("urgencyLabel") and item.get("companyName")
                        else f"Review the latest imported opportunity: {item['title']}."
                    ),
                    "relatedOpportunityId": item["opportunityId"],
                    "relatedOpportunityTitle": item["title"],
                }
            )
            for index, item in enumerate(recommended_opportunities[:2])
        ],
        "askFollowUps": [
            "Which imported opportunities are closing soonest?",
            "What profile context is missing before source-only fit can become personalized?",
        ],
        "sync": read_model["sync"],
        "provenance": _build_provenance(domain=domain, scope=scope, sync=read_model["sync"]),
    }


def list_opportunities_payload(
    *,
    bootstrap: Any,
    domain: str,
    scope: str,
    status: str | None = None,
    closing_within_days: int | None = None,
    cursor_offset: int = 0,
    limit: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    read_model = _load_projection(bootstrap=bootstrap, domain=domain, scope=scope, now=now)
    filtered_items = []
    for item in read_model["opportunityItems"]:
        if status and item.get("status") != status:
            continue
        closing_in_days = item.get("closingInDays")
        if (
            closing_within_days is not None
            and (closing_in_days is None or closing_in_days > closing_within_days)
        ):
            continue
        filtered_items.append(item)
    start_index = max(cursor_offset, 0)
    resolved_limit = len(filtered_items) if limit is None else max(limit, 0)
    items = filtered_items[start_index : start_index + resolved_limit]
    next_offset = start_index + len(items)
    return _compact_object(
        {
            "items": items,
            "nextCursor": format_opportunity_cursor(next_offset) if next_offset < len(filtered_items) else None,
            "sync": read_model["sync"],
            "provenance": _build_provenance(domain=domain, scope=scope, sync=read_model["sync"]),
        }
    )


def get_opportunity_detail_payload(
    *,
    bootstrap: Any,
    domain: str,
    scope: str,
    opportunity_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    read_model = _load_projection(bootstrap=bootstrap, domain=domain, scope=scope, now=now)
    record = read_model["opportunityById"].get(opportunity_id)
    canonical_key = decode_opportunity_id(opportunity_id)
    if not record or canonical_key != record.get("canonicalKey"):
        raise KeyError(f"Unknown opportunity: {opportunity_id}")
    return _compact_object(
        {
            "opportunityId": record["opportunityId"],
            "objectId": record["objectId"],
            "title": record["title"],
            "summary": record["summary"],
            "descriptionMarkdown": record["descriptionMarkdown"],
            "employmentType": record.get("employmentType"),
            "opensAt": record.get("opensAt"),
            "closesAt": record.get("closesAt"),
            "status": record["status"],
            "source": record["source"],
            "company": record.get("company"),
            "roles": record.get("roles", []),
            "qualification": record.get("qualification", {}),
            "analysis": record["analysis"],
            "evidence": record["evidence"],
            "sync": read_model["sync"],
            "provenance": _build_provenance(domain=domain, scope=scope, sync=read_model["sync"]),
        }
    )


def get_calendar_payload(
    *,
    bootstrap: Any,
    domain: str,
    scope: str,
    from_date: str | None = None,
    to_date: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    read_model = _load_projection(bootstrap=bootstrap, domain=domain, scope=scope, now=now)
    filtered_items: list[dict[str, Any]] = []
    for item in read_model["opportunityItems"]:
        starts_at = item.get("calendarStartsAt")
        if not starts_at:
            continue
        starts_at_dt = datetime.fromisoformat(str(starts_at).replace("Z", "+00:00"))
        if from_date and starts_at_dt < datetime.fromisoformat(f"{from_date}T00:00:00+00:00"):
            continue
        if to_date and starts_at_dt > datetime.fromisoformat(f"{to_date}T23:59:59.999000+00:00"):
            continue
        filtered_items.append(
            _compact_object(
                {
                    "calendarItemId": f"calendar_{item['opportunityId']}",
                    "kind": "opportunity_deadline",
                    "label": f"{item['title']} closes",
                    "startsAt": starts_at,
                    "opportunityId": item["opportunityId"],
                    "objectId": item["objectId"],
                    "objectKind": "opportunity",
                    "objectTitle": item["title"],
                    "urgencyLabel": item.get("urgencyLabel"),
                    "companyName": item.get("companyName"),
                }
            )
        )
    filtered_items.sort(key=lambda item: datetime.fromisoformat(item["startsAt"].replace("Z", "+00:00")))
    return {
        "items": filtered_items,
        "sync": read_model["sync"],
        "provenance": _build_provenance(domain=domain, scope=scope, sync=read_model["sync"]),
    }
