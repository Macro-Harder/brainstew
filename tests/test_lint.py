"""Tests for lint: one positive and one clean negative per code."""

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


def test_ix01_page_missing_from_index(tmp_path: Path) -> None:
    wiki = make_wiki(tmp_path)
    write(wiki, "concepts/gamma.md", page("Gamma", "concepts", "See [[alpha]]."))
    issues = lint(wiki)
    assert "IX01" in codes(issues)
    ix01 = next(i for i in issues if i.code == "IX01")
    assert "gamma" in ix01.path


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


def test_end_to_end_example_wiki(tmp_path: Path) -> None:
    root = tmp_path
    (root / "raw").mkdir()
    (root / "raw" / "fresnel-lens.txt").write_text(
        "The Fresnel Lens and Lighthouse Illumination\n", encoding="utf-8"
    )
    wiki = root / "wiki"
    for folder in ("sources", "entities", "concepts", "synthesis"):
        (wiki / folder).mkdir(parents=True)
    (wiki / "synthesis" / ".gitkeep").write_text("", encoding="utf-8")
    write(wiki, "sources/fresnel-lens.md", page(
        "Fresnel Lens", "sources",
        "The Fresnel lens, invented by [[augustin-fresnel]], replaced weak reflector systems. "
        "Its concentric rings focused light into a powerful beam. See also [[fresnel-lens-optics]] "
        "and [[lighthouse-illumination]].",
    ))
    write(wiki, "entities/augustin-fresnel.md", page(
        "Augustin Fresnel", "entities",
        "Augustin-Jean Fresnel developed the stepped-ring lens described in [[fresnel-lens]].",
    ))
    write(wiki, "entities/lighthouse.md", page(
        "Lighthouse", "entities",
        "The [[fresnel-lens]] greatly increased the effective range of [[lighthouse-illumination]].",
    ))
    write(wiki, "concepts/fresnel-lens-optics.md", page(
        "Fresnel Lens Optics", "concepts",
        "Concentric prismatic rings that focus light. Details appear in [[fresnel-lens]] "
        "and were developed by [[augustin-fresnel]].",
    ))
    write(wiki, "concepts/lighthouse-illumination.md", page(
        "Lighthouse Illumination", "concepts",
        "The [[fresnel-lens]] replaced fires and reflectors, improving safety for [[lighthouse]] structures.",
    ))
    write(wiki, "index.md", (
        "# Wiki Index\n"
        "\n"
        "## Sources\n"
        "- [[fresnel-lens]] - Fresnel Lens summary\n"
        "\n"
        "## Entities\n"
        "- [[augustin-fresnel]] - Augustin Fresnel summary\n"
        "- [[lighthouse]] - Lighthouse summary\n"
        "\n"
        "## Concepts\n"
        "- [[fresnel-lens-optics]] - Fresnel Lens Optics summary\n"
        "- [[lighthouse-illumination]] - Lighthouse Illumination summary\n"
        "\n"
        "## Synthesis\n"
    ))
    write(wiki, "log.md", (
        "# Wiki Log\n"
        "\n"
        "## [2026-01-20] ingest | Fresnel Lens\n"
        "- Read raw/fresnel-lens.txt\n"
        "- Created source, entity and concept pages\n"
        "- Updated index.md\n"
    ))
    proc = subprocess.run(
        [sys.executable, "-m", "brainstew", "--root", str(root), "lint"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout == "lint: 0 errors, 0 warnings\n"
