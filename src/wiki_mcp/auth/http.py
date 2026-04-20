from __future__ import annotations

import os
from collections.abc import Mapping


DEFAULT_HTTP_AUTH_TOKEN_ENV = "STRATAWIKI_HTTP_AUTH_TOKEN"


def resolve_http_auth_token(token: str | None = None) -> str | None:
    if token is not None:
        normalized = str(token).strip()
        return normalized or None

    raw = os.environ.get(DEFAULT_HTTP_AUTH_TOKEN_ENV, "").strip()
    return raw or None


def resolve_bearer_token(headers: Mapping[str, str] | None) -> str | None:
    if headers is None:
        return None
    normalized_headers = {str(key).lower(): str(value) for key, value in headers.items()}
    raw = normalized_headers.get("authorization")
    if raw is None:
        return None
    scheme, _, value = raw.partition(" ")
    if scheme.lower() != "bearer":
        return None
    normalized = value.strip()
    return normalized or None
