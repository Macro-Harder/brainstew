"""Frontmatter parsing for wiki pages."""

import datetime
import re

_FIELDS = {"title", "type", "summary", "sources", "updated", "tags"}
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


class FrontmatterError(ValueError):
    """Raised when a frontmatter block is malformed."""


def _parse_date(value: str) -> None:
    if not _DATE_RE.fullmatch(value):
        raise FrontmatterError(f"updated is not YYYY-MM-DD: {value}")
    try:
        datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise FrontmatterError(f"updated is not YYYY-MM-DD: {value}") from exc


def _parse_value(key: str, raw: str) -> str | list[str]:
    raw = raw.strip()
    if '"' in raw or "'" in raw:
        raise FrontmatterError(f"quoted value not allowed for {key}")
    if "[" in raw or "]" in raw:
        if not (raw.startswith("[") and raw.endswith("]")):
            raise FrontmatterError(f"invalid inline list for {key}: {raw}")
        inner = raw[1:-1]
        if "[" in inner or "]" in inner:
            raise FrontmatterError(f"nested brackets in inline list for {key}: {raw}")
        inner = inner.strip()
        if not inner:
            raise FrontmatterError(f"empty inline list for {key}")
        items = [item.strip() for item in inner.split(",")]
        if any(not item for item in items):
            raise FrontmatterError(f"empty item in inline list for {key}: {raw}")
        return items
    if "," in raw or ":" in raw:
        raise FrontmatterError(f"invalid scalar value for {key}")
    if key == "updated":
        _parse_date(raw)
    return raw


def parse_frontmatter(text: str) -> tuple[dict[str, str | list[str]], str]:
    """Parse a `---` fenced frontmatter block; return (meta, body)."""
    text = text.lstrip("﻿")
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
        if line != line.lstrip():
            raise FrontmatterError(f"indented frontmatter line: {stripped}")
        key, sep, raw = stripped.partition(":")
        if not sep:
            raise FrontmatterError(f"invalid frontmatter line: {line.strip()}")
        key = key.strip()
        if not key or key not in _FIELDS:
            raise FrontmatterError(f"unknown or invalid key: {key}")
        if key in meta:
            raise FrontmatterError(f"duplicate key: {key}")
        meta[key] = _parse_value(key, raw)
    return meta, "\n".join(lines[end + 1:]).strip()
