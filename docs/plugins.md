---
created: 2026-10-26
updated: 2026-10-27
---

# External tool plugins

The engine routes file sets and normalizes diagnostics. It never installs tools at check time,
uses `shell=False`, passes root-relative files as separate `./path` arguments, and never adds fix
flags. Review executable paths, options, native configs and dependency locks before enabling
`--allow-plugins`. The flag authorizes all configured plugins for this invocation.

On Windows, bare executable names are resolved through the caller's `PATH` before launch,
so a `python` plugin uses the selected environment instead of Windows choosing the parent
interpreter's installation directory. Explicit executable paths keep their configured meaning.
See Python's [executable resolution guidance](https://docs.python.org/3/library/subprocess.html#popen-constructor).

Real Ruff integration (Ruff retains all Python analysis logic):

```yaml
version: 2
plugins:
  - id: python-ruff
    command: [ruff, check, --no-fix, --output-format, json, '{files}']
    format: ruff
    files: ['**/*.py']
    timeout: 30
    success_codes: [0]
    diagnostic_codes: [1]
```

This uses Ruff's documented [CLI and JSON output](https://docs.astral.sh/ruff/configuration/).
Pin Ruff alongside the engine in dev tooling. This project's own policy invokes this adapter
against its source, scripts and tests. `--no-fix` overrides an accidental native `fix=true`.

Three formats are supported:

| Format | Expected stdout |
| --- | --- |
| `json` | JSON array of `{file, line, column?, message, code?}`; positive one-based locations |
| `ruff` | Native Ruff JSON array (`filename`, `location.row/column`, `message`, `code`) |
| `regex` | Every nonempty stdout line matches a configured regex with named `file`, `line`, `message` and optional `column`, `code` groups |

## Repository-scoped checks

Engine 0.4.0 adds optional `scope: repository`; the default `scope: files` preserves existing
selected-file behavior. Use repository scope for deterministic cross-file metadata and required
configuration checks. For example:

```yaml
plugins:
  - id: project-metadata
    scope: repository
    command: [python, .repo-policy/scripts/check_project.py, '{files}']
    format: json
    files: [pyproject.toml, uv.lock, CHANGELOG.md]
```

The engine runs this command even with empty or deletion-only selection and even when no
declared input exists. `{files}` receives discovered safe/unignored matching files across the
repository, independently of the requested selection and global exclusions. Built-in pruned
directories remain omitted. The checker may read its declared required paths directly and
report missing ones. Its diagnostics must match its own `files`/`exclude` patterns and remain
safe/root-relative; unlike ordinary plugins they need not name a selected or existing file.
Global exclusions and contract selectors cannot disable a repository check. Reasoned exceptions
suppress its matching diagnostics after output validation. Scope never expands OS permissions.

`--allow-plugins` is required even with no inputs; the engine does not certify that a script is
read-only. Review the implementation and pin its runtime/dependencies. Commit mode still runs
the committed script/configuration in an exact snapshot without `.git`; Git-dependent checks
need an explicit supported design, not discovery of another checkout.

The schema-version-1 `repository_checks` array gains entries with `rule`, `kind: plugin`,
`scope: repository` and `files_checked` (actual file arguments). Top-level `files_checked`
continues to describe the requested selection. Native file plugins retain their old output
boundary and report shape; local/AF reports stay identical for identical inputs/toolchains.
See the [project rule audit](rule-coverage.md) for concrete checked facts and limits.

For example, yamllint's existing parsable output can be consumed without implementing YAML style:

```yaml
plugins:
  - id: yaml-style
    command: [yamllint, --format, parsable, '{files}']
    format: regex
    files: ['**/*.yaml', '**/*.yml']
    pattern: '(?P<file>.+):(?P<line>\d+):(?P<column>\d+): (?P<message>.+)'
    diagnostic_codes: [1]
```

Validate the output of your pinned tool before adoption. Other tools (markdownlint, ESLint,
Spectral, JSON Schema validators, compiler checks) can use native parsable output or a small
local output translator. Such translators only normalize diagnostics; they must not reproduce
the tool's checking logic. There is no claim of a bundled adapter for every tool format.

Tool messages are preserved and may contain source excerpts; engine reports should be handled
as repository data. Native tool rule codes are prefixed in `message`; the enclosing plugin id
is the stable engine `rule`. Severity is configured per plugin. Use native tool settings for
per-native-rule levels and suppressions.

Missing executables, timeout, malformed/unrecognized output, diagnostics outside selected/declared paths,
failed commands without diagnostics or unexpected return codes all fail with exit 2. Output is
captured to temporary files and limited to 4 MiB per stream when read; disk use while a tool runs
is not capped. Timeout is 1–300 seconds (default 30); on POSIX the process group is killed on timeout.
Large file sets may exceed OS command-line limits and then fail explicitly; batching is future work.

Plugins inherit the caller's environment and permissions. They can access the network or mutate
files if their implementation/config does so. This is an execution adapter, not an OS sandbox.
Use a container with network disabled, read-only checkout, resource limits and scrubbed credentials
for webhook/fork checks. No plugins run in the default starter configuration.
