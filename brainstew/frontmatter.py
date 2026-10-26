"""Frontmatter parsing for wiki pages."""

import datetime

_FIELDS = {"title", "type", "summary", "sources", "updated", "tags"}


class FrontmatterError(ValueError):
    """Raised when a frontmatter block is malformed."""


def _parse_date(value: str) -> None:
    try:
        datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise FrontmatterError(f"updated is not YYYY-MM-DD: {value}") from exc


def _parse_value(key: str, raw: str) -> str | list[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [item.strip() for item in inner.split(",")]
    if "," in raw or ":" in raw:
        raise FrontmatterError(f"invalid scalar value for {key}")
    if key == "updated":
        _parse_date(raw)
    return raw


def parse_frontmatter(text: str) -> tuple[dict[str, str | list[str]], str]:
    """Parse a `---` fenced frontmatter block; return (meta, body)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError("first line is not '---'")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise FrontmatterError("no closing '---' fence")
    meta: dict[str, str | list[str]] = {}
    for line in lines[1:end]:
        stripped = line.strip()
        if not stripped:
            continue
        key, sep, raw = stripped.partition(":")
        if not sep:
            raise FrontmatterError(f"invalid frontmatter line: {line.strip()}")
        key = key.strip()
        if not key or key not in _FIELDS:
            raise FrontmatterError(f"unknown or invalid key: {key}")
        meta[key] = _parse_value(key, raw)
    return meta, "\n".join(lines[end + 1:]).strip()
