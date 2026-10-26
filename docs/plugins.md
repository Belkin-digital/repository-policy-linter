# External tool plugins

The engine routes file sets and normalizes diagnostics. It never installs tools at check time,
uses `shell=False`, passes root-relative files as separate `./path` arguments, and never adds fix
flags. Review executable paths, options, native configs and dependency locks before enabling
`--allow-plugins`. The flag authorizes all configured plugins for this invocation.

Real Ruff integration (Ruff retains all Python analysis logic):

```yaml
version: 1
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

Missing executables, timeout, malformed/unrecognized output, diagnostics outside selected paths,
failed commands without diagnostics or unexpected return codes all fail with exit 2. Output is
captured to temporary files and limited to 4 MiB per stream when read; disk use while a tool runs
is not capped. Timeout is 1–300 seconds (default 30); on POSIX the process group is killed on timeout.
Large file sets may exceed OS command-line limits and then fail explicitly; batching is future work.

Plugins inherit the caller's environment and permissions. They can access the network or mutate
files if their implementation/config does so. This is an execution adapter, not an OS sandbox.
Use a container with network disabled, read-only checkout, resource limits and scrubbed credentials
for webhook/fork checks. No plugins run in the default starter configuration.
