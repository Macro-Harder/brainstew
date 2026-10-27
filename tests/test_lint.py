"""Tests for lint: one positive and one clean negative per code."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from brainstew.lint import Issue, lint

FM = (
    "---\n"
    "title: {title}\n"
    "type: {type}\n"
    "summary: {summary}\n"
    "sources: [raw/a.txt]\n"
    "updated: {updated}\n"
    "---\n"
    "\n"
    "{body}\n"
)

INDEX = (
    "# Wiki Index\n"
    "\n"
    "## Sources\n"
    "- [[alpha]] - Alpha summary\n"
    "\n"
    "## Entities\n"
    "- [[beta]] - Beta summary\n"
    "\n"
    "## Concepts\n"
    "\n"
    "## Synthesis\n"
)
LOG = "# Wiki Log\n\n## [2026-01-20] ingest | First\n- did a thing\n"


def write(wiki: Path, rel: str, text: str) -> None:
    p = wiki / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


TYPE_OF = {"sources": "source", "entities": "entity", "concepts": "concept", "synthesis": "synthesis"}


def page(title: str, folder: str, body: str = "Body.", updated: str = "2026-01-20") -> str:
    return FM.format(title=title, type=TYPE_OF[folder], summary=f"{title} summary", body=body, updated=updated)


def make_wiki(tmp_path: Path) -> Path:
    wiki = tmp_path / "wiki"
    write(wiki, "sources/alpha.md", page("Alpha", "sources", "See [[beta]]."))
    write(wiki, "entities/beta.md", page("Beta", "entities", "See [[alpha]]."))
    write(wiki, "index.md", INDEX)
    write(wiki, "log.md", LOG)
    return wiki


def codes(issues: list[Issue]) -> list[str]:
    return [i.code for i in issues]


def test_clean_wiki(tmp_path: Path) -> None:
    assert lint(make_wiki(tmp_path)) == []


def test_finding_f21_nonexistent_raw_path_rejected(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", page("Alpha", "sources").replace("sources: [raw/a.txt]", "sources: [raw/missing.txt]"))
    (wiki.parent / "raw").mkdir()
    assert "FM02" in codes(lint(wiki))


def test_finding_f21_negative_existing_raw_path_accepted(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki.parent, "raw/a.txt", "content")
    assert lint(wiki) == []


def test_fm01_missing_required_field(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    text = page("Alpha", "sources", "See [[beta]].").replace("summary: Alpha summary\n", "")
    write(wiki, "sources/alpha.md", text)
    assert "FM01" in codes(lint(wiki))


def test_fm01_negative_has_all_fields(tmp_path: Path) -> None:
    assert "FM01" not in codes(lint(make_wiki(tmp_path)))


def test_fm02_first_line_not_fence(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", "title: Alpha\n---\n")
    assert "FM02" in codes(lint(wiki))


def test_fm02_no_closing_fence(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", "---\ntitle: Alpha\n")
    assert "FM02" in codes(lint(wiki))


def test_fm02_invalid_date(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", page("Alpha", "sources", "See [[beta]].", updated="2026-13-40"))
    assert "FM02" in codes(lint(wiki))


def test_fm02_date_field_is_reported_via_frontmatter_error_only_once(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", page("Alpha", "sources", "See [[beta]].", updated="2026-13-40"))
    issues = lint(wiki)
    assert codes(issues).count("FM02") == 1


def test_fm02_negative_valid_date(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", page("Alpha", "sources", "See [[beta]].", updated="2026-02-28"))
    assert "FM02" not in codes(lint(wiki))


def test_ty01_type_mismatch(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", page("Alpha", "sources", "See [[beta]].").replace("type: source", "type: concept"))
    issues = lint(wiki)
    assert "TY01" in codes(issues)
    assert "OR01" not in codes(issues)


def test_ty01_negative(tmp_path: Path) -> None:
    assert "TY01" not in codes(lint(make_wiki(tmp_path)))


def test_lk01_broken_link(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", page("Alpha", "sources", "See [[missing-slug]]."))
    assert "LK01" in codes(lint(wiki))


def test_lk01_negative_resolved_link(tmp_path: Path) -> None:
    assert "LK01" not in codes(lint(make_wiki(tmp_path)))


def test_or01_orphan_page(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "entities/beta.md", page("Beta", "entities"))
    issues = lint(wiki)
    assert codes(issues) == ["OR01"]
    assert issues[0].severity == "WARN"


def test_or01_negative_linked_page(tmp_path: Path) -> None:
    assert "OR01" not in codes(lint(make_wiki(tmp_path)))


def test_or01_index_links_do_not_count(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "entities/beta.md", page("Beta", "entities"))
    issues = lint(wiki)
    assert codes(issues) == ["OR01"]
    assert issues[0].path.endswith("alpha.md")


def test_finding_f7_docs_do_not_claim_lint_enforces_citations() -> None:
    agents_md = (Path(__file__).resolve().parent.parent / "AGENTS.md").read_text(encoding="utf-8")
    assert "Every factual claim in a wiki page must include at least one citation" not in agents_md
    assert "citation coverage is a review responsibility" in agents_md


def test_finding_f7_docs_do_not_claim_lint_enforces_citations_negative() -> None:
    agents_md = (Path(__file__).resolve().parent.parent / "AGENTS.md").read_text(encoding="utf-8")
    assert "Run `python -m brainstew lint`" in agents_md


def test_ix01_page_missing_from_index(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "concepts/gamma.md", page("Gamma", "concepts", "See [[alpha]]."))
    issues = lint(wiki)
    assert "IX01" in codes(issues)
    ix01 = next(i for i in issues if i.code == "IX01")
    assert ix01.path == "wiki/concepts/gamma.md"


def test_ix01_negative_listed_in_index(tmp_path: Path) -> None:
    assert "IX01" not in codes(lint(make_wiki(tmp_path)))


def test_ix02_index_references_unknown_slug(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "index.md", INDEX.replace("## Concepts\n", "## Concepts\n- [[ghost]] - ghost summary\n"))
    issues = lint(wiki)
    assert "IX02" in codes(issues)
    assert any(i.path == "wiki/index.md" for i in issues if i.code == "IX02")


def test_ix02_negative(tmp_path: Path) -> None:
    assert "IX02" not in codes(lint(make_wiki(tmp_path)))


def test_ix03_missing_index(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    (wiki / "index.md").unlink()
    issues = lint(wiki)
    assert "IX03" in codes(issues)
    assert any(i.path == "wiki/index.md" for i in issues if i.code == "IX03")


def test_ix03_negative(tmp_path: Path) -> None:
    assert "IX03" not in codes(lint(make_wiki(tmp_path)))


def test_lg01_bad_heading_format(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "log.md", "# Wiki Log\n\n## 2026-01-20 ingest First\n- did a thing\n")
    issues = lint(wiki)
    assert "LG01" in codes(issues)
    assert any(i.path == "wiki/log.md" for i in issues if i.code == "LG01")


def test_lg01_negative_valid_headings(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(
        wiki,
        "log.md",
        "# Wiki Log\n\n## [2026-01-20] ingest | First\n- a\n\n## [2026-01-21] query | Look\n- b\n",
    )
    assert "LG01" not in codes(lint(wiki))


def test_lg02_missing_log(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    (wiki / "log.md").unlink()
    issues = lint(wiki)
    assert "LG02" in codes(issues)
    assert any(i.path == "wiki/log.md" for i in issues if i.code == "LG02")


def test_lg02_negative(tmp_path: Path) -> None:
    assert "LG02" not in codes(lint(make_wiki(tmp_path)))


def test_du01_duplicate_slug(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "entities/alpha.md", page("Alpha Two", "entities", "See [[alpha]]."))
    issues = lint(wiki)
    assert "DU01" in codes(issues)
    assert all(i.path.endswith("alpha.md") for i in issues if i.code == "DU01")


def test_finding_f11_case_variant_slug_collision_detected(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "entities/Alpha.md", page("Alpha Two", "entities", "See [[alpha]]."))
    issues = lint(wiki)
    du01 = [i for i in issues if i.code == "DU01"]
    assert du01, "case-variant slug 'Alpha' must collide with existing slug 'alpha'"
    assert {i.path for i in du01} == {"wiki/sources/alpha.md", "wiki/entities/Alpha.md"}
    # negative: slugs that differ in more than case are still distinct
    assert "DU01" not in codes(lint(make_wiki(tmp_path / "negative")))


def test_du01_negative_unique_slugs(tmp_path: Path) -> None:
    assert "DU01" not in codes(lint(make_wiki(tmp_path)))


def test_issues_sorted_by_path_then_code(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "concepts/zulu.md", page("Zulu", "concepts", "See [[alpha]]."))
    issues = lint(wiki)
    keys = [(i.path, i.code) for i in issues]
    assert keys == sorted(keys)


def test_run_missing_wiki_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from brainstew.cli import main

    rc = main(["--root", str(tmp_path), "lint"])
    out, err = capsys.readouterr()
    assert rc == 2
    assert err


def test_cli_clean_exit_zero(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "brainstew", "--root", str(make_wiki(tmp_path).parent), "lint"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout == "lint: 0 errors, 0 warnings\n"
    assert proc.stderr == ""


def test_cli_output_line_format(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "entities/beta.md", page("Beta", "entities"))
    proc = subprocess.run(
        [sys.executable, "-m", "brainstew", "--root", str(wiki.parent), "lint"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    lines = proc.stdout.strip().splitlines()
    assert re.fullmatch(r"WARN OR01 \S*wiki/sources/alpha\.md: orphan page", lines[0])
    assert lines[-1] == "lint: 0 errors, 1 warnings"
    assert proc.stderr == ""


def test_cli_strict_promotes_warning_to_error(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "entities/beta.md", page("Beta", "entities"))
    proc = subprocess.run(
        [sys.executable, "-m", "brainstew", "--root", str(wiki.parent), "lint", "--strict"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert proc.stdout.splitlines()[0].startswith("ERROR OR01 ")
    assert proc.stdout.splitlines()[-1] == "lint: 1 errors, 0 warnings"


def test_cli_missing_wiki_dir_exit_two(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "brainstew", "--root", str(tmp_path), "lint"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert proc.stderr


def test_cli_root_after_subcommand(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "brainstew", "lint", "--root", str(make_wiki(tmp_path).parent)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout == "lint: 0 errors, 0 warnings\n"


def test_finding_f3_symlinked_root_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from brainstew.cli import main

    real_root = tmp_path / "real"
    real_root.mkdir()
    make_wiki(real_root)
    link = tmp_path / "link"
    link.symlink_to(real_root)
    rc = main(["--root", str(link), "lint"])
    out, err = capsys.readouterr()
    assert rc == 2
    assert err


def test_cli_prog_and_description_match_spec() -> None:
    import brainstew.cli as cli

    assert cli.build_parser().prog == "brainstew"
    assert cli.build_parser().description == (
        "brainstew: tools for an LLM-maintained markdown wiki (search, lint, log)."
    )
    assert not hasattr(cli, "USAGE")


def test_fm02_reported_path_is_wiki_relative(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", "---\ntitle: Alpha\n")
    issues = lint(wiki)
    fm02 = next(i for i in issues if i.code == "FM02")
    assert fm02.path == "wiki/sources/alpha.md"


def test_lg01_reports_all_bad_headings(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "log.md", "# Wiki Log\n\n## 2026-01-20 ingest First\n- a\n\n## 2026-01-21 query Second\n- b\n")
    issues = lint(wiki)
    lg01 = [i for i in issues if i.code == "LG01"]
    assert len(lg01) == 2


# --- FM02 field-type/value validation ---


def test_fm02_bogus_type_list_rejected(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", page("Alpha", "sources").replace("type: source", "type: [bogus]"))
    issues = lint(wiki)
    assert "TY01" not in codes(issues)
    fm02 = [i for i in issues if i.code == "FM02" and i.path == "wiki/sources/alpha.md"]
    assert any("type" in i.message for i in fm02)


def test_fm02_scalar_sources_rejected(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", page("Alpha", "sources").replace("sources: [raw/a.txt]", "sources: raw/a.txt"))
    issues = lint(wiki)
    fm02 = [i for i in issues if i.code == "FM02" and i.path == "wiki/sources/alpha.md"]
    assert any("sources" in i.message for i in fm02)


def test_fm02_empty_sources_list_rejected(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", page("Alpha", "sources").replace("sources: [raw/a.txt]", "sources: []"))
    issues = lint(wiki)
    fm02 = [i for i in issues if i.code == "FM02" and i.path == "wiki/sources/alpha.md"]
    assert any("sources" in i.message for i in fm02)


def test_fm02_sources_entry_must_be_raw_path_or_source_slug(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", page("Alpha", "sources").replace("sources: [raw/a.txt]", "sources: [beta]"))
    issues = lint(wiki)
    fm02 = [i for i in issues if i.code == "FM02" and i.path == "wiki/sources/alpha.md"]
    assert any("sources entry" in i.message for i in fm02)


def test_fm02_sources_source_slug_accepted(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", page("Alpha", "sources"))
    write(wiki, "entities/beta.md", page("Beta", "entities").replace("sources: [raw/a.txt]", "sources: [alpha]"))
    assert "FM02" not in codes(lint(wiki))


def test_fm02_empty_title_rejected(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", page("Alpha", "sources").replace("title: Alpha", "title:   "))
    issues = lint(wiki)
    assert any(i.code == "FM02" and "title" in i.message for i in issues)


def test_fm02_empty_summary_rejected(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", page("Alpha", "sources").replace("summary: Alpha summary", "summary:   "))
    issues = lint(wiki)
    assert any(i.code == "FM02" and "summary" in i.message for i in issues)


def test_fm02_updated_non_date_shape_rejected(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", page("Alpha", "sources", updated="20260120"))
    issues = lint(wiki)
    assert any(i.code == "FM02" and i.path == "wiki/sources/alpha.md" for i in issues)


def test_fm02_field_validation_negative(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    text = page("Alpha", "sources").replace("---\n\nBody.", "---\ntags: [a, b]\n---\n\nBody.")
    write(wiki, "sources/alpha.md", text)
    assert "FM02" not in codes(lint(wiki))


def test_fm02_sources_raw_path_escape_rejected(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    text = page("Alpha", "sources").replace("sources: [raw/a.txt]", "sources: [raw/../../outside.txt]")
    write(wiki, "sources/alpha.md", text)
    issues = lint(wiki)
    fm02 = [i for i in issues if i.code == "FM02" and i.path == "wiki/sources/alpha.md"]
    assert any("sources entry" in i.message for i in fm02)


def test_fm02_sources_raw_path_dotdot_inside_raw_accepted(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    text = page("Alpha", "sources").replace("sources: [raw/a.txt]", "sources: [raw/../raw/a.txt]")
    write(wiki, "sources/alpha.md", text)
    issues = lint(wiki)
    assert "FM02" not in codes(issues)


def test_fm02_sources_raw_path_negative(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    text = page("Alpha", "sources").replace("sources: [raw/a.txt]", "sources: [raw/foo.txt, raw/sub/b.txt]")
    write(wiki, "sources/alpha.md", text)
    issues = lint(wiki)
    assert "FM02" not in codes(issues)


def test_fm02_sources_raw_path_check_is_platform_independent(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "sources/alpha.md", page("Alpha", "sources", "See [[beta]]."))
    write(wiki, "entities/beta.md", page("Beta", "entities"))
    assert "FM02" not in codes(lint(wiki))
    # The check must behave like posixpath even when the platform would use
    # ntpath (on Windows os.path.normpath("raw/a.txt") gives "raw\a.txt").
    import posixpath

    from brainstew.lint import _norm_posix

    assert _norm_posix("raw/a.txt") == posixpath.normpath("raw/a.txt")
    assert _norm_posix("raw/a.txt").startswith("raw/")
    assert _norm_posix("raw/../raw/a.txt") == posixpath.normpath("raw/../raw/a.txt")
    assert _norm_posix("raw/../raw/a.txt").startswith("raw/")
    assert _norm_posix("raw/../../outside.txt") == posixpath.normpath("raw/../../outside.txt")
    assert not _norm_posix("raw/../../outside.txt").startswith("raw/")

    # ntpath would produce a backslash separator, so the POSIX raw/ prefix
    # check would fail under ntpath-style behaviour; the check uses posixpath.
    import ntpath

    assert posixpath.normpath("raw/a.txt") != ntpath.normpath("raw/a.txt")
    assert ntpath.normpath("raw/a.txt").startswith("raw") and not ntpath.normpath("raw/a.txt").startswith("raw/")
    assert _norm_posix("raw/a.txt").startswith("raw/")

    # PurePosixPath inputs must normalize under POSIX rules too.
    from pathlib import PurePosixPath

    assert _norm_posix(str(PurePosixPath("raw/../raw/a.txt"))) == "raw/a.txt"


def test_finding_f10_sources_raw_path_with_backslashes_rejected(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    text = page("Alpha", "sources").replace(
        "sources: [raw/a.txt]", "sources: [raw/foo\\..\\..\\..\\outside.txt]"
    )
    write(wiki, "sources/alpha.md", text)
    issues = lint(wiki)
    fm02 = [i for i in issues if i.code == "FM02" and i.path == "wiki/sources/alpha.md"]
    assert any("sources entry" in i.message for i in fm02)


# --- index.md structure ---


def test_finding_f2_all_links_on_index_bullet_checked(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "index.md", INDEX.replace(
        "- [[alpha]] - Alpha summary",
        "- [[alpha]] - Alpha summary, see also [[ghost]]",
    ))
    issues = lint(wiki)
    assert any("unknown slug: [[ghost]]" in i.message and i.path == "wiki/index.md" for i in issues)


def test_ix02_index_heading_wrong_order(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    text = INDEX.replace("## Synthesis\n", "## Entities\n\n## Synthesis\n")
    write(wiki, "index.md", text)
    issues = lint(wiki)
    ix = [i for i in issues if i.code == "IX02" and i.path == "wiki/index.md"]
    assert any("order" in i.message for i in ix)


def test_ix02_index_missing_heading(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "index.md", INDEX.replace("## Concepts\n\n", ""))
    issues = lint(wiki)
    ix = [i for i in issues if i.code == "IX02" and i.path == "wiki/index.md"]
    assert any("order" in i.message for i in ix)


def test_ix02_duplicate_entry_in_index(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    text = INDEX.replace("- [[alpha]] - Alpha summary\n", "- [[alpha]] - Alpha summary\n- [[alpha]] - Alpha again\n")
    write(wiki, "index.md", text)
    issues = lint(wiki)
    ix = [i for i in issues if i.code == "IX02" and i.path == "wiki/index.md"]
    assert any("2 times" in i.message for i in ix)


def test_ix02_index_structure_negative(tmp_path: Path) -> None:
    assert "IX02" not in codes(lint(make_wiki(tmp_path)))


def test_ix02_slug_in_wrong_section(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    text = INDEX.replace("- [[beta]] - Beta summary\n", "- [[beta]] - Beta summary\n- [[alpha]] - Alpha summary\n")
    write(wiki, "index.md", text)
    issues = lint(wiki)
    ix02 = [i for i in issues if i.code == "IX02" and i.path == "wiki/index.md"]
    assert any("belongs in Sources" in i.message for i in ix02)


def test_ix02_slug_in_wrong_section_each_folder(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "concepts/gamma.md", page("Gamma", "concepts", "See [[alpha]]."))
    write(wiki, "synthesis/delta.md", page("Delta", "synthesis", "See [[alpha]]."))
    text = INDEX.replace(
        "## Concepts\n",
        "## Concepts\n- [[gamma]] - Gamma summary\n- [[delta]] - Delta summary\n",
    )
    write(wiki, "index.md", text)
    issues = lint(wiki)
    ix02 = [i for i in issues if i.code == "IX02" and i.path == "wiki/index.md"]
    assert any("belongs in Synthesis" in i.message for i in ix02)


def test_ix02_slug_in_correct_section_negative(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "concepts/gamma.md", page("Gamma", "concepts", "See [[alpha]]."))
    text = INDEX.replace("## Concepts\n", "## Concepts\n- [[gamma]] - Gamma summary\n")
    write(wiki, "index.md", text)
    issues = lint(wiki)
    assert "IX02" not in codes(issues)
    assert "IX01" not in codes(issues)


def test_finding_f22_link_in_index_prose_rejected(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "index.md", INDEX.replace(
        "## Concepts\n",
        "## Concepts\nRelevant background: [[ghost]] and [[alpha]].\n",
    ))
    issues = lint(wiki)
    ix02 = [i for i in issues if i.code == "IX02" and i.path == "wiki/index.md"]
    assert ix02, "non-bullet index lines containing links must be rejected"


def test_finding_f22_link_before_any_heading_rejected(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "index.md", INDEX.replace(
        "# Wiki Index\n",
        "# Wiki Index\n\nSee [[alpha]] first.\n",
    ))
    issues = lint(wiki)
    ix02 = [i for i in issues if i.code == "IX02" and i.path == "wiki/index.md"]
    assert ix02, "links on non-bullet lines before any heading must be rejected"


def test_finding_f22_prose_without_links_accepted(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "index.md", INDEX.replace(
        "## Concepts\n",
        "## Concepts\nPlain prose without any links.\n",
    ))
    assert "IX02" not in codes(lint(wiki))


# --- log.md heading dates ---


def test_lg01_impossible_heading_date(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "log.md", "# Wiki Log\n\n## [2026-99-99] ingest | First\n- did a thing\n")
    issues = lint(wiki)
    assert "LG01" in codes(issues)
    assert any("impossible" in i.message for i in issues if i.code == "LG01")


def test_lg01_impossible_heading_date_negative(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "log.md", "# Wiki Log\n\n## [2026-02-28] ingest | First\n- did a thing\n")
    assert "LG01" not in codes(lint(wiki))


# --- invalid UTF-8 handling ---


def test_invalid_utf8_in_page_reported(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    (wiki / "sources" / "alpha.md").write_bytes(b"---\ntitle: broken \xff\n---\n\nbody\n")
    issues = lint(wiki)
    utf8 = [i for i in issues if "invalid UTF-8" in i.message]
    assert len(utf8) == 1
    assert utf8[0].path == "wiki/sources/alpha.md"
    assert utf8[0].severity == "ERROR"


def test_invalid_utf8_in_index_reported(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    (wiki / "index.md").write_bytes(b"# Wiki Index\n\xff\xfe\n")
    issues = lint(wiki)
    assert any("invalid UTF-8" in i.message and i.path == "wiki/index.md" for i in issues)


def test_invalid_utf8_in_log_reported(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    (wiki / "log.md").write_bytes(b"# Wiki Log\n\xff\xfe\n")
    issues = lint(wiki)
    assert any("invalid UTF-8" in i.message and i.path == "wiki/log.md" for i in issues)


def test_invalid_utf8_never_raises(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    (wiki / "sources" / "alpha.md").write_bytes(b"\xff\xfe\x00")
    (wiki / "index.md").write_bytes(b"\xff\xfe\x00")
    (wiki / "log.md").write_bytes(b"\xff\xfe\x00")
    issues = lint(wiki)  # must not raise
    assert issues


def test_unreadable_page_reported(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    page = wiki / "sources" / "alpha.md"
    page.write_text("x", encoding="utf-8")
    if os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    os.chmod(page, 0)
    try:
        issues = lint(wiki)  # must not raise
    finally:
        os.chmod(page, 0o644)
    fm02 = [i for i in issues if i.code == "FM02" and i.path == "wiki/sources/alpha.md"]
    assert len(fm02) == 1
    assert fm02[0].severity == "ERROR"
    assert fm02[0].message
    assert "Traceback" not in fm02[0].message
    assert all(i.path != "wiki/entities/beta.md" or i.code != "FM02" for i in issues)


def test_unreadable_page_does_not_stop_other_checks(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    page = wiki / "entities" / "beta.md"
    page.write_text("x", encoding="utf-8")
    if os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    os.chmod(page, 0)
    try:
        issues = lint(wiki)  # must not raise
    finally:
        os.chmod(page, 0o644)
    assert any(i.code == "FM02" and i.path == "wiki/entities/beta.md" for i in issues)
    paths = [i.path for i in issues]
    assert "wiki/sources/alpha.md" in paths
    assert "wiki/index.md" in paths
    codes_list = [i.code for i in issues if i.path == "wiki/entities/beta.md"]
    assert codes_list == sorted(codes_list)
    assert [(i.path, i.code) for i in issues] == sorted((i.path, i.code) for i in issues)


def test_unreadable_index_reported(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    index = wiki / "index.md"
    index.write_text("x", encoding="utf-8")
    if os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    os.chmod(index, 0)
    try:
        issues = lint(wiki)  # must not raise
    finally:
        os.chmod(index, 0o644)
    assert any(i.code == "FM02" and i.path == "wiki/index.md" and "unreadable" in i.message
               for i in issues)


def test_unreadable_log_reported(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    log = wiki / "log.md"
    log.write_text("x", encoding="utf-8")
    if os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    os.chmod(log, 0)
    try:
        issues = lint(wiki)  # must not raise
    finally:
        os.chmod(log, 0o644)
    assert any(i.code == "LG02" and i.path == "wiki/log.md" and "unreadable" in i.message
               for i in issues)


def test_finding_f15_unreadable_category_dir_reported_at_category_path(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    d = wiki / "concepts"
    d.mkdir()
    if os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    os.chmod(d, 0)
    try:
        issues = lint(wiki)  # must not raise
    finally:
        os.chmod(d, 0o755)
    hits = [i for i in issues if i.code == "FM02" and "unreadable directory" in i.message]
    assert len(hits) == 1
    assert hits[0].path == "wiki/concepts"
    assert hits[0].severity == "ERROR"
    assert hits[0].message
    assert "Traceback" not in hits[0].message
