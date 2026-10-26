"""Tests for page discovery and link extraction."""

from pathlib import Path

from llmwiki.pages import discover_pages

FM = "---\ntitle: {title}\ntype: {type}\nsummary: {summary}\nsources: [raw/a.txt]\nupdated: 2026-01-20\n---\n\n{body}\n"


def write_page(wiki: Path, folder: str, name: str, text: str) -> None:
    d = wiki / folder
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(text, encoding="utf-8")


def make_page(title: str, folder: str, body: str = "Body.") -> str:
    return FM.format(title=title, type=folder, summary=f"{title} summary", body=body)


def build_wiki(tmp_path: Path) -> Path:
    wiki = tmp_path / "wiki"
    write_page(wiki, "sources", "fresnel-lens.md", make_page("Fresnel Lens", "sources", "See [[lighthouse]]."))
    write_page(wiki, "entities", "lighthouse.md", make_page("Lighthouse", "entities"))
    write_page(wiki, "concepts", "optics.md", make_page("Optics", "concepts"))
    write_page(wiki, "synthesis", "summary.md", make_page("Summary", "synthesis"))
    (wiki / "sources" / "sub").mkdir()
    write_page(wiki, "sources", "sub/deep.md", make_page("Deep", "sources"))
    (wiki / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    (wiki / "log.md").write_text("# Wiki Log\n", encoding="utf-8")
    (wiki / "notes.md").write_text("# Not a page\n", encoding="utf-8")
    (wiki / "synthesis" / ".gitkeep").write_text("", encoding="utf-8")
    return wiki


def test_discovers_all_four_folders(tmp_path: Path) -> None:
    pages = discover_pages(build_wiki(tmp_path))
    slugs = [p.slug for _, p in pages]
    assert slugs == ["fresnel-lens", "lighthouse", "optics", "summary"]


def test_ignores_root_files_and_nested_dirs(tmp_path: Path) -> None:
    pages = discover_pages(build_wiki(tmp_path))
    paths = [p for p, _ in pages]
    assert all(p.parent.name in ("sources", "entities", "concepts", "synthesis") for p in paths)
    assert not any(p.name in ("index.md", "log.md", "notes.md") for p in paths)
    assert not any(p.parent.name == "sub" for p in paths)


def test_page_fields(tmp_path: Path) -> None:
    page = discover_pages(build_wiki(tmp_path))[0][1]
    assert page.slug == "fresnel-lens"
    assert page.folder == "sources"
    assert page.meta["title"] == "Fresnel Lens"
    assert page.meta["sources"] == ["raw/a.txt"]
    assert page.body.startswith("See [[lighthouse]].")


def test_link_extraction(tmp_path: Path) -> None:
    page = next(p for _, p in discover_pages(build_wiki(tmp_path)) if p.slug == "fresnel-lens")
    assert page.links == ["lighthouse"]


def test_multiple_links_in_order(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    write_page(
        wiki,
        "concepts",
        "multi.md",
        make_page("Multi", "concepts", "A [[b]] and [[c]] and back to [[b]]."),
    )
    page = discover_pages(wiki)[0][1]
    assert page.links == ["b", "c", "b"]


def test_unparseable_page_reports_path_with_none(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    write_page(wiki, "sources", "broken.md", "no fence here\n")
    (wiki / "sources" / "good.md").write_text(make_page("Good", "sources"), encoding="utf-8")
    pages = discover_pages(wiki)
    broken = dict(pages)
    assert broken[wiki / "sources" / "broken.md"] is None
    assert broken[wiki / "sources" / "good.md"] is not None
