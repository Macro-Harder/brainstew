"""Page discovery and link extraction for the wiki."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from llmwiki.frontmatter import parse_frontmatter

PAGE_DIRS = ("sources", "entities", "concepts", "synthesis")
LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass
class Page:
    slug: str
    path: Path
    folder: str
    meta: dict[str, str | list[str]]
    body: str
    links: list[str] = field(default_factory=list)


def iter_page_files(wiki: Path) -> list[Path]:
    files: list[Path] = []
    for folder in PAGE_DIRS:
        d = Path(wiki) / folder
        if d.is_dir():
            files.extend(sorted(p for p in d.iterdir() if p.is_file() and p.suffix == ".md"))
    return files


def load_page(path: Path) -> tuple[Path, Page | None]:
    """Read one page file; return (path, None) when frontmatter is invalid."""
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    return path, Page(
        slug=path.stem,
        path=path,
        folder=path.parent.name,
        meta=meta,
        body=body,
        links=[m.group(1) for m in LINK_RE.finditer(body)],
    )


def discover_pages(wiki: Path) -> list[tuple[Path, Page | None]]:
    """Load every page under the four wiki subfolders (non-recursive).

    index.md, log.md and stray .md files in wiki/ root are not pages.
    Unreadable pages come back as (path, None) so lint can flag them.
    """
    out: list[tuple[Path, Page | None]] = []
    for path in iter_page_files(Path(wiki)):
        try:
            out.append(load_page(path))
        except ValueError:
            out.append((path, None))
    return out
