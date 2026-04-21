from __future__ import annotations

from wiki_mcp.prompts import (
    DEFAULT_PROMPT_LANGUAGE,
    PromptCatalog,
    resolve_prompt_language,
    resolve_prompt_version,
)


def test_resolve_prompt_language_defaults_to_english() -> None:
    assert resolve_prompt_language(environ={}) == DEFAULT_PROMPT_LANGUAGE
    assert resolve_prompt_language(environ={"WIKI_MCP_PROMPT_LANGUAGE": "ko"}) == "ko"
    assert resolve_prompt_language(environ={"WIKI_MCP_PROMPT_LANGUAGE": "invalid"}) == "en"


def test_resolve_prompt_version_suffixes_non_default_language() -> None:
    assert resolve_prompt_version("personal.query.answer.v1", "en") == "personal.query.answer.v1"
    assert resolve_prompt_version("personal.query.answer.v1", "ko") == "personal.query.answer.v1.ko"


def test_prompt_catalog_reads_korean_generation_templates() -> None:
    catalog = PromptCatalog(language="ko")

    system_prompt = catalog.read_text("personal_generation", "system")
    operation_prompt = catalog.render(
        "personal_generation",
        "operation_summarize",
        instruction_value="간결하게",
    )

    assert "Personal raw 노트" in system_prompt
    assert "간결한 wiki 문서로 요약" in operation_prompt
