"""Show entries from the wiki log."""

import argparse
import re
import sys
from pathlib import Path

OP_RE = re.compile(r"## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|edit) \| ")


def split_entries(text: str) -> list[tuple[str, list[str]]]:
    """Split log text into (heading, bullet lines) pairs."""
    entries: list[tuple[str, list[str]]] = []
    heading: str | None = None
    bullets: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if heading is not None:
                entries.append((heading, bullets))
            heading = line
            bullets = []
        elif line.startswith("- ") and heading is not None:
            bullets.append(line)
    if heading is not None:
        entries.append((heading, bullets))
    return entries


def read_log(wiki: Path) -> list[tuple[str, list[str]]]:
    return split_entries((wiki / "log.md").read_text(encoding="utf-8"))


def render(entries: list[tuple[str, list[str]]]) -> str:
    return "\n\n".join("\n".join([h, *b]) for h, b in entries)


def run(args: argparse.Namespace) -> int:
    wiki = Path(args.root) / "wiki"
    log = wiki / "log.md"
    if not log.is_file():
        print(f"error: no log.md at {log}", file=sys.stderr)
        return 2
    entries = read_log(wiki)
    if args.op:
        entries = [e for e in entries if OP_RE.match(e[0]) and OP_RE.match(e[0]).group(1) == args.op]
    if args.n > 0:
        entries = entries[-args.n:]
    else:
        entries = []
    if entries:
        print(render(entries))
    return 0
