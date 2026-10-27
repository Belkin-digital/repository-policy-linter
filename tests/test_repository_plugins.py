import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from repo_policy.af import main as af_main
from repo_policy.engine import run
from repo_policy.model import PolicyError


class RepositoryPluginTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "repo"
        self.root.mkdir()
        self.plugin = {
            "id": "metadata",
            "scope": "repository",
            "format": "json",
            "files": ["metadata.json"],
            "command": [
                sys.executable,
                "-c",
                (
                    "import json; print(json.dumps([{'file':'metadata.json','line':1,'message':'missing metadata'}]))"
                ),
                "{files}",
            ],
        }
        self.config()

    def put(self, name, content):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    def config(self, **options):
        self.put(
            ".repo-policy/policy.yaml",
            yaml.safe_dump({"version": 2, "plugins": [self.plugin], **options}),
        )

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE)

    def commit(self):
        self.git("add", ".")
        self.git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "--allow-empty",
            "-m",
            "fixture",
        )
        return self.git("rev-parse", "HEAD").decode().strip()

    def test_repository_plugin_runs_with_empty_selection_and_reports_missing_file(self):
        report = run(self.root, files=[], allow_plugins=True)
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["files_checked"], [])
        self.assertEqual([d["file"] for d in report["diagnostics"]], ["metadata.json"])
        self.assertEqual(report["repository_checks"][0]["files_checked"], [])
        self.plugin.pop("scope")
        self.config()
        ordinary = run(self.root, files=[])
        self.assertEqual(ordinary["exit_code"], 0)
        self.assertNotIn("repository_checks", ordinary)

    def test_permission_is_required_even_with_no_matching_inputs(self):
        with self.assertRaisesRegex(PolicyError, "requires --allow-plugins"):
            run(self.root, files=[])

    def test_global_selection_and_exclusions_do_not_hide_repository_metadata(self):
        self.put("metadata.json", "{}\n")
        self.config(exclude=["metadata.json"])
        report = run(self.root, files=[], allow_plugins=True)
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["repository_checks"][0]["files_checked"], ["metadata.json"])

    def test_repository_output_stays_within_declared_patterns(self):
        self.plugin["files"] = ["other.json"]
        self.config()
        with self.assertRaisesRegex(PolicyError, "outside selected file set"):
            run(self.root, files=[], allow_plugins=True)
        self.plugin["files"] = ["metadata.json"]
        self.plugin["scope"] = "files"
        self.config()
        self.put("metadata.json", "{}\n")
        self.plugin["files"] = ["*.json"]
        self.config()
        self.put("other.json", "{}\n")
        with self.assertRaisesRegex(PolicyError, "outside selected file set"):
            run(self.root, files=["other.json"], allow_plugins=True)

    def test_exception_applies_to_missing_repository_file(self):
        self.config(
            exceptions=[
                {"rule": "metadata", "files": ["metadata.json"], "reason": "Explicit waiver"}
            ]
        )
        self.assertEqual(run(self.root, files=[], allow_plugins=True)["exit_code"], 0)

    def test_unknown_scope_is_configuration_error(self):
        self.plugin["scope"] = "global-ish"
        self.config()
        with self.assertRaisesRegex(PolicyError, "plugin.scope"):
            run(self.root, allow_plugins=True)

    def test_commit_checks_run_repository_plugin_even_for_empty_commit(self):
        self.git("init", "-b", "main")
        self.commit()
        sha = self.commit()
        report = run(self.root, commit=sha, allow_plugins=True)
        self.assertEqual(report["files_checked"], [])
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["diagnostics"][0]["file"], "metadata.json")

    def test_local_af_reports_are_identical(self):
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
                    "--allow-plugins",
                ]
            )
        self.assertEqual(code, 1)
        self.assertEqual(
            json.loads((output / "report.json").read_text()), run(self.root, allow_plugins=True)
        )

    def test_contract_cannot_weaken_repository_plugin(self):
        self.put(
            ".repo-policy/contracts/document.yaml",
            yaml.safe_dump(
                {
                    "contract_version": 1,
                    "id": "document",
                    "files": ["unmatched/*"],
                    "entrypoints": ["AGENTS.md"],
                    "criteria": [{"id": "metadata", "rule": "metadata"}],
                }
            ),
        )
        self.put(
            "AGENTS.md",
            "---\nrepo_policy_root: .repo-policy\nrepo_policy_contracts: [document]\n---\n",
        )
        self.config(contracts=[".repo-policy/contracts/document.yaml"])
        report = run(self.root, files=[], allow_plugins=True)
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["contracts"][0]["status"], "failed")

    def test_explicit_file_scope_preserves_default_report(self):
        self.put("metadata.json", "{}\n")
        self.plugin.pop("scope")
        self.config()
        default = run(self.root, allow_plugins=True)
        self.plugin["scope"] = "files"
        self.config()
        self.assertEqual(run(self.root, allow_plugins=True), default)
