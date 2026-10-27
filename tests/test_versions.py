import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from repo_policy.af import main as af_main
from repo_policy.cli import main
from repo_policy.engine import run
from repo_policy.model import PolicyError
from repo_policy.versions import semver


class VersionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repo"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "core.autocrlf", "false")
        self.rule = {
            "id": "release-version",
            "kind": "version-increment",
            "path": "pyproject.toml",
            "pattern": '^version = "(?P<version>[^"\\r\\n]+)"\\r?$',
        }
        self.config()
        self.version("0.1.0")
        self.put("README.md", "# Fixture\n")

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
        return path

    def version(self, value):
        return self.put("pyproject.toml", f'[project]\nversion = "{value}"\n')

    def config(self, **options):
        self.put(
            ".repo-policy/policy.yaml",
            yaml.safe_dump({"version": 2, "rules": [self.rule], **options}),
        )

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), "-c", "core.hooksPath=/dev/null", *args],
            check=True,
            capture_output=True,
        ).stdout

    def commit(self, message="fixture"):
        self.git("add", "--all")
        self.git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=tests@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--allow-empty",
            "-m",
            message,
        )
        return self.git("rev-parse", "HEAD").decode().strip()

    def test_initial_version_and_non_git_error_are_explicit(self):
        report = run(self.root, files=[])
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["repository_checks"][0]["baseline"], "initial")
        self.commit()
        self.assertEqual(run(self.root)["exit_code"], 0)
        with tempfile.TemporaryDirectory() as temporary:
            other = Path(temporary).resolve()
            (other / ".repo-policy").mkdir()
            (other / ".repo-policy/policy.yaml").write_bytes(
                (self.root / ".repo-policy/policy.yaml").read_bytes()
            )
            with self.assertRaises(PolicyError):
                run(other)

    def test_working_changes_require_bump_even_with_empty_selection(self):
        head = self.commit()
        self.put("README.md", "# Edited\n")
        report = run(self.root, files=[])
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["diagnostics"][0]["rule"], "release-version")
        self.assertEqual(report["repository_checks"][0]["base_commit"], head)
        self.version("0.1.1")
        self.assertEqual(run(self.root, files=[])["exit_code"], 0)
        self.version("0.0.9")
        self.assertEqual(run(self.root)["exit_code"], 1)

    def test_version_gate_ignores_selectors_but_honors_explicit_exception(self):
        self.rule.update(files=["never/*"], exclude=["**/*"])
        self.config(exclude=["pyproject.toml"])
        self.commit()
        self.put("README.md", "# Changed\n")
        self.assertEqual(run(self.root, files=[])["exit_code"], 1)
        self.config(
            exclude=["pyproject.toml"],
            exceptions=[
                {
                    "rule": "release-version",
                    "files": ["pyproject.toml"],
                    "reason": "Explicit fixture waiver",
                }
            ],
        )
        self.assertEqual(run(self.root, files=[])["exit_code"], 0)

    def test_crlf_and_clean_checkout_validate_the_same_bump(self):
        self.commit()
        self.put("pyproject.toml", b'[project]\r\nversion = "0.2.0"\r\n')
        self.assertEqual(run(self.root)["exit_code"], 0)
        sha = self.commit()
        self.assertEqual(run(self.root)["exit_code"], 0)
        self.assertEqual(run(self.root, commit=sha)["exit_code"], 0)

    def test_untracked_only_does_not_change_baseline_but_staged_addition_does(self):
        self.commit()
        self.put("local.json", "{}\n")
        self.assertEqual(run(self.root)["exit_code"], 0)
        self.git("add", "local.json")
        report = run(self.root, files=[])
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["repository_checks"][0]["baseline"], "head")

    def test_deletion_only_and_empty_commits_cannot_skip_check(self):
        self.commit()
        (self.root / "README.md").unlink()
        self.assertEqual(run(self.root, mode="changed")["exit_code"], 1)
        deletion = self.commit()
        report = run(self.root, commit=deletion)
        self.assertEqual(report["files_checked"], [])
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(run(self.root)["exit_code"], 1)
        empty = self.commit()
        self.assertEqual(run(self.root, commit=empty)["exit_code"], 1)

    def test_exact_commit_ignores_dirty_versions_and_compares_first_parent(self):
        initial = self.commit()
        self.version("0.2.0")
        sha = self.commit()
        self.version("9.0.0")
        report = run(self.root, commit=sha)
        self.assertEqual(report["exit_code"], 0)
        summary = report["repository_checks"][0]
        self.assertEqual(summary["current_version"], "0.2.0")
        self.assertEqual(summary["previous_version"], "0.1.0")
        self.assertEqual(summary["base_commit"], initial)
        self.assertEqual(summary["baseline"], "first_parent")
        self.version("0.2.0")
        self.put("README.md", "# No bump\n")
        bad = self.commit()
        self.version("9.1.0")
        self.assertEqual(run(self.root, commit=bad)["exit_code"], 1)

    def test_first_version_source_can_be_introduced_but_invalid_baseline_fails(self):
        (self.root / "pyproject.toml").unlink()
        self.commit()
        self.version("0.1.0")
        self.assertEqual(run(self.root)["exit_code"], 0)
        self.version("invalid")
        self.commit()
        self.version("0.2.0")
        with self.assertRaisesRegex(PolicyError, "cannot parse the version baseline"):
            run(self.root)

    def test_invalid_current_version_and_duplicate_matches_are_violations(self):
        self.commit()
        for value in ("01.2.3", "1.2", "1.2.3-01", "1.2.3+", "v1.2.3"):
            with self.subTest(value=value):
                self.version(value)
                self.assertEqual(run(self.root)["exit_code"], 1)
        self.put("pyproject.toml", 'version = "0.2.0"\nversion = "0.3.0"\n')
        self.assertEqual(run(self.root)["exit_code"], 1)
        self.put("pyproject.toml", b'version = "0.2.0"\n\xff')
        self.assertEqual(run(self.root)["exit_code"], 1)
        (self.root / "pyproject.toml").unlink()
        self.assertEqual(run(self.root, files=[])["exit_code"], 1)

    def test_missing_git_parent_is_execution_error_not_bootstrap(self):
        parent = self.commit()
        self.version("0.2.0")
        child = self.commit()
        path = self.root / ".git/objects" / parent[:2] / parent[2:]
        path.chmod(0o600)
        path.unlink()
        with self.assertRaises(PolicyError):
            run(self.root, commit=child)
        with self.assertRaises(PolicyError):
            run(self.root)

    def test_current_and_baseline_sources_are_bounded(self):
        self.config(max_file_bytes=64)
        self.put("pyproject.toml", "# " + "x" * 128 + '\nversion = "0.1.0"\n')
        self.commit()
        self.assertEqual(run(self.root)["exit_code"], 1)
        self.version("0.2.0")
        with self.assertRaisesRegex(PolicyError, "baseline exceeds max_file_bytes"):
            run(self.root)

    def test_semver_order_and_build_metadata(self):
        values = [
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-alpha.beta",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
            "1.0.0",
            "1.0.1",
            "1.1.0",
        ]
        self.assertEqual(sorted(values, key=semver), values)
        self.assertEqual(semver("1.0.0+old"), semver("1.0.0+new"))
        self.version("1.0.0+old")
        self.commit()
        self.version("1.0.0+new")
        self.assertEqual(run(self.root)["exit_code"], 1)

    def test_invalid_config_is_rejected_and_old_rules_stay_unchanged(self):
        for options in (
            {"path": "../outside"},
            {"pattern": "("},
            {"pattern": "(.*)"},
            {"pattern": None},
        ):
            with self.subTest(options=options):
                original = self.rule.copy()
                self.rule.update(options)
                self.config()
                with self.assertRaises(PolicyError):
                    run(self.root)
                self.rule = original
        self.put(".repo-policy/policy.yaml", "version: 2\nrules: []\n")
        self.assertNotIn("repository_checks", run(self.root))

    def test_local_and_af_reports_identical_and_fix_does_not_raise_version(self):
        self.commit()
        self.put("README.md", "# Edited\n")
        before = (self.root / "pyproject.toml").read_bytes()
        report = run(self.root, files=[])
        self.assertEqual(run(self.root, files=[], fix=True), report)
        self.assertEqual((self.root / "pyproject.toml").read_bytes(), before)
        output = self.root.parent / "output"
        with contextlib.redirect_stdout(io.StringIO()):
            code = af_main(
                [
                    "--root",
                    str(self.root),
                    "--session-root",
                    str(self.root.parent),
                    "--output-dir",
                    str(output),
                    "--all",
                ]
            )
        self.assertEqual(code, 1)
        self.assertEqual(json.loads((output / "report.json").read_text()), run(self.root))
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(
                ["check", "--root", str(self.root), "--files", "README.md", "--format", "json"]
            )
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(buffer.getvalue())["schema_version"], 1)

    def test_fix_on_clean_checkout_requires_bump_after_creating_tracked_change(self):
        self.put("README.md", "Missing newline")
        self.put(
            ".repo-policy/policy.yaml",
            yaml.safe_dump(
                {
                    "version": 2,
                    "rules": [
                        self.rule,
                        {
                            "id": "newline",
                            "kind": "final-newline",
                            "safe_fix": True,
                            "files": ["README.md"],
                        },
                    ],
                }
            ),
        )
        self.commit()
        report = run(self.root, fix=True)
        self.assertEqual(report["fixed"], ["README.md"])
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual([d["rule"] for d in report["diagnostics"]], ["release-version"])
        self.assertEqual(report["repository_checks"][0]["baseline"], "head")
        self.version("0.1.1")
        self.assertEqual(run(self.root)["exit_code"], 0)
