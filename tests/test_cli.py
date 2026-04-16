from __future__ import annotations

import io
import json
from pathlib import Path

from wiki_mcp.cli import run_cli
from wiki_mcp.tools import build_default_tool_registry


class StubIngestionEntrypoint:
    def ingest_source(self, source: dict[str, object]) -> dict[str, object]:
        return {"ok": True, "source": source}

    def ingest_worknet_source(
        self,
        provider: object,
        source_id: str,
        *,
        auth_key: str | None = None,
        include_raw: bool = False,
    ) -> dict[str, object]:
        return {
            "ok": True,
            "provider": provider,
            "source_id": source_id,
            "auth_key": auth_key,
            "include_raw": include_raw,
        }


class StubPageReadEntrypoint:
    def get_page(self, **kwargs: object) -> dict[str, object]:
        return {"ok": True, "page": kwargs}

    def list_pages(self, **kwargs: object) -> dict[str, object]:
        return {"ok": True, "pages": [], **kwargs}

    def get_personal_page(self, **kwargs: object) -> dict[str, object]:
        return {"ok": True, "page": kwargs}

    def list_personal_pages(self, **kwargs: object) -> dict[str, object]:
        return {"ok": True, "pages": [], **kwargs}

    def get_interpretation_page(self, **kwargs: object) -> dict[str, object]:
        return {"ok": True, "page": kwargs}

    def list_interpretation_pages(self, **kwargs: object) -> dict[str, object]:
        return {"ok": True, "pages": [], **kwargs}


class StubRetrievalReadEntrypoint:
    def retrieve_for_query(self, **kwargs: object) -> dict[str, object]:
        return {"ok": True, "retrieval": kwargs}


class StubPersonalQueryEntrypoint:
    def query_personal_knowledge(self, **kwargs: object) -> dict[str, object]:
        return {
            "ok": True,
            "projection": {
                "family": "answer",
                "kind": "personal_query",
                "scope": kwargs["scope_ref"]["scope"],
                "layers": ["personal", "interpretation", "fact"],
            },
            "retrieval": {"question": kwargs["question"]},
            "answer": {
                "answer_type": "personal_query_answer",
                "generation_strategy": "deterministic_summary_bundle_v1",
                "personal_family": "career_transition_plan",
                "question": kwargs["question"],
                "answer_summary": "summary",
                "answer_rationale": "rationale",
                "answer_rationale_items": [],
                "answer_markdown": "# title",
                "recommended_actions": [],
                "citations": [],
                "input_bundle": {
                    "question": kwargs["question"],
                    "scope_ref": kwargs["scope_ref"],
                    "personal_context": [],
                    "interpretation_context": [],
                    "fact_context": [],
                },
            },
        }


class StubServer:
    def __init__(self) -> None:
        self.closed = False
        self.tools = build_default_tool_registry(
            ingestion_entrypoint=StubIngestionEntrypoint(),
            page_read_entrypoint=StubPageReadEntrypoint(),
            retrieval_read_entrypoint=StubRetrievalReadEntrypoint(),
            personal_query_entrypoint=StubPersonalQueryEntrypoint(),
        )

    def list_tools(self):  # noqa: ANN201
        return self.tools.list_tools()

    def export_tool_schemas(self) -> list[dict[str, object]]:
        return self.tools.export_tool_schemas()

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> object:
        return self.tools.call_tool(name, arguments)

    def call_tool_with_envelope(
        self,
        name: str,
        arguments: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return self.tools.call_tool_with_envelope(name, arguments)

    def close(self) -> None:
        self.closed = True


def build_stub_server(**_: object) -> StubServer:
    return StubServer()


def test_cli_lists_registered_tools() -> None:
    stdout = io.StringIO()

    exit_code = run_cli(
        ["list-tools"],
        server_factory=build_stub_server,
        stdout=stdout,
        stderr=io.StringIO(),
    )

    payload = json.loads(stdout.getvalue())

    assert exit_code == 0
    assert any(item["name"] == "retrieve_for_query" for item in payload)
    assert any(item["name"] == "query_personal_knowledge" for item in payload)


def test_cli_can_show_one_tool_schema() -> None:
    stdout = io.StringIO()

    exit_code = run_cli(
        ["show-tool", "query_personal_knowledge"],
        server_factory=build_stub_server,
        stdout=stdout,
        stderr=io.StringIO(),
    )

    payload = json.loads(stdout.getvalue())

    assert exit_code == 0
    assert payload["name"] == "query_personal_knowledge"
    assert payload["entrypoint"] == "personal.query_knowledge"


def test_cli_can_call_tool_with_inline_json_arguments() -> None:
    stdout = io.StringIO()

    exit_code = run_cli(
        [
            "call",
            "retrieve_for_query",
            "--args",
            json.dumps(
                {
                    "domain": "recruiting",
                    "question": "backend transition plan",
                    "scope_ref": {
                        "scope": "user",
                        "tenant_id": "tenant-1",
                        "user_id": "user-1",
                    },
                }
            ),
        ],
        server_factory=build_stub_server,
        stdout=stdout,
        stderr=io.StringIO(),
    )

    payload = json.loads(stdout.getvalue())

    assert exit_code == 0
    assert payload["retrieval"]["question"] == "backend transition plan"


def test_cli_can_call_tool_with_args_file_and_envelope(tmp_path: Path) -> None:
    arguments_path = tmp_path / "args.json"
    arguments_path.write_text(
        json.dumps(
            {
                "domain": "recruiting",
                "question": "what should I do this week?",
                "scope_ref": {
                    "scope": "user",
                    "tenant_id": "tenant-1",
                    "user_id": "user-1",
                },
            }
        ),
        encoding="utf-8",
    )
    stdout = io.StringIO()

    exit_code = run_cli(
        [
            "call",
            "query_personal_knowledge",
            "--args-file",
            str(arguments_path),
            "--envelope",
        ],
        server_factory=build_stub_server,
        stdout=stdout,
        stderr=io.StringIO(),
    )

    payload = json.loads(stdout.getvalue())

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["result"]["answer"]["personal_family"] == "career_transition_plan"
