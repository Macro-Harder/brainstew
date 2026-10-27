"""Lint checks for the wiki."""

import argparse
import datetime
import posixpath
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from brainstew.frontmatter import FrontmatterError, parse_frontmatter
from brainstew.pages import LINK_RE, PAGE_DIRS, discover_pages

REQUIRED = ("title", "type", "summary", "sources", "updated")
FOLDER_OF = {"source": "sources", "entity": "entities", "concept": "concepts", "synthesis": "synthesis"}
INDEX_HEADINGS = ("Sources", "Entities", "Concepts", "Synthesis")
LOG_HEADING_RE = re.compile(r"## \[(\d{4}-\d{2}-\d{2})\] (ingest|query|lint|edit) \| \S")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass
class Issue:
    severity: str
    code: str
    path: str
    message: str


def _norm_posix(path: str) -> str:
    """Normalize a documented source path with POSIX rules, on any platform."""
    return posixpath.normpath(path)


def _valid_date(value: str) -> bool:
    if not DATE_RE.fullmatch(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _check_page(page, issues: list[Issue]) -> None:
    rel = f"wiki/{page.folder}/{page.slug}.md"
    missing = [f for f in REQUIRED if f not in page.meta]
    if missing:
        issues.append(Issue("ERROR", "FM01", rel, f"missing fields: {', '.join(missing)}"))
    title = page.meta.get("title")
    if "title" in page.meta and (not isinstance(title, str) or not title.strip()):
        issues.append(Issue("ERROR", "FM02", rel, "title must be a nonempty string"))
    summary = page.meta.get("summary")
    if "summary" in page.meta and (not isinstance(summary, str) or not summary.strip()):
        issues.append(Issue("ERROR", "FM02", rel, "summary must be a nonempty string"))
    page_type = page.meta.get("type")
    if page_type is not None and not isinstance(page_type, str):
        issues.append(Issue("ERROR", "FM02", rel, "type must be one of source|entity|concept|synthesis"))
    elif isinstance(page_type, str) and page_type not in FOLDER_OF:
        issues.append(Issue("ERROR", "FM02", rel, "type must be one of source|entity|concept|synthesis"))
    elif isinstance(page_type, str) and FOLDER_OF[page_type] != page.folder:
        issues.append(Issue("ERROR", "TY01", rel, f"type {page_type} in folder {page.folder}"))
    sources = page.meta.get("sources")
    if "sources" in page.meta and (not isinstance(sources, list) or not sources):
        issues.append(Issue("ERROR", "FM02", rel, "sources must be a nonempty list of raw/ paths or source-page slugs"))
    updated = page.meta.get("updated")
    if "updated" in page.meta and (not isinstance(updated, str) or not _valid_date(updated)):
        issues.append(Issue("ERROR", "FM02", rel, "updated must be a valid YYYY-MM-DD date"))
    tags = page.meta.get("tags")
    if "tags" in page.meta and (not isinstance(tags, list) or not all(isinstance(t, str) for t in tags)):
        issues.append(Issue("ERROR", "FM02", rel, "tags must be a list of strings"))


def _check_index(wiki: Path, pages, issues: list[Issue]) -> None:
    index = wiki / "index.md"
    if index.is_symlink():
        issues.append(Issue("ERROR", "IX03", "wiki/index.md", "symlinked index.md"))
        return
    if not index.is_file():
        issues.append(Issue("ERROR", "IX03", "wiki/index.md", "missing index.md"))
        return
    try:
        text = index.read_text(encoding="utf-8")
    except OSError as exc:
        issues.append(Issue("ERROR", "FM02", "wiki/index.md", f"unreadable: {exc.strerror or exc}"))
        return
    except UnicodeDecodeError:
        issues.append(Issue("ERROR", "FM02", "wiki/index.md", "invalid UTF-8"))
        return
    page_slugs = {p.slug for p in pages}
    order: list[str] = []
    bullets: dict[str, list[str]] = {}
    heading: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            order.append(heading)
            if heading not in bullets:
                bullets[heading] = []
        elif heading is not None and line.startswith("- "):
            bullets[heading].extend(m.group(1) for m in LINK_RE.finditer(line))
    if order != list(INDEX_HEADINGS):
        issues.append(Issue(
            "ERROR", "IX02", "wiki/index.md",
            f"headings must be exactly {', '.join(INDEX_HEADINGS)} in that order",
        ))
    page_by_slug = {p.slug: p for p in pages if p is not None}
    section_of = {p.slug: INDEX_HEADINGS[PAGE_DIRS.index(p.folder)] for p in pages if p is not None}
    listed: Counter[str] = Counter()
    for heading, slugs in bullets.items():
        for slug in slugs:
            listed[slug] += 1
            if slug in page_by_slug:
                page = page_by_slug[slug]
                rel = f"wiki/{page.folder}/{page.slug}.md"
                if heading != section_of[slug]:
                    issues.append(Issue(
                        "ERROR", "IX02", "wiki/index.md",
                        f"[[{slug}]] listed under {heading}, belongs in {section_of[slug]}",
                    ))
    for slug, count in listed.items():
        if slug not in page_slugs:
            issues.append(Issue("ERROR", "IX02", "wiki/index.md", f"unknown slug: [[{slug}]]"))
        elif count > 1:
            issues.append(Issue("ERROR", "IX02", "wiki/index.md", f"listed {count} times: [[{slug}]]"))
    for page in pages:
        if page.slug not in listed:
            issues.append(Issue("ERROR", "IX01", f"wiki/{page.folder}/{page.slug}.md", "not listed in index.md"))


def _check_log(wiki: Path, issues: list[Issue]) -> None:
    log = wiki / "log.md"
    if log.is_symlink():
        issues.append(Issue("ERROR", "LG02", "wiki/log.md", "symlinked log.md"))
        return
    if not log.is_file():
        issues.append(Issue("ERROR", "LG02", "wiki/log.md", "missing log.md"))
        return
    try:
        text = log.read_text(encoding="utf-8")
    except OSError as exc:
        issues.append(Issue("ERROR", "LG02", "wiki/log.md", f"unreadable: {exc.strerror or exc}"))
        return
    except UnicodeDecodeError:
        issues.append(Issue("ERROR", "FM02", "wiki/log.md", "invalid UTF-8"))
        return
    for line in text.splitlines():
        if not line.startswith("## "):
            continue
        m = LOG_HEADING_RE.match(line)
        if m is None:
            issues.append(Issue("ERROR", "LG01", "wiki/log.md", f"bad heading: {line}"))
        elif not _valid_date(m.group(1)):
            issues.append(Issue("ERROR", "LG01", "wiki/log.md", f"impossible date in heading: {line}"))


def lint(wiki: Path) -> list[Issue]:
    issues: list[Issue] = []
    pages = []
    for path, page in discover_pages(wiki):
        if page is None:
            if path.suffix == ".md" and path.parent.name in PAGE_DIRS:
                rel = f"wiki/{path.parent.name}/{path.name}"
            else:
                rel = f"wiki/{path.parent.name}"
            if path.suffix == ".md":
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError as exc:
                    issues.append(Issue("ERROR", "FM02", rel, f"unreadable: {exc.strerror or exc}"))
                    continue
                except UnicodeDecodeError:
                    issues.append(Issue("ERROR", "FM02", rel, "invalid UTF-8"))
                    continue
                try:
                    parse_frontmatter(text)
                    message = "invalid frontmatter"
                except FrontmatterError as exc:
                    message = str(exc)
                issues.append(Issue("ERROR", "FM02", rel, message))
            else:
                issues.append(Issue("ERROR", "FM02", rel, f"unreadable directory: {path.name}"))
            continue
        pages.append(page)
        _check_page(page, issues)

    source_slugs = {p.slug for p in pages if p.folder == "sources"}
    slug_counts = Counter(p.slug for p in pages)
    slugs = set(slug_counts)
    for page in pages:
        rel = f"wiki/{page.folder}/{page.slug}.md"
        if slug_counts[page.slug] > 1:
            issues.append(Issue("ERROR", "DU01", rel, f"duplicate slug: {page.slug}"))
        sources = page.meta.get("sources")
        if isinstance(sources, list):
            for item in sources:
                if not isinstance(item, str) or not (
                    item in source_slugs
                    or (item.startswith("raw/") and _norm_posix(item).startswith("raw/"))
                ):
                    issues.append(Issue(
                        "ERROR", "FM02", rel,
                        f"sources entry must be a raw/ path or existing source-page slug: {item}",
                    ))
        for slug in page.links:
            if slug not in slugs:
                issues.append(Issue("ERROR", "LK01", rel, f"broken link: [[{slug}]]"))
        if not any(
            other is not page and slug == page.slug
            for other in pages
            for slug in other.links
        ):
            issues.append(Issue("WARN", "OR01", rel, "orphan page"))
        if not page.links:
            issues.append(Issue(
                "WARN", "CT01", rel,
                "no citation: every factual claim must include at least one [[source-slug]] link",
            ))

    _check_index(wiki, pages, issues)
    _check_log(wiki, issues)

    issues.sort(key=lambda i: (i.path, i.code))
    return issues


def run(args: argparse.Namespace) -> int:
    root = Path(args.root)
    prefix = Path(root.anchor) if root.is_absolute() else Path()
    for part in root.parts[1:] if root.is_absolute() else root.parts:
        prefix = prefix / part
        if prefix.is_symlink():
            print(f"error: {prefix} is a symlink; refusing to read", file=sys.stderr)
            return 2
    wiki = root / "wiki"
    if wiki.is_symlink():
        print(f"error: {wiki} is a symlink; refusing to read", file=sys.stderr)
        return 2
    if not wiki.is_dir():
        print(f"error: no wiki dir at {wiki}", file=sys.stderr)
        return 2
    issues = lint(wiki)
    if args.strict:
        issues = [Issue("ERROR", i.code, i.path, i.message) for i in issues]
    for issue in issues:
        print(f"{issue.severity} {issue.code} {issue.path}: {issue.message}")
    errors = sum(1 for i in issues if i.severity == "ERROR")
    warnings = len(issues) - errors
    print(f"lint: {errors} errors, {warnings} warnings")
    return 0 if errors == 0 else 1
