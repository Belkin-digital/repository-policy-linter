---
created: 2026-10-26
updated: 2026-10-26
---

# Release and versioning

Version 0.1.0 source is available in the public
[GitHub repository](https://github.com/Belkin-digital/repository-policy-linter).
Wheels are built locally; no registry name ownership or package release is assumed.
The package metadata version and `repo_policy.__version__` must match. CLI `--version` prints it;
reports carry engine/config/diagnostic schema versions. SemVer applies to the package; a breaking
config/diagnostic schema requires a new explicit schema version, not silent reinterpretation.

1. Run locked tests, formatting/lint, policy, pre-commit and `uv build`.
2. Run `uv run python scripts/smoke_wheel.py`: install into a fresh environment with no source
   checkout import. Dependency installation may access the package registry; the installed
   checker runs locally without network. Use an approved wheelhouse for offline installation.
3. Compute SHA-256 of the wheel; retain the source commit and dependency lock. Install the skill
   in a disposable scope and test setup twice in a disposable target repository.
4. After the chosen remote/registry is available and publication is authorized, push the reviewed
   commit, tag `v0.1.0` and upload the wheel/sdist/checksums. Package naming must be verified at
   that time; do not overwrite another distribution or reuse an existing release version.
5. Point target dependency locks to the same immutable distribution for local agents, CI and AF.
   Use an internal wheelhouse for offline operation. Keep skill installation separate from engine
   installation; changing a skill does not silently upgrade the engine in target repositories.

The source repository contains `scripts/install_skill.py`; it copies only `skills/repo-policy-setup`
to an explicit destination. The engine wheel intentionally contains no repository setup scripts
or auto-install hooks. The source distribution includes the skill and project documentation.
