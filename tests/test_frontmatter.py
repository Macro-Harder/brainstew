"""Tests for the frontmatter parser."""

import pytest

from brainstew.frontmatter import FrontmatterError, parse_frontmatter

BASE = (
    "---\n"
    "title: Fresnel Lens\n"
    "type: source\n"
    "summary: A lens summary.\n"
    "sources: [raw/fresnel-lens.txt, fresnel-lens]\n"
    "updated: 2026-01-20\n"
    "tags: [optics, light]\n"
    "---\n"
)


def valid_text() -> str:
    return BASE + "\nBody text.\n"


def test_valid_scalars_and_lists() -> None:
    meta, body = parse_frontmatter(valid_text())
    assert meta["title"] == "Fresnel Lens"
    assert meta["type"] == "source"
    assert meta["summary"] == "A lens summary."
    assert meta["sources"] == ["raw/fresnel-lens.txt", "fresnel-lens"]
    assert meta["updated"] == "2026-01-20"
    assert meta["tags"] == ["optics", "light"]
    assert body == "Body text."


def test_body_spans_multiple_lines() -> None:
    _, body = parse_frontmatter(BASE + "\n# Heading\n\nPara.\n")
    assert body == "# Heading\n\nPara."


def test_missing_required_field_is_parser_neutral_but_detectable() -> None:
    text = BASE.replace("updated: 2026-01-20\n", "")
    meta, _ = parse_frontmatter(text)
    assert "updated" not in meta


def test_first_line_not_fence() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("title: X\n---\n")


def test_no_closing_fence() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\ntitle: X\n")


def test_line_without_colon() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\ntitle\n---\n")


def test_unknown_key() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\nauthor: Someone\n---\n")


def test_invalid_date() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\nupdated: 2026-13-45\n---\n")


def test_comma_in_scalar() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\ntitle: a, b\n---\n")


def test_empty_list() -> None:
    meta, _ = parse_frontmatter("---\ntags: []\n---\n")
    assert meta["tags"] == []


def test_empty_text() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("")
