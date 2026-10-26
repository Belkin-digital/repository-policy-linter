# Integration details

## External dependency and portability

Use an actual published version or a wheel with an immutable digest. Never install an unrelated
package just because a name matches this unreleased project. Example helper call (replace the
example source/digest with the actual built wheel; an illustrative URL is not a published artifact):

```text
python3 <skill>/scripts/configure.py --root <target> --engine 'repository-policy-linter @ file:///absolute/path/to/repository_policy_linter-0.1.0-py3-none-any.whl#sha256=<actual-64-hex-digest>'
```

Preview first, then repeat with `--apply`. Target dependency files are left unchanged if they
exist; inspect `matches: false` and reconcile manually. The helper accepts exact package versions
or credential-free wheel URLs with SHA-256; it does not resolve existence or install anything.
It refuses symlink output files and existing managed instruction sections are preserved.
The engine wheel is an external dependency; config, locks and integration snippets belong in target.
For a portable rollout publish the exact wheel in an approved internal artifact store and use its
HTTPS URL + digest in local/CI/AF installation. Lock transitive dependencies through the target's
manager or an offline wheelhouse; `==` pins alone are not a full supply-chain lock.

## pre-commit

Merge one local hook into existing `repos:`; retain comments, stages, exclusions and other hooks.
Use the existing environment manager when it provides a deterministic entry command:

```yaml
repos:
  - repo: local
    hooks:
      - id: repo-policy
        name: Repository policy
        language: system
        entry: .venv-policy/bin/repo-policy check --files
        pass_filenames: true
        types: [file]
        require_serial: true
```

On Windows choose the `Scripts/repo-policy.exe` path or the repository's cross-platform launcher.
If plugins were reviewed, place `--allow-plugins` **before** `--files`. A portable alternative is
`language: python` with exact engine `additional_dependencies`; specialist tools must then also
exist in that hook environment. Run `pre-commit validate-config` and `pre-commit run --all-files`.
Install Git hooks only when target setup authorization covers it; never overwrite custom hook
scripts. pre-commit normally stashes unstaged changes; direct CLI always checks working-tree
contents, not an independent index snapshot. Hook-only checks are not the platform trust boundary.
See [official local-hook guidance](https://pre-commit.com/#repository-local-hooks).

## CI

Extend existing CI with a pinned dependency installation and `repo-policy check --all`; prefer a
native manager/lock. For a PR incremental mode fetch sufficient history and use
`check --changed --base <trusted base ref>`. Missing history fails; never silently replace the base.
Establish baseline violations in a nonblocking pilot before enforcing. Do not run fix automatically
in CI. Keep plugins in a separately reviewed, pinned environment, with no credentials for fork runs.
Engine/runtime changes and policy changes must be visible in review.

## Agent instructions

Keep rule definitions in `.repo-policy.yaml`. Add only installation/check commands and a link to
policy in the maintained AGENTS/CLAUDE source. Preserve symlink/import/generated conventions;
the helper refuses a symlink rather than replacing it. If `.claude` is generated, update its source
and run the existing generator only when authorized. Record the clean/known-violations baseline.

## AF Runner / platform observation

The platform uses the exact same package, policy and plugin toolchain. Within the selected checkout:

```text
repo-policy-af --root /session/work/repos/selected --session-root /session --output-dir /session/runs/<run-id>/policy-output --all
```

The wrapper returns the policy exit code, `report.json` and `outputs.fragment.json`. It never
overwrites Runner's result manifest. Runner can merge the fragment after applying its own artifact
and access policy; `publish` defaults to false. Do not invent Skill manifests: the AF native format
is a versioned declarative integration contract, not a `protocol: shell` package installer.

For gradual migration, run trusted push/PR checks on the exact head SHA in observation mode,
compare normalized local/Runner diagnostics using identical pins, then enable required checks by
explicit repository selection. Store SHA/config/engine/toolchain provenance, deduplicate events,
reject stale results and keep fork execution isolated. Server-side checks must use an approved
policy baseline so an agent cannot disable its own gate by changing config in the PR.
