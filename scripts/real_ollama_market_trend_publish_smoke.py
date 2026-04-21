from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wiki_mcp.adapters.llm.config import resolve_ollama_model_for_profile
from wiki_mcp.bootstrap import DEFAULT_DATABASE_URL
from wiki_mcp.cli import load_nearest_env_file


class SmokeFailure(RuntimeError):
    pass


def _request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = None
    headers = {"Accept": "application/json"}
    if body is not None:
        payload = json.dumps(body, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=payload,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise SmokeFailure(
            f"HTTP request failed for {method} {path}: {exc.code} {exc.reason} {message}"
        ) from exc
    except URLError as exc:
        raise SmokeFailure(f"HTTP request failed for {method} {path}: {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SmokeFailure(
            f"HTTP request returned non-JSON output for {method} {path}: {raw[:400]}"
        ) from exc


def _assert_ok(payload: dict[str, Any], *, label: str) -> dict[str, Any]:
    if payload.get("ok") is not True:
        raise SmokeFailure(f"{label} did not return ok=true: {json.dumps(payload, ensure_ascii=False)}")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise SmokeFailure(f"{label} returned an unexpected result payload: {json.dumps(payload, ensure_ascii=False)}")
    return result


def _tags_path_for_ollama(base_url: str) -> str:
    parsed = urlparse(base_url)
    path = parsed.path.rstrip("/")
    if not path:
        path = "/api"
    return f"{path}/tags"


def _verify_ollama_ready(*, ollama_base_url: str, expected_model: str) -> None:
    parsed = urlparse(ollama_base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    try:
        payload = _request_json(origin, _tags_path_for_ollama(ollama_base_url))
    except SmokeFailure as exc:
        raise SmokeFailure(
            f"Ollama runtime is unreachable or unhealthy. Start Ollama locally and ensure OLLAMA_BASE_URL is correct. {exc}"
        ) from exc

    models = payload.get("models")
    if not isinstance(models, list):
        raise SmokeFailure(f"Ollama /tags returned an unexpected payload: {json.dumps(payload, ensure_ascii=False)}")

    available_models = sorted(
        {
            str(model.get("name")).strip()
            for model in models
            if isinstance(model, dict) and str(model.get("name", "")).strip()
        }
    )
    if expected_model not in available_models:
        raise SmokeFailure(
            "Configured Ollama model is not available locally. "
            f"Expected {expected_model!r}, available={available_models}"
        )


def _connect_smoke_database():
    import psycopg
    from psycopg.rows import dict_row

    candidate_urls = list(
        dict.fromkeys(
            [
                os.environ.get("DATABASE_URL", "").strip() or None,
                DEFAULT_DATABASE_URL,
                "postgresql://stratawiki:stratawiki@localhost:5432/stratawiki_jobswiki",
            ]
        )
    )
    last_error: Exception | None = None
    for candidate in candidate_urls:
        if not candidate:
            continue
        try:
            connection = psycopg.connect(candidate, row_factory=dict_row)
            return connection, candidate
        except Exception as exc:  # pragma: no cover - only exercised in live smoke
            last_error = exc
    raise SmokeFailure(
        "Could not connect to a Postgres database for live smoke verification. "
        f"Tried candidates={candidate_urls}. Last error={last_error}"
    )


def _select_fact_ids(*, domain: str, fact_snapshot_id: str, limit: int = 5) -> list[str]:
    connection, _ = _connect_smoke_database()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM fact.record_envelopes
                WHERE domain = %s
                  AND scope = 'shared'
                  AND status = 'active'
                  AND fact_snapshot_id = %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (domain, fact_snapshot_id, limit),
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    fact_ids = [str(row["id"]) for row in rows if row.get("id")]
    if not fact_ids:
        raise SmokeFailure(
            f"No shared facts were found for domain={domain!r} and fact_snapshot={fact_snapshot_id!r}."
        )
    return fact_ids


def _fetch_published_record(*, domain: str, subject_id: str) -> dict[str, Any]:
    connection, _ = _connect_smoke_database()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    status,
                    title,
                    claim,
                    summary,
                    interpretation_snapshot_id,
                    provenance_json
                FROM interp.record
                WHERE domain = %s
                  AND family = 'market_trend'
                  AND scope = 'shared'
                  AND subject_id = %s
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (domain, subject_id),
            )
            row = cursor.fetchone()
    finally:
        connection.close()

    if row is None:
        raise SmokeFailure(
            f"No interpretation record was found after publish for subject_id={subject_id!r}."
        )
    return dict(row)


def main() -> int:
    loaded_env_file = load_nearest_env_file(cwd=REPO_ROOT)
    if loaded_env_file is not None:
        print(f"[live-market-trend-smoke] env file: {loaded_env_file}")

    stratawiki_base_url = os.environ.get("STRATAWIKI_BASE_URL", "http://127.0.0.1:18080").rstrip("/")
    ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/api").rstrip("/")
    domain = os.environ.get("STRATAWIKI_LIVE_SMOKE_DOMAIN", "recruiting").strip()
    model_profile = os.environ.get("STRATAWIKI_LIVE_SMOKE_MODEL_PROFILE", "balanced_default").strip()
    expected_model = resolve_ollama_model_for_profile(model_profile, environ=os.environ)
    connection, database_url = _connect_smoke_database()
    connection.close()
    print(f"[live-market-trend-smoke] database: {database_url}")

    health = _assert_ok(_request_json(stratawiki_base_url, "/healthz"), label="healthz")
    if health.get("status") != "ok":
        raise SmokeFailure(f"StrataWiki runtime is not healthy: {json.dumps(health, ensure_ascii=False)}")

    _verify_ollama_ready(ollama_base_url=ollama_base_url, expected_model=expected_model)

    snapshot_result = _assert_ok(
        _request_json(
            stratawiki_base_url,
            f"/api/v1/snapshot-status?{urlencode({'domain': domain})}",
        ),
        label="snapshot-status",
    )
    fact_snapshot = snapshot_result.get("fact_snapshot")
    if not isinstance(fact_snapshot, str) or not fact_snapshot.strip():
        raise SmokeFailure(
            f"Snapshot status did not include a current fact snapshot for domain={domain!r}: "
            f"{json.dumps(snapshot_result, ensure_ascii=False)}"
        )

    fact_ids = _select_fact_ids(domain=domain, fact_snapshot_id=fact_snapshot)
    subject_id = f"live-ollama-market-trend-smoke-{uuid4().hex[:10]}"

    build_payload = {
        "domain": domain,
        "partition": {
            "family": "market_trends",
            "segment": subject_id,
        },
        "fact_ids": fact_ids,
        "fact_snapshot": fact_snapshot,
        "model_profile": model_profile,
        "publish": True,
    }
    build_result = _assert_ok(
        _request_json(
            stratawiki_base_url,
            "/api/v1/interpretation-builds",
            method="POST",
            body=build_payload,
        ),
        label="interpretation-build",
    )
    if build_result.get("status") != "ok":
        raise SmokeFailure(
            f"Interpretation build did not complete successfully: {json.dumps(build_result, ensure_ascii=False)}"
        )
    if not build_result.get("interpretation_snapshot"):
        raise SmokeFailure(
            f"Interpretation build did not publish a snapshot: {json.dumps(build_result, ensure_ascii=False)}"
        )

    record = _fetch_published_record(domain=domain, subject_id=subject_id)
    generated_by = {}
    provenance = record.get("provenance_json")
    if isinstance(provenance, dict):
        generated_by = provenance.get("generated_by") or {}
    if record.get("status") != "published":
        raise SmokeFailure(f"Published interpretation record has unexpected status: {record}")
    if generated_by.get("provider") != "ollama":
        raise SmokeFailure(f"Published interpretation was not generated by Ollama: {record}")
    if generated_by.get("model") != expected_model:
        raise SmokeFailure(
            f"Published interpretation used an unexpected model. expected={expected_model!r} record={record}"
        )
    if not generated_by.get("prompt_version"):
        raise SmokeFailure(f"Published interpretation is missing prompt metadata: {record}")

    print(
        json.dumps(
            {
                "status": "ok",
                "domain": domain,
                "subject_id": subject_id,
                "fact_snapshot": fact_snapshot,
                "fact_ids": fact_ids,
                "record_id": record["id"],
                "interpretation_snapshot_id": record["interpretation_snapshot_id"],
                "provider": generated_by.get("provider"),
                "model": generated_by.get("model"),
                "prompt_version": generated_by.get("prompt_version"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(f"[live-market-trend-smoke] failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
