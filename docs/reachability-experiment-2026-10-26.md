---
created: 2026-10-26
updated: 2026-10-26
---

# Experiment 2: Markdown reachability

The experiment adds `markdown-navigation` (`kind: markdown-reachable`) to the repository's
own policy. The initial run returned exit 1: only `AGENTS.md` was reachable, and the other
18 of 19 Markdown files were unreachable. Inline code paths in the agent instructions did
not count as links. The initial machine-readable report is kept in ignored
`work/reachability-before.json`.

## Agent response

The agent kept the rule enabled and added meaningful navigation: `AGENTS.md` links the
project overview, Claude instructions, documentation index and setup skill source. The
[documentation index](README.md) groups usage guides, platform work, experiments and delivery
records. Existing links connect the skill's integration reference and the copied AF-PM
requirements. No document is hidden by a new exception or exclusion.

The configured root is `AGENTS.md`. This checkout contains the skill's source, not an
installed repository skill; its source is reached by a normal link. Additional existing
installed skills can be explicit roots in another repository. There is no home-directory
scan or assumption that the AF Runner can see local personal skills.

## Behavior and boundaries

The optional `[markdown]` dependency supplies the existing CommonMark parser. The graph
traversal stays local, bounded by the configured file size limit, and does not fetch URLs
or render HTML. Reference links and HTML anchors participate; fenced/inline code, comments,
frontmatter and image alternatives do not. Cycles are handled without recursion.

The complete graph is checked even for `--changed` and `--files`. Deleting a link or a
transit document can orphan an unchanged descendant. Missing roots fail. JSON retains
normal diagnostics and adds a `repository_checks` graph summary. Local and AF execution
share that exact engine and report.

CLI `fix` does not insert links: choosing the right documentation entrypoint requires an
explicit edit. This is a reachability rule; broken-link and anchor validation remain a
separate check. See the [configuration contract](configuration.md#markdown-reachability).

## Verification

After the navigation edits, all **21 of 21** Markdown files are reachable (the two new
files are the documentation index and this report). Both all-file and changed-file checks
return exit 0 with no diagnostics. The final reports are in ignored
`work/reachability-after.json` and `work/reachability-changed.json`.

- 54 unit/integration tests pass, including 17 graph tests and the optional-extra setup test.
  Cases cover multi-hop paths, disconnected cycles, encoded paths, real versus example
  links, explicit installed-skill roots, exclusions, unsafe/missing roots, bounded UTF-8,
  unchanged descendants, deletion-only changes, diagnostic compatibility and AF parity.
- 20 practical self-policy scenarios pass in disposable repositories. Actual Git commits
  prove that an otherwise valid orphan document is blocked, adding its index link succeeds,
  and deleting the transit index is blocked even with an empty changed-file selection.
  The existing newline/date/plugin/hook checks also pass. The live repository's history
  and user-local `docviewer.json` were not modified by these scenarios.
- Frozen dependency sync, Ruff lint and format checks, pre-commit configuration validation,
  both pre-commit hooks and the native skill validator pass.
- Source archive and wheel build successfully; scratch caches and environments are excluded.
  A fresh non-editable wheel install proves the base package works without the parser,
  enabling a graph rule without its extra returns exit 2, installing `[markdown]` enables
  graph checks, and `fix` leaves an orphan's bytes unchanged.
- Distribution smoke testing installs the standalone skill, configures a disposable target
  twice without changes on repetition, installs the digest-pinned external wheel with its
  extra, and runs the target check without copying engine sources.

Local verification used Python 3.14.7 on macOS. The configured Python/OS CI matrix has not
been run remotely, no package has been published and no rollout to other repositories was
performed for this experiment. Unit AF parity is not a deployed platform end-to-end test.
