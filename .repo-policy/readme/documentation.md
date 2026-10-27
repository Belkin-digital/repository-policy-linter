---
created: 2026-10-26
updated: 2026-10-27
---

# documentation

The [documentation contract](../contracts/documentation.yaml) applies to maintained Markdown
except native skill entrypoints. Its `dates` criterion uses the `markdown-dates` check from
the [Markdown registry](../checks/markdown.yaml): YAML frontmatter must contain `created` and
`updated`. `preserve_keys: [created]` compares the existing typed value at the same Git path;
presence/preservation do not prove original date accuracy or follow rename ancestry. Preserve
existing creation dates and use
confirmed history for missing dates, as described in [AGENTS.md](../../AGENTS.md).

Navigation starts in [AGENTS.md](../../AGENTS.md) and the [docs index](../../docs/README.md).
Run `uv run --frozen repo-policy explain documentation` to resolve the contract by ID.
The always-active `markdown-navigation` check separately verifies the full Markdown graph.
