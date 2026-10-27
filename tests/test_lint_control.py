"""Regression tests for finding F26: lint must escape control characters in diagnostics."""

from pathlib import Path

import pytest

from brainstew.cli import main

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


def make_wiki(root: Path) -> Path:
    wiki = root / "wiki"
    write(wiki, "sources/alpha.md", FM.format(title="Alpha", type="source", summary="Alpha summary", body="See [[beta]].", updated="2026-01-20"))
    write(wiki, "entities/beta.md", FM.format(title="Beta", type="entity", summary="Beta summary", body="See [[alpha]].", updated="2026-01-20"))
    write(wiki, "index.md", INDEX)
    write(wiki, "log.md", LOG)
    return wiki


def test_finding_f26_parse_error_control_chars_escaped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = make_wiki(tmp_path)
    bad = (
        "---\n"
        " \x1b[31mtitle: Alpha\n"
        "---\n"
        "body\n"
    )
    write(root, "wiki/sources/broken.md", bad)
    rc = main(["--root", str(root), "lint"])
    out, _ = capsys.readouterr()
    assert rc == 1
    assert "\x1b" not in out
    assert "\\x1b[31mtitle: Alpha" in out


def test_finding_f26_filename_control_chars_escaped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = make_wiki(tmp_path)
    write(root, "wiki/entities/beta\x1b[31m.md", FM.format(title="Beta Two", type="entity", summary="Beta summary", body="See [[alpha]].", updated="2026-01-20"))
    rc = main(["--root", str(root), "lint"])
    out, _ = capsys.readouterr()
    assert rc == 1
    assert "\x1b" not in out
    assert "wiki/entities/beta\\x1b[31m.md" in out


def test_finding_f26_root_path_control_chars_escaped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "ro\x1bot"
    root.mkdir()
    real = make_wiki(tmp_path / "real")
    (root / "wiki").symlink_to(real / "wiki")
    rc = main(["--root", str(root), "lint"])
    _, err = capsys.readouterr()
    assert rc == 2
    assert "\x1b" not in err
    assert "\\x1b" in err
