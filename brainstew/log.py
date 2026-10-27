"""Show entries from the wiki log."""

import argparse
import re
import sys
from pathlib import Path

OP_RE = re.compile(r"## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|edit) \| ")


class LogReadError(ValueError):
    """Raised when log.md cannot be read."""


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
    try:
        text = (wiki / "log.md").read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise LogReadError(f"log.md is not valid UTF-8: {exc}") from exc
    except OSError as exc:
        raise LogReadError(f"cannot read log.md: {exc.strerror or exc}") from exc
    return split_entries(text)


_CTRL_RE = re.compile(r"[\x00-\x09\x0b-\x1f\x7f\x80-\x9f]")


def _escape_ctrl(match: re.Match[str]) -> str:
    return "".join(f"\\x{ord(ch):02x}" for ch in match.group())


def render(entries: list[tuple[str, list[str]]]) -> str:
    text = "\n\n".join("\n".join([h, *b]) for h, b in entries)
    return _CTRL_RE.sub(_escape_ctrl, text)


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).absolute()
    current = Path(root.anchor)
    for part in root.parts[1:]:
        current = current / part
        if current.is_symlink():
            print(f"error: {current} is a symlink; refusing to read", file=sys.stderr)
            return 2
    wiki = root / "wiki"
    if wiki.is_symlink():
        print(f"error: {wiki} is a symlink; refusing to read", file=sys.stderr)
        return 2
    log = wiki / "log.md"
    if log.is_symlink():
        print(f"error: {log} is a symlink; refusing to read", file=sys.stderr)
        return 2
    if not log.is_file():
        print(f"error: no log.md at {log}", file=sys.stderr)
        return 2
    try:
        entries = read_log(wiki)
    except LogReadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.op:
        entries = [e for e in entries if OP_RE.match(e[0]) and OP_RE.match(e[0]).group(1) == args.op]
    if args.n > 0:
        entries = entries[-args.n:]
    else:
        entries = []
    if entries:
        print(render(entries))
    return 0
