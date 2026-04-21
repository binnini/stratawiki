from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from string import Template

DEFAULT_PROMPT_LANGUAGE = "en"
SUPPORTED_PROMPT_LANGUAGES = {"en", "ko"}


def resolve_prompt_language(*, environ: dict[str, str] | None = None) -> str:
    env = environ or os.environ
    configured = env.get("WIKI_MCP_PROMPT_LANGUAGE", "").strip().lower()
    if configured in SUPPORTED_PROMPT_LANGUAGES:
        return configured
    return DEFAULT_PROMPT_LANGUAGE


def resolve_prompt_version(base_version: str, language: str) -> str:
    if language == DEFAULT_PROMPT_LANGUAGE:
        return base_version
    return f"{base_version}.{language}"


@lru_cache(maxsize=64)
def _read_template(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").rstrip()


class PromptCatalog:
    def __init__(
        self,
        *,
        language: str | None = None,
        base_path: Path | None = None,
    ) -> None:
        resolved_language = (language or DEFAULT_PROMPT_LANGUAGE).strip().lower()
        if resolved_language not in SUPPORTED_PROMPT_LANGUAGES:
            raise ValueError(
                f"Unsupported prompt language: {resolved_language!r}. "
                f"Expected one of {sorted(SUPPORTED_PROMPT_LANGUAGES)}."
            )
        self.language = resolved_language
        self.base_path = base_path or Path(__file__).resolve().parent / "templates"

    def read_text(self, namespace: str, template_name: str) -> str:
        template_path = self.base_path / namespace / self.language / f"{template_name}.txt"
        if not template_path.exists():
            raise FileNotFoundError(f"Unknown prompt template: {template_path}")
        return _read_template(str(template_path))

    def render(self, namespace: str, template_name: str, **values: object) -> str:
        normalized_values = {
            key: value if isinstance(value, str) else str(value)
            for key, value in values.items()
        }
        return Template(self.read_text(namespace, template_name)).safe_substitute(
            normalized_values
        )
