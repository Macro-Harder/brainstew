# LLM Wiki Agent Instructions

## Layers
- raw/: immutable sources. Read only. Never create, edit, or delete files here.
- wiki/: agent-owned. All creation and editing happens here.
- schema: AGENTS.md and .agents/skills/*/SKILL.md files.

## Rules
- Every factual claim in a wiki page must include at least one citation using [[source-slug]].
- Never write to raw/.
- Every write operation must update wiki/index.md and append an entry to wiki/log.md.
- Slugs are unique. Use [[slug]] for all cross-references.
- Run `python -m brainstew lint` (or `wiki lint` after `pip install -e .`) before finishing any task.

## Workflows

### Ingest
1. Read the target raw/ file completely.
2. Create or update the source summary page in wiki/sources/.
3. Create or update entity pages in wiki/entities/ for key named things.
4. Create or update concept pages in wiki/concepts/ for key ideas.
5. Add or revise [[links]] so every new claim is cited.
6. Update wiki/index.md with one-line entries for all touched pages.
7. Append a log entry: `## [YYYY-MM-DD] ingest | <title>`
8. Run `python -m brainstew lint` and fix any issues.

### Query
1. Run `python -m brainstew search <query>` or read index.md to locate relevant pages.
2. Read the full content of selected pages.
3. Synthesize an answer that includes [[citations]].
4. If the synthesis is durable, write it as a new page in wiki/synthesis/.
5. Update index.md and append `## [YYYY-MM-DD] query | <short title>` to log.md.
6. Run `python -m brainstew lint`.

### Lint
1. Execute `python -m brainstew lint --strict`.
2. For every ERROR, edit the affected page(s) or index/log.
3. For every WARN, either fix or explicitly link the orphan.
4. Re-run lint until clean.
5. Append `## [YYYY-MM-DD] lint | fixed issues` to log.md.
