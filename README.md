# brainstew

A starter kit for an LLM-maintained markdown wiki, built for coding agents like AgenC.

brainstew implements the LLM Wiki pattern: an agent reads raw source material, distills it into a structured set of linked markdown pages, and keeps that wiki up to date as it works. The wiki becomes a persistent, searchable knowledge base that the agent itself maintains over time, with an index and a log that record what was added and why.

Based on the LLM Wiki idea by Andrej Karpathy (https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

This is an unofficial implementation and is not endorsed by Andrej Karpathy.

## Quickstart

```bash
git clone https://github.com/Macro-Harder/brainstew
cd brainstew
python -m brainstew lint
python -m brainstew search lens
python -m brainstew log
```

The repository ships with a small example wiki (about the Fresnel lens) so every command works out of the box on a fresh clone. After `pip install -e .` the `wiki` command works too, e.g. `wiki lint`.

To grow the wiki, drop a new file into `raw/` and ask your agent to run the wiki-ingest skill on it.

## Using it with an agent

The project is designed for AgenC (or any coding agent that reads AGENTS.md and `.agents/skills/`). For example, you can prompt:

> Ingest raw/my-article.md using the wiki-ingest skill.

The agent reads AGENTS.md for the ground rules, runs the skill's workflow, and leaves the wiki lint-clean. The other two skills cover answering questions from the wiki (wiki-query) and repairing lint issues (wiki-lint).

## How it works

There are three layers:

- `raw/` — immutable source material. Read only; the agent never writes here.
- `wiki/` — the agent-owned knowledge base: source summaries, entity pages, concept pages, and synthesis pages, all connected with `[[slug]]` links.
- `schema` — AGENTS.md and the `.agents/skills/*/SKILL.md` files that tell the agent how to operate.

Three operations drive the wiki:

- **ingest** — read a raw file, create or update source/entity/concept pages, cite every claim, update the index, append to the log.
- **query** — search the wiki, read relevant pages, produce a cited answer, and file durable results as synthesis pages.
- **lint** — check the wiki for structural problems (missing frontmatter, broken links, orphans, index/log inconsistencies) and fix them.

Two files tie it together: `wiki/index.md` lists every page with a one-line summary, and `wiki/log.md` is an append-only history of operations performed on the wiki.

### Directory tree

```
raw/
wiki/
  sources/
  entities/
  concepts/
  synthesis/
    .gitkeep
  index.md
  log.md
```

## CLI reference

```
usage: brainstew [-h] [--root ROOT] {lint,search,log} ...

brainstew: tools for an LLM-maintained markdown wiki (search, lint, log).

positional arguments:
  {lint,search,log}
    lint             check the wiki for issues
    search           search wiki pages
    log              show recent wiki log entries

options:
  -h, --help         show this help message and exit
  --root ROOT        wiki root (default: current dir)
```

```
usage: brainstew lint [-h] [--strict]

options:
  -h, --help  show this help message and exit
  --strict    warnings are errors
```

```
usage: brainstew search [-h] [--limit LIMIT] query

positional arguments:
  query

options:
  -h, --help     show this help message and exit
  --limit LIMIT
```

```
usage: brainstew log [-h] [-n N] [--op {ingest,query,lint,edit}]

options:
  -h, --help            show this help message and exit
  -n N
  --op {ingest,query,lint,edit}
```

Exit codes: 0 on success, 1 for a command-specific failure (lint errors, no search hits), 2 for usage errors or a missing wiki directory.

## Known issues
- F57: 16 failing tests in tests/test_lint.py, caused by the F21 lint change that requires every `sources` entry under raw/ to exist on disk.
- F56: one failing fixture test in tests/test_pages.py (test_symlinked_non_page_dir_still_lints_clean builds pages citing raw/a.txt without creating that file).
- The final full pytest run was not run, so the suite state is unverified.

## License

MIT — see [LICENSE](LICENSE).
