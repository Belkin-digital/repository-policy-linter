# Repository Policy Linter

Python 3.11+, `src/repo_policy`, one runtime dependency (PyYAML).
Run `uv sync --frozen`, unit tests, `ruff check .`, `ruff format --check .`,
`repo-policy check --all --allow-plugins`, pre-commit and `uv build` before completion.
Use `uv run --frozen` for these commands. Tests use disposable repositories only.

Policy schema, diagnostic schema and return codes are public contracts. Add compatibility
tests when changing them. Local and AF execution must use the same engine and policy, with
identical results given the same file selection and toolchain. Never add network calls or
telemetry to the core. External tools are explicit, trusted plugins; never claim they are sandboxed.
Safe fixes remain opt-in, per-file, byte-preserving except for a final newline.
Keep the installable skill independent of the engine source. Do not deploy into other repos,
publish packages or create platform objects unless the user authorized that scope.
