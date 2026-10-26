"""Search the wiki pages."""

import argparse
import sys
from pathlib import Path

from brainstew.pages import Page, discover_pages

WEIGHTS = (("title", 10), ("summary", 5), ("body", 1))


def _title(page: Page) -> str:
    title = page.meta.get("title")
    return title if isinstance(title, str) else ""


def _score(page: Page, terms: list[str]) -> int:
    total = 0
    for field, weight in WEIGHTS:
        text = page.meta.get(field) if field != "body" else page.body
        if isinstance(text, str):
            lowered = text.lower()
            total += weight * sum(lowered.count(t) for t in terms)
    return total


def search(wiki: Path, query: str) -> list[tuple[Page, int]]:
    terms = query.lower().split()
    if not terms:
        return []
    scored = []
    for _, page in discover_pages(wiki):
        if page is None:
            continue
        score = _score(page, terms)
        if score > 0:
            scored.append((page, score))
    scored.sort(key=lambda ps: (-ps[1], _title(ps[0])))
    return scored


def run(args: argparse.Namespace) -> int:
    if args.limit < 0:
        print(f"error: --limit must be >= 0, got {args.limit}", file=sys.stderr)
        return 2
    wiki = Path(args.root) / "wiki"
    if not wiki.is_dir():
        print(f"error: no wiki dir at {wiki}", file=sys.stderr)
        return 2
    results = search(wiki, args.query)
    if not results:
        return 1
    for page, _ in results[: args.limit]:
        print(f"{page.slug}\t{page.meta.get('type', '')}\t{page.meta.get('summary', '')}")
    return 0
