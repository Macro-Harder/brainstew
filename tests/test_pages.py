"""Tests for page discovery and link extraction."""

from pathlib import Path

from brainstew.pages import discover_pages

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


def test_load_page_returns_none_for_invalid_frontmatter(tmp_path: Path) -> None:
    from brainstew.pages import load_page

    wiki = tmp_path / "wiki"
    write_page(wiki, "sources", "badfm.md", "no fence here\n")
    path = wiki / "sources" / "badfm.md"
    result = load_page(path)
    assert result == (path, None)


def test_unparseable_page_reports_path_with_none(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    write_page(wiki, "sources", "broken.md", "no fence here\n")
    (wiki / "sources" / "good.md").write_text(make_page("Good", "sources"), encoding="utf-8")
    pages = discover_pages(wiki)
    broken = dict(pages)
    assert broken[wiki / "sources" / "broken.md"] is None
    assert broken[wiki / "sources" / "good.md"] is not None


def test_symlinked_page_outside_wiki_is_not_discovered(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    write_page(wiki, "sources", "real.md", make_page("Real", "sources"))
    (wiki / "sources" / "good.md").write_text(make_page("Good", "sources"), encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text(make_page("Outside", "sources"), encoding="utf-8")
    (wiki / "sources" / "escape.md").symlink_to(outside)
    pages = discover_pages(wiki)
    paths = [p for p, _ in pages]
    assert wiki / "sources" / "escape.md" not in paths
    assert wiki / "sources" / "real.md" in paths
    assert wiki / "sources" / "good.md" in paths


def test_symlinked_page_is_not_linted_even_when_it_points_to_another_page(tmp_path: Path) -> None:
    from brainstew.lint import lint

    wiki = tmp_path / "wiki"
    write_page(wiki, "sources", "real.md", make_page("Real", "sources"))
    (wiki / "sources" / "escape.md").symlink_to(wiki / "sources" / "real.md")
    (wiki / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    (wiki / "log.md").write_text("# Wiki Log\n", encoding="utf-8")
    issues = lint(wiki)
    paths = [i.path for i in issues]
    assert all("escape.md" not in p for p in paths)


def test_symlinked_subdirectory_not_discovered(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    write_page(wiki, "sources", "real.md", make_page("Real", "sources"))
    (wiki / "sources" / "good.md").write_text(make_page("Good", "sources"), encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leaked.md").write_text(make_page("Leaked", "sources"), encoding="utf-8")
    (wiki / "sources" / "sub").symlink_to(outside)
    pages = discover_pages(wiki)
    paths = [p for p, _ in pages]
    assert wiki / "sources" / "real.md" in paths
    assert wiki / "sources" / "good.md" in paths
    assert all(p.name != "leaked.md" for p in paths)
    assert len(paths) == 2


def test_symlinked_page_folder_not_discovered(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leaked.md").write_text(make_page("Leaked", "sources"), encoding="utf-8")
    (wiki / "sources").symlink_to(outside)
    pages = discover_pages(wiki)
    paths = [p for p, _ in pages]
    assert all(p.name != "leaked.md" for p in paths)
    assert not any(p.parent.name == "sources" for p in paths)


def test_symlinked_subdirectory_not_read_by_search_or_lint(tmp_path: Path) -> None:
    from brainstew.lint import lint
    from brainstew.search import search

    wiki = tmp_path / "wiki"
    write_page(wiki, "sources", "real.md", make_page("Real", "sources"))
    (wiki / "sources" / "good.md").write_text(make_page("Good", "sources"), encoding="utf-8")
    (wiki / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    (wiki / "log.md").write_text("# Wiki Log\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leaked.md").write_text(make_page("Leaked", "sources"), encoding="utf-8")
    (wiki / "sources" / "sub").symlink_to(outside)
    assert search(wiki, "leaked") == []
    assert search(wiki, "real") != []
    issues = lint(wiki)
    paths = [i.path for i in issues]
    assert all("leaked.md" not in p for p in paths)


def test_symlinked_non_page_dir_still_lints_clean(tmp_path: Path) -> None:
    from brainstew.lint import lint

    wiki = tmp_path / "wiki"
    write_page(wiki, "sources", "real.md", make_page("Real", "source", "See [[good]]."))
    write_page(wiki, "sources", "good.md", make_page("Good", "source", "See [[thing]]."))
    write_page(wiki, "entities", "thing.md", make_page("Thing", "entity", "See [[notion]]."))
    write_page(wiki, "concepts", "notion.md", make_page("Notion", "concept", "See [[wrap]]."))
    write_page(wiki, "synthesis", "wrap.md", make_page("Wrap", "synthesis", "See [[real]] and [[good]]."))
    (wiki / "index.md").write_text(
        "# Wiki Index\n\n"
        "## Sources\n"
        "- [[real]] - Real summary\n"
        "- [[good]] - Good summary\n\n"
        "## Entities\n"
        "- [[thing]] - Thing summary\n\n"
        "## Concepts\n"
        "- [[notion]] - Notion summary\n\n"
        "## Synthesis\n"
        "- [[wrap]] - Wrap summary\n",
        encoding="utf-8",
    )
    (wiki / "log.md").write_text("# Wiki Log\n", encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "pic.png").write_text("", encoding="utf-8")
    (wiki / "sources" / "assets").symlink_to(assets)
    assert lint(wiki) == []


def test_finding_f6_symlinked_category_dir_reported(tmp_path: Path) -> None:
    from brainstew.lint import lint

    wiki = tmp_path / "wiki"
    write_page(wiki, "sources", "real.md", make_page("Real", "sources"))
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leaked.md").write_text(make_page("Leaked", "concepts"), encoding="utf-8")
    (wiki / "concepts").symlink_to(outside)
    (wiki / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    (wiki / "log.md").write_text("# Wiki Log\n", encoding="utf-8")
    pages = discover_pages(wiki)
    paths = [p for p, _ in pages]
    assert wiki / "concepts" in paths
    assert all(p.name != "leaked.md" for p in paths)
    issues = lint(wiki)
    assert any("concepts" in i.message for i in issues)


def test_unreadable_page_reports_path_with_none(tmp_path: Path, monkeypatch) -> None:
    from pathlib import Path as _P

    wiki = tmp_path / "wiki"
    write_page(wiki, "sources", "bad.md", make_page("Bad", "sources"))
    (wiki / "sources" / "good.md").write_text(make_page("Good", "sources"), encoding="utf-8")

    def boom(self, *args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(_P, "read_text", boom)
    pages = discover_pages(wiki)
    result = dict(pages)
    assert result[wiki / "sources" / "bad.md"] is None
    assert result[wiki / "sources" / "good.md"] is None


def test_readable_page_loads_normally(tmp_path) -> None:
    wiki = tmp_path / "wiki"
    write_page(wiki, "sources", "fine.md", make_page("Fine", "sources"))
    pages = discover_pages(wiki)
    assert len(pages) == 1
    path, page = pages[0]
    assert page is not None
    assert path == wiki / "sources" / "fine.md"
    assert page.slug == "fine"
