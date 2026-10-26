"""Tests for the frontmatter parser."""

from pathlib import Path

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


def test_unknown_key_still_rejected_with_field_set_only() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\nauthor: Someone\n---\n")
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\n: novalue\n---\n")


def test_invalid_date() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\nupdated: 2026-13-45\n---\n")


def test_compact_date_rejected() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\nupdated: 20260120\n---\n")


def test_week_date_rejected() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\nupdated: 2026-W04-2\n---\n")


def test_impossible_calendar_date_rejected() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\nupdated: 2026-02-30\n---\n")


def test_date_shape_and_validity_both_required() -> None:
    # Right shape, impossible calendar date.
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\nupdated: 2026-99-99\n---\n")
    # Wrong shape entirely.
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\nupdated: 20-01-20\n---\n")


def test_comma_in_scalar() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\ntitle: a, b\n---\n")


def test_empty_list_rejected() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\ntags: []\n---\n")


def test_empty_text() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("")


def test_duplicate_key_rejected() -> None:
    text = BASE.replace(
        "summary: A lens summary.\n",
        "summary: A lens summary.\nsummary: Another summary.\n",
    )
    with pytest.raises(FrontmatterError):
        parse_frontmatter(text)


def test_duplicate_key_via_lint(tmp_path) -> None:
    from brainstew.lint import lint

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    text = BASE.replace(
        "summary: A lens summary.\n",
        "summary: A lens summary.\nsummary: Another summary.\n",
    )
    (wiki / "sources" / "dup.md").write_text(text, encoding="utf-8")
    (wiki / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    (wiki / "log.md").write_text("# Wiki Log\n", encoding="utf-8")
    issues = lint(wiki)
    fm02 = [i for i in issues if i.code == "FM02" and i.path == "wiki/sources/dup.md"]
    assert len(fm02) == 1


def test_quoted_scalar_rejected() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter('---\ntitle: "A lens summary"\n---\n')
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\ntitle: 'A lens summary'\n---\n")


def test_malformed_list_bracket_rejected() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\ntags: [item1, item2\n---\n")
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\ntags: item1, item2]\n---\n")
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\ntags: [item1, [item2]]\n---\n")


def test_no_duplicate_keys_parses_cleanly() -> None:
    meta, body = parse_frontmatter(valid_text())
    assert meta["title"] == "Fresnel Lens"
    assert body == "Body text."
