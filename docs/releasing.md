---
created: 2026-10-26
updated: 2026-10-27
---

# Release and versioning

Version 0.4.0 source is available in the public
[GitHub repository](https://github.com/Belkin-digital/repository-policy-linter).
Wheels are built locally; no registry name ownership or package release is assumed.
The package metadata version and `repo_policy.__version__` must match. CLI `--version` prints it;
reports carry engine/config/diagnostic schema versions. SemVer applies to the package; a breaking
config/diagnostic schema requires a new explicit schema version, not silent reinterpretation.

Before every project commit, increment the package version, including documentation/test-only
commits. Use a minor increment for compatible features and a patch increment for fixes and
documentation/test-only changes. Synchronize `pyproject.toml`, `repo_policy.__version__`, the
project entry in `uv.lock`, the changelog and current installation examples in the same commit.
Regenerate the lock with `uv lock`, then install and verify it with `uv sync --frozen`.
An increased package version does not itself create a Git tag, GitHub release or registry release.

The repository enables the built-in `package-version-increment` check from
[the versioning registry](../.repo-policy/checks/versioning.yaml). It compares `pyproject.toml`
against HEAD while tracked changes are pending, and against the first parent on a clean
checkout or with `--commit`. Untracked-only local files do not indicate a pending commit;
stage new project files before the final check. Missing history fails with exit 2. CI fetches
two commits so this comparison can run. See the [rule contract](configuration.md#version-increments)
for initialization, prerelease and file-selection behavior. The check does not choose the next
version or edit files; package/runtime synchronization and wheel installation remain checked
by the tests and release verification below.

1. Run locked tests, formatting/lint, policy, pre-commit and `uv build`.
2. Run `uv run python scripts/smoke_wheel.py`: install into a fresh environment with no source
   checkout import. Dependency installation may access the package registry; the installed
   checker runs locally without network. Use an approved wheelhouse for offline installation.
3. Compute SHA-256 of the wheel; retain the source commit and dependency lock. Install the skill
   in a disposable scope and test setup twice in a disposable target repository.
4. After the chosen remote/registry is available and publication is authorized, push the reviewed
   commit, tag `v<package-version>` and upload the wheel/sdist/checksums. Package naming must be
   verified at that time; do not overwrite another distribution or reuse an existing release version.
5. Point target dependency locks to the same immutable distribution for local agents, CI and AF.
   Use an internal wheelhouse for offline operation. Keep skill installation separate from engine
   installation; changing a skill does not silently upgrade the engine in target repositories.

The source repository contains `scripts/install_skill.py`; it copies only `skills/repo-policy-setup`
to an explicit destination. The engine wheel intentionally contains no repository setup scripts
or auto-install hooks. The source distribution includes the skill and project documentation.
