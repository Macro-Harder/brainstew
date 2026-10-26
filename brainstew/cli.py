"""Command-line interface for brainstew."""

import argparse
import sys

USAGE = "usage: python -m brainstew [--root PATH] {lint,search,log} ..."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m brainstew",
        description="Lint, search and log a small LLM-maintained wiki.",
    )
    parser.add_argument("--root", default=".", help="wiki root (default: current dir)")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_root(p: argparse.ArgumentParser) -> None:
        p.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    p_lint = sub.add_parser("lint", help="check the wiki for issues")
    p_lint.add_argument("--strict", action="store_true", help="warnings are errors")
    add_root(p_lint)

    p_search = sub.add_parser("search", help="search wiki pages")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=10)
    add_root(p_search)

    p_log = sub.add_parser("log", help="show recent wiki log entries")
    p_log.add_argument("-n", type=int, default=10)
    p_log.add_argument("--op", choices=["ingest", "query", "lint", "edit"])
    add_root(p_log)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "root", None) is None:
        args.root = "."
    if args.command == "lint":
        from brainstew.lint import run
        return run(args)
    if args.command == "search":
        from brainstew.search import run
        return run(args)
    from brainstew.log import run
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
