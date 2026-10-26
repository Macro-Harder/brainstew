"""Tests for the log command."""

import subprocess
import sys
from pathlib import Path

from llmwiki.cli import main
from llmwiki.log import read_log, render, split_entries

LOG = (
    "# Wiki Log\n"
    "\n"
    "## [2026-01-18] ingest | First Page\n"
    "- read raw file\n"
    "- wrote summary\n"
    "\n"
    "## [2026-01-19] query | Lens Lookup\n"
    "- searched for lens\n"
    "\n"
    "## [2026-01-20] lint | Fixed Issues\n"
    "- fixed index\n"
    "\n"
    "## [2026-01-21] edit | Updated Page\n"
    "- revised text\n"
)


def make_wiki(tmp_path: Path, text: str = LOG) -> Path:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text(text, encoding="utf-8")
    return wiki


def test_split_entries(tmp_path: Path) -> None:
    entries = read_log(make_wiki(tmp_path))
    assert [h for h, _ in entries] == [
        "## [2026-01-18] ingest | First Page",
        "## [2026-01-19] query | Lens Lookup",
        "## [2026-01-20] lint | Fixed Issues",
        "## [2026-01-21] edit | Updated Page",
    ]
    assert entries[0][1] == ["- read raw file", "- wrote summary"]
    assert entries[1][1] == ["- searched for lens"]


def test_render_blank_line_separated(tmp_path: Path) -> None:
    entries = read_log(make_wiki(tmp_path))
    text = render(entries[-2:])
    assert text == (
        "## [2026-01-20] lint | Fixed Issues\n- fixed index\n\n"
        "## [2026-01-21] edit | Updated Page\n- revised text"
    )


def test_split_preserves_headings_without_bullets(tmp_path: Path) -> None:
    entries = split_entries("## [2026-01-20] edit | Empty\nBody line\n")
    assert entries == [("## [2026-01-20] edit | Empty", [])]


def test_cli_tail_default_ten(tmp_path: Path, capsys) -> None:
    make_wiki(tmp_path)
    rc = main(["--root", str(tmp_path), "log"])
    out, _ = capsys.readouterr()
    assert rc == 0
    assert out.count("## [") == 4
    assert out.startswith("## [2026-01-18] ingest | First Page\n- read raw file\n")


def test_cli_tail_n(tmp_path: Path, capsys) -> None:
    make_wiki(tmp_path)
    rc = main(["--root", str(tmp_path), "log", "-n", "2"])
    out, _ = capsys.readouterr()
    assert rc == 0
    assert out == (
        "## [2026-01-20] lint | Fixed Issues\n- fixed index\n\n"
        "## [2026-01-21] edit | Updated Page\n- revised text\n"
    )


def test_cli_op_filter(tmp_path: Path, capsys) -> None:
    make_wiki(tmp_path)
    rc = main(["--root", str(tmp_path), "log", "--op", "query"])
    out, _ = capsys.readouterr()
    assert rc == 0
    assert out == "## [2026-01-19] query | Lens Lookup\n- searched for lens\n"


def test_cli_n_applies_after_op_filter(tmp_path: Path, capsys) -> None:
    text = LOG + "\n".join(
        f"\n## [2026-02-0{i}] ingest | Ingest {i}\n- bullet {i}" for i in range(1, 4)
    )
    make_wiki(tmp_path, text)
    rc = main(["--root", str(tmp_path), "log", "--op", "ingest", "-n", "2"])
    out, _ = capsys.readouterr()
    assert rc == 0
    assert [line for line in out.splitlines() if line.startswith("## ")] == [
        "## [2026-02-02] ingest | Ingest 2",
        "## [2026-02-03] ingest | Ingest 3",
    ]


def test_cli_zero_entries_exit_zero(tmp_path: Path, capsys) -> None:
    make_wiki(tmp_path, "# Wiki Log\n")
    rc = main(["--root", str(tmp_path), "log"])
    out, err = capsys.readouterr()
    assert rc == 0
    assert out == ""
    assert err == ""


def test_cli_no_match_for_op_exit_zero(tmp_path: Path, capsys) -> None:
    make_wiki(tmp_path)
    rc = main(["--root", str(tmp_path), "log", "--op", "edit", "-n", "5"])
    out, _ = capsys.readouterr()
    assert rc == 0
    assert out == "## [2026-01-21] edit | Updated Page\n- revised text\n"


def test_cli_missing_log_exit_two(tmp_path: Path, capsys) -> None:
    rc = main(["--root", str(tmp_path), "log"])
    out, err = capsys.readouterr()
    assert rc == 2
    assert out == ""
    assert "no log.md" in err


def test_cli_subprocess_end_to_end(tmp_path: Path) -> None:
    make_wiki(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "llmwiki", "--root", str(tmp_path), "log", "-n", "1"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout == "## [2026-01-21] edit | Updated Page\n- revised text\n"
