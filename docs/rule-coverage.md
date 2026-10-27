---
created: 2026-10-27
updated: 2026-10-27
---

# AGENTS rule coverage

This audit maps the current [repository instructions](../AGENTS.md) to checks and names the
remaining limits. It introduces no rubric criterion, review scope or automatic review trigger.
Universal setup guidance lives in the standalone [skill](../skills/repo-policy-setup/SKILL.md)
and [rule-design reference](../skills/repo-policy-setup/references/rule-design.md), and is included
in fresh generated target instructions. This project's Python layout and release conventions
are enforced by its own [project registry](../.repo-policy/checks/project.yaml).

| Requirement | Enforcement | What remains outside this check |
| --- | --- | --- |
| Python 3.11+, one core dependency | `project-integrity`: parsed `requires-python`, Ruff target, exactly one unconditional PyYAML dependency; direct core imports limited to stdlib/yaml/markdown_it/self | Runtime compatibility is tested in the Python CI matrix; import checks do not prove every execution path |
| Source checkout is the engine; no circular wheel dependency | Required source paths; editable lock entry and no self-dependency across core/extra/dev declarations | Installed environment identity and actual execution are verified by locked CI and wheel smoke tests |
| Local/CI/AF share policy and engine | Canonical frozen hook/CI commands, lock/runtime version agreement; local/AF parity and schema compatibility tests | A static check cannot prove a remote harness used those inputs |
| No core network/telemetry/LLM clients | AST guard rejects known direct network/client import families, including aliases; rejects undeclared third-party imports | Dynamic imports, subprocess behavior, arbitrary stdlib calls and plugin permissions require code review/runtime isolation; no sandbox claim |
| External tools explicit, reviewed, check-only | Engine requires `--allow-plugins`; check-only canonical hooks, Ruff `--no-fix`, safe paths/output scope | Human authorization and arbitrary plugin behavior cannot be inferred from configuration |
| Safe fixes opt-in and newline-only | Existing engine implementation and byte/mode/symlink/concurrency regression tests; canonical hooks use `check` | Tests establish covered behavior, not arbitrary future code correctness |
| Skill independent of engine source | Bootstrap configurator is stdlib-only; detects a vendored `repo_policy` directory; starter asset parity and isolated installer smoke | Post-install helpers may use the external engine; arbitrarily renamed/copied logic is not recognized by a package-name guard |
| Increment version before every commit | Built-in `version-increment`, active even with empty/deletion-only selection | Choosing a meaningful SemVer increment remains an author decision; CI validates its checked commit, not all historical commits |
| Keep package/runtime/lock/examples consistent | `project-integrity` compares TOML, literal AST `__version__`, editable lock version, compatible lock entries for unconditional requirements, and literal current distribution references | Historical delivery documents, conditional dependency resolution and feature minimum versions are outside these matching checks |
| Update changelog | First changelog version equals the package version and its section is nonempty | Relevance and completeness of release notes need judgment |
| Frozen tests/lint/format/policy/build before completion | At least one CI job retains the canonical frozen command set and first-parent history; pre-commit settings are checked | A file linter cannot prove an agent executed commands before reporting completion |
| Hooks always run, including deletion-only commits, and never stage/fix | Canonical entries and `always_run`, `pass_filenames`, serial flags are parsed and checked | New or custom hook implementations need explicit review |
| Disposable test repositories; preserve unrelated changes/local settings | Tests use disposable fixtures; setup integration tests verify preservation and repeatability | General side effects or user intent cannot be proven by finding a temporary-directory call |
| Policy structure, unique IDs and references | Existing unsuppressible `system-*` checks, in every selection mode | Approved policy-baseline control belongs to the platform |
| Scope ID navigation before editing | Entry-point metadata and declared IDs checked by the engine; `explain` resolves contract/explanation | Whether an agent actually read the contract requires harness/person responsibility |
| Markdown reachable from root instructions | Existing full-graph `markdown-navigation`, including changed-file mode | Link intent and prose usefulness are not established by reachability |
| Date presence, preserve `created` | Existing frontmatter keys plus `preserve_keys: [created]`, including native skill `metadata`; local Git snapshot/parent baseline | No authorship/date-accuracy inference, rename lineage, automatic date invention or semantic `updated` freshness check |
| Native skill metadata placement | `project-integrity` checks string name/description, a metadata mapping, and no top-level created/updated duplicates | Full native skill validation still uses the official skill validator; metadata checks do not judge description quality |
| Prefer machine enforcement for new rules | The agent instructions, standalone skill and generated target guidance require the feasibility decision | The quality of that decision is not established by a keyword-presence test |
| Ask before implementing/changing/expanding rubric checks | Explicit approval requirement in AGENTS, skill entrypoint, review/design references and fresh generated target instructions | Authorization evidence and cost choices remain with the user/harness |
| Independent rubric reviewer, exact hashes, stored verdicts, repair limit | Existing hashed requests and approved harness review protocol; protocol regression tests | Core neither launches reviewers nor imports/authenticates verdicts; no new rubric enforcement is added |
| No unrelated deployment/publication/platform mutations | Scope and approval instructions in AGENTS and the standalone skill | A repository linter cannot infer user consent or control arbitrary external side effects |

`project-integrity` is a reviewed read-only Python plugin under `.repo-policy/scripts/`, using
the pinned dev `packaging` parser and the installed engine's safe YAML loader. Its checks parse
metadata/AST, never execute inspected source, and bound each input to 1 MiB. It runs in the
same committed snapshot as other tools and does not need `.git` there. Missing required files
and invalid metadata produce normal diagnostics; unsafe plugin output remains an execution error.

The import guard is a guard on declared syntax, not a proof of a network-free program. The
installation-reference check covers literal wheel/requirement/status versions in README,
release instructions and the skill integration reference. Put historical examples in historical
documents. The CI/hook checks enforce this repository's canonical commands, while tolerating
hook whitespace and CI job renaming; they are not a general shell-program verifier.

With [repository-scoped plugins](plugins.md#repository-scoped-checks) and
[frontmatter preservation](configuration.md#preserving-frontmatter-values), other repositories
can adopt the relevant mechanisms with their own metadata sources and conventions. Run all
checks after integration and exercise meaningful failures in disposable fixtures. Keep optional
rubric proposals unimplemented until the user agrees to their scope and recurring cost.
