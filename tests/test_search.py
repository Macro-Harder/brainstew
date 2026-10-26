"""Tests for the search command."""

import subprocess
import sys
from pathlib import Path

from brainstew.cli import main
from brainstew.search import search

FM = (
    "---\n"
    "title: {title}\n"
    "type: {type}\n"
    "summary: {summary}\n"
    "sources: [raw/a.txt]\n"
    "updated: 2026-01-20\n"
    "---\n"
    "\n"
    "{body}\n"
)


def write(wiki: Path, rel: str, text: str) -> None:
    p = wiki / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


TYPE_OF = {"sources": "source", "entities": "entity", "concepts": "concept", "synthesis": "synthesis"}


def make_page(title: str, folder: str, summary: str, body: str) -> str:
    return FM.format(title=title, type=TYPE_OF[folder], summary=summary, body=body)


def build_wiki(tmp_path: Path) -> Path:
    wiki = tmp_path / "wiki"
    write(wiki, "sources/lens.md", make_page("Fresnel Lens", "sources", "A lens summary.", "Body mentions nothing useful."))
    write(wiki, "entities/light.md", make_page("Light", "entities", "Brightness summary.", "The lens idea appears here."))
    write(wiki, "concepts/optics.md", make_page("Optics", "concepts", "Optics of lenses.", "Deep lens physics everywhere."))
    return wiki


def slugs(wiki: Path, query: str) -> list[str]:
    return [p.slug for p, _ in search(wiki, query)]


def test_body_match_beats_nothing_but_counts_once(tmp_path: Path) -> None:
    wiki = build_wiki(tmp_path)
    hits = slugs(wiki, "nothing")
    assert hits == ["lens"]


def test_title_beats_summary_beats_body(tmp_path: Path) -> None:
    wiki = build_wiki(tmp_path)
    assert slugs(wiki, "lens") == ["lens", "optics", "light"]


def test_per_term_scoring_sums(tmp_path: Path) -> None:
    wiki = build_wiki(tmp_path)
    hits = search(wiki, "optics lens")
    by_slug = {p.slug: s for p, s in hits}
    assert by_slug["optics"] > by_slug["lens"]
    assert set(by_slug) == {"lens", "light", "optics"}


def test_any_term_matches(tmp_path: Path) -> None:
    wiki = build_wiki(tmp_path)
    hits = slugs(wiki, "zzzquit")
    assert hits == []
    hits = slugs(wiki, "zzzquit optics")
    assert hits == ["optics"]


def test_terms_are_lowercased(tmp_path: Path) -> None:
    wiki = build_wiki(tmp_path)
    assert slugs(wiki, "LENS") == ["lens", "optics", "light"]


def test_sort_tie_break_by_title(tmp_path: Path) -> None:
    wiki = build_wiki(tmp_path)
    write(wiki, "synthesis/zzz.md", make_page("Zebra Lens", "synthesis", "No lens here.", "Nope."))
    write(wiki, "synthesis/aaa.md", make_page("Alpha Lens", "synthesis", "No lens here.", "Nope."))
    assert slugs(wiki, "nope") == ["aaa", "zzz"]


def test_zero_hits_empty(tmp_path: Path) -> None:
    wiki = build_wiki(tmp_path)
    assert search(wiki, "qqqq") == []


def test_cli_hit_exit_zero(tmp_path: Path, capsys) -> None:
    build_wiki(tmp_path)
    rc = main(["--root", str(tmp_path), "search", "lens"])
    out, err = capsys.readouterr()
    assert rc == 0
    lines = out.strip().splitlines()
    assert lines[0] == "lens\tsource\tA lens summary."
    assert len(lines) == 3


def test_cli_zero_hits_exit_one(tmp_path: Path, capsys) -> None:
    build_wiki(tmp_path)
    rc = main(["--root", str(tmp_path), "search", "qqqq"])
    out, err = capsys.readouterr()
    assert rc == 1
    assert out == ""
    assert err == ""


def test_cli_limit(tmp_path: Path, capsys) -> None:
    build_wiki(tmp_path)
    rc = main(["--root", str(tmp_path), "search", "lens", "--limit", "2"])
    out, _ = capsys.readouterr()
    assert rc == 0
    assert len(out.strip().splitlines()) == 2


def test_cli_limit_default_ten(tmp_path: Path, capsys) -> None:
    wiki = build_wiki(tmp_path)
    for i in range(12):
        write(wiki, f"synthesis/p{i:02d}.md", make_page(f"P{i:02d}", "synthesis", f"lens page {i}.", "lens body."))
    rc = main(["--root", str(tmp_path), "search", "lens"])
    out, _ = capsys.readouterr()
    assert rc == 0
    assert len(out.strip().splitlines()) == 10


def test_cli_missing_wiki_dir(tmp_path: Path, capsys) -> None:
    rc = main(["--root", str(tmp_path), "search", "lens"])
    out, err = capsys.readouterr()
    assert rc == 2
    assert out == ""
    assert "no wiki dir" in err


def test_cli_subprocess_end_to_end(tmp_path: Path) -> None:
    build_wiki(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "brainstew", "--root", str(tmp_path), "search", "lens", "--limit", "1"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout.splitlines()[0].startswith("lens\tsource\t")
