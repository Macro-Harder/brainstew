"""Lint checks for the wiki."""

import argparse
import datetime
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from brainstew.frontmatter import FrontmatterError
from brainstew.pages import LINK_RE, discover_pages

REQUIRED = ("title", "type", "summary", "sources", "updated")
FOLDER_OF = {"source": "sources", "entity": "entities", "concept": "concepts", "synthesis": "synthesis"}
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
LOG_HEADING_RE = re.compile(r"## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|edit) \| \S")


@dataclass
class Issue:
    severity: str
    code: str
    path: str
    message: str


def _valid_date(value: str) -> bool:
    try:
        datetime.date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _check_page(page, issues: list[Issue]) -> None:
    rel = str(page.path)
    missing = [f for f in REQUIRED if f not in page.meta]
    if missing:
        issues.append(Issue("ERROR", "FM01", rel, f"missing fields: {', '.join(missing)}"))
    updated = page.meta.get("updated")
    if isinstance(updated, str) and (
        not DATE_RE.match(updated) or not _valid_date(updated)
    ):
        issues.append(Issue("ERROR", "FM02", rel, f"updated not YYYY-MM-DD: {updated}"))
    page_type = page.meta.get("type")
    if isinstance(page_type, str) and (
        page_type not in FOLDER_OF or FOLDER_OF[page_type] != page.folder
    ):
        issues.append(Issue("ERROR", "TY01", rel, f"type {page_type} in folder {page.folder}"))


def lint(wiki: Path) -> list[Issue]:
    issues: list[Issue] = []
    pages = []
    for path, page in discover_pages(wiki):
        if page is None:
            issues.append(Issue("ERROR", "FM02", str(path), "invalid frontmatter"))
            continue
        pages.append(page)
        _check_page(page, issues)

    slug_counts = Counter(p.slug for p in pages)
    slugs = set(slug_counts)
    for page in pages:
        rel = str(page.path)
        if slug_counts[page.slug] > 1:
            issues.append(Issue("ERROR", "DU01", rel, f"duplicate slug: {page.slug}"))
        for slug in page.links:
            if slug not in slugs:
                issues.append(Issue("ERROR", "LK01", rel, f"broken link: [[{slug}]]"))
        if not any(
            other is not page and slug == page.slug
            for other in pages
            for slug in other.links
        ):
            issues.append(Issue("WARN", "OR01", rel, "orphan page"))

    index = wiki / "index.md"
    if not index.is_file():
        issues.append(Issue("ERROR", "IX03", "wiki/index.md", "missing index.md"))
    else:
        referenced = {m.group(1) for m in LINK_RE.finditer(index.read_text(encoding="utf-8"))}
        for slug in sorted(referenced - slugs):
            issues.append(Issue("ERROR", "IX02", "wiki/index.md", f"unknown slug: [[{slug}]]"))
        for page in pages:
            if page.slug not in referenced:
                issues.append(Issue("ERROR", "IX01", str(page.path), "not listed in index.md"))

    log = wiki / "log.md"
    if not log.is_file():
        issues.append(Issue("ERROR", "LG02", "wiki/log.md", "missing log.md"))
    else:
        for line in log.read_text(encoding="utf-8").splitlines():
            if line.startswith("## ") and not LOG_HEADING_RE.match(line):
                issues.append(Issue("ERROR", "LG01", "wiki/log.md", f"bad heading: {line}"))
                break

    issues.sort(key=lambda i: (i.path, i.code))
    return issues


def run(args: argparse.Namespace) -> int:
    wiki = Path(args.root) / "wiki"
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
