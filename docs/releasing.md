---
created: 2026-10-26
updated: 2026-10-27
---

# Release and versioning

Version 0.4.1 source is available in the public
[GitHub repository](https://github.com/Belkin-digital/repository-policy-linter).
Registry releases use the official
[PyPI project](https://pypi.org/project/repository-policy-linter/). Verify that the selected
version is available there; a source commit or successful build is not a published release.
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
4. After publication is authorized, push the reviewed commit and an immutable
   `v<package-version>` tag. Run the release workflow below, first without uploading, then
   with publishing enabled. Verify package naming; never overwrite another distribution,
   move an existing release tag or reuse an existing release version.
5. Point target dependency locks to the same immutable distribution for local agents, CI and AF.
   Use an internal wheelhouse for offline operation. Keep skill installation separate from engine
   installation; changing a skill does not silently upgrade the engine in target repositories.

The source repository contains `scripts/install_skill.py`; it copies only `skills/repo-policy-setup`
to an explicit destination. The engine wheel intentionally contains no repository setup scripts
or auto-install hooks. The source distribution includes the skill and project documentation.

## First-time PyPI setup

The owner needs a [PyPI account](https://pypi.org/account/register/), a verified email and
two-factor authentication. Complete registration, terms acceptance and recovery setup personally;
do not send passwords, recovery codes or API tokens through the project or chat.

On [account publishing](https://pypi.org/manage/account/publishing/), configure a pending GitHub
publisher for the first release. For an existing project use its Publishing settings instead.
The exact fields for this repository are:

| PyPI field | Value |
| --- | --- |
| PyPI project name | `repository-policy-linter` |
| GitHub repository owner | `Belkin-digital` |
| GitHub repository name | `repository-policy-linter` |
| Workflow filename | `release.yml` |
| Environment name | `pypi` |

Create the matching `pypi` environment in GitHub. A pending publisher creates the PyPI project
on the first successful upload; it does not reserve the name in advance. This workflow uses
short-lived OIDC credentials, without a stored PyPI token. See the official
[pending publisher instructions](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
and [publishing documentation](https://docs.pypi.org/trusted-publishers/using-a-publisher/).

## Manual release workflow

[release.yml](../.github/workflows/release.yml) is manually dispatched from `main`. Its build job
checks out only the requested version tag, verifies the tag against package metadata, retains
first-parent history and runs frozen tests, lint/format, policy, pre-commit, build and wheel smoke
checks. The resulting wheel and sdist are retained as a GitHub Actions artifact with checksums
in the build log. Archive paths and source bytes must match the selected Git tree; local app
settings and other untracked files are not distributable source. This job has no PyPI/OIDC permission.

Run a rehearsal for an existing reviewed tag:

```bash
gh workflow run release.yml --repo Belkin-digital/repository-policy-linter --ref main -f tag=v0.4.1 -f publish=false
```

After the rehearsal passes and the matching publisher is configured, run the same command with
`-f publish=true`. Only the separate `publish` job receives `id-token: write` in the `pypi`
environment. It downloads this run's verified artifact and invokes the official PyPA action;
it does not check out or run project code. No push or tag event automatically publishes packages.
An older reviewed tag, such as `v0.4.0`, may be selected without changing its source or version.

After upload, verify both files and their SHA-256 digests through PyPI's release JSON, then
install the exact version from PyPI in a fresh environment outside the checkout:

```bash
python3 -m venv /tmp/repo-policy-release-check
/tmp/repo-policy-release-check/bin/python -m pip install 'repository-policy-linter[markdown]==0.4.1'
/tmp/repo-policy-release-check/bin/repo-policy --version
```

Exercise `init` and `check` in a disposable repository. Record the source commit, workflow run,
artifact checksums and PyPI version URL. PyPI authorization or a name conflict is a publication
blocker; a successful build or GitHub upload alone must not be reported as a PyPI release.
