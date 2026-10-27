"""Page discovery and link extraction for the wiki."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from brainstew.frontmatter import FrontmatterError, parse_frontmatter

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


def iter_page_files(wiki: Path) -> tuple[list[Path], list[Path]]:
    """Return (page files, unreadable category directories)."""
    files: list[Path] = []
    errors: list[Path] = []
    for folder in PAGE_DIRS:
        d = Path(wiki) / folder
        if d.is_symlink():
            errors.append(d)
            continue
        if not d.is_dir():
            continue
        try:
            entries = sorted(d.iterdir())
        except OSError:
            errors.append(d)
            continue
        files.extend(
            p for p in entries
            if p.suffix == ".md" and not p.is_symlink() and p.is_file()
        )
    return files, errors


def load_page(path: Path) -> tuple[Path, Page | None]:
    """Read one page file; return (path, None) when the file is unreadable
    or frontmatter is invalid."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return path, None
    try:
        meta, body = parse_frontmatter(text)
    except FrontmatterError:
        return path, None
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
    Unreadable pages and unreadable category directories come back as
    (path, None) so lint can flag them.
    """
    out: list[tuple[Path, Page | None]] = []
    files, errors = iter_page_files(Path(wiki))
    for path in errors:
        out.append((path, None))
    for path in files:
        try:
            out.append(load_page(path))
        except (ValueError, OSError):
            out.append((path, None))
    return out
