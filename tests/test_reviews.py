import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from repo_policy.af import main as af_main
from repo_policy.cli import main
from repo_policy.engine import run
from repo_policy.model import PolicyError


class ReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repo"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.email", "tests@example.invalid")
        self.git("config", "user.name", "Test")
        self.git("config", "core.autocrlf", "false")
        self.manifest = {
            "version": 2,
            "contracts": [".repo-policy/contracts/artifact-quality.yaml"],
        }
        self.data(".repo-policy/policy.yaml", self.manifest)
        self.contract = {
            "contract_version": 1,
            "id": "artifact-quality",
            "files": ["artifacts/*"],
            "entrypoints": ["docs/README.md"],
            "criteria": [{"id": "quality", "rubric": ".repo-policy/rubrics/quality.md"}],
        }
        self.data(".repo-policy/contracts/artifact-quality.yaml", self.contract)
        self.put(
            ".repo-policy/rubrics/quality.md", "# Quality\nExplain causes and recovery steps.\n"
        )
        self.put("AGENTS.md", "---\nrepo_policy_root: .repo-policy\n---\n# Agent\n")
        self.put("docs/README.md", "---\nrepo_policy_contracts: [artifact-quality]\n---\n# Docs\n")
        self.put("artifacts/one.md", "# One\n")
        self.put("artifacts/two.md", "# Two\n")

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
        return path

    def data(self, name, value):
        return self.put(name, yaml.safe_dump(value, sort_keys=False))

    def git(self, *args):
        return subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            check=True,
            capture_output=True,
        ).stdout

    def commit(self):
        self.git("add", "--all")
        self.git("commit", "--allow-empty", "-m", "fixture")
        return self.git("rev-parse", "HEAD").decode().strip()

    def cli(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main([*args, "--root", str(self.root)])
        return code, output.getvalue(), errors.getvalue()

    def test_initial_commit_requests_have_stable_byte_hashes_and_no_machine_error(self):
        sha = self.commit()
        report = run(self.root, commit=sha)
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["selection"], "commit")
        self.assertEqual(report["commit"], sha)
        self.assertIsNone(report["base_commit"])
        self.assertTrue(report["review_required"])
        self.assertEqual(report, run(self.root, commit="HEAD"))
        requests = report["review_requests"]
        self.assertEqual(
            [r["artifact"] for r in requests], ["artifacts/one.md", "artifacts/two.md"]
        )
        for request in requests:
            self.assertEqual(request["schema_version"], 1)
            self.assertEqual(request["snapshot"], "commit")
            self.assertEqual(
                request["artifact_sha256"],
                hashlib.sha256((self.root / request["artifact"]).read_bytes()).hexdigest(),
            )
            self.assertEqual(
                request["contract_sha256"],
                hashlib.sha256((self.root / request["contract"]).read_bytes()).hexdigest(),
            )
            criterion = request["criteria"][0]
            self.assertEqual(
                criterion["rubric_sha256"],
                hashlib.sha256((self.root / criterion["rubric"]).read_bytes()).hexdigest(),
            )
            payload = {k: v for k, v in request.items() if k != "request_id"}
            expected = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
            self.assertEqual(request["request_id"], hashlib.sha256(expected.encode()).hexdigest())

    def test_commit_uses_only_immutable_bytes_despite_dirty_index_policy_and_untracked_files(self):
        parent = self.commit()
        committed = b"# Committed\r\n"
        self.put("artifacts/one.md", committed)
        sha = self.commit()
        self.put("artifacts/one.md", "Dirty index\n")
        self.git("add", "artifacts/one.md")
        self.put("artifacts/one.md", "Dirty working tree\n")
        self.put("artifacts/untracked.md", "Untracked\n")
        policy = self.put(".repo-policy/policy.yaml", "invalid: [\n")
        before = policy.read_bytes()
        report = run(self.root, commit=sha)
        self.assertEqual(report["base_commit"], parent)
        self.assertEqual(report["files_checked"], ["artifacts/one.md"])
        self.assertEqual(len(report["review_requests"]), 1)
        self.assertEqual(
            report["review_requests"][0]["artifact_sha256"], hashlib.sha256(committed).hexdigest()
        )
        self.assertEqual(policy.read_bytes(), before)
        self.assertEqual((self.root / "artifacts/one.md").read_text(), "Dirty working tree\n")

    def test_contract_only_change_includes_all_bound_artifacts_and_machine_checks(self):
        self.commit()
        self.manifest["rules"] = [
            {"id": "title", "kind": "required-text", "pattern": "^# ", "files": ["artifacts/*"]}
        ]
        self.data(".repo-policy/policy.yaml", self.manifest)
        self.commit()
        self.contract["criteria"].append({"id": "title", "rule": "title"})
        self.data(".repo-policy/contracts/artifact-quality.yaml", self.contract)
        sha = self.commit()
        report = run(self.root, commit=sha)
        self.assertEqual(
            [r["artifact"] for r in report["review_requests"]],
            ["artifacts/one.md", "artifacts/two.md"],
        )
        self.assertIn("artifacts/two.md", report["files_checked"])
        self.assertNotIn("artifacts/two.md", report["changed_files"])

    def test_shared_rubric_change_rechecks_every_bound_contract(self):
        second = {**self.contract, "id": "second"}
        path = ".repo-policy/contracts/second.yaml"
        self.data(path, second)
        self.manifest["contracts"].append(path)
        self.data(".repo-policy/policy.yaml", self.manifest)
        self.put(
            "docs/README.md",
            "---\nrepo_policy_contracts: [artifact-quality, second]\n---\n# Docs\n",
        )
        self.commit()
        self.put(".repo-policy/rubrics/quality.md", "# More precise criteria\n")
        sha = self.commit()
        requests = run(self.root, commit=sha)["review_requests"]
        self.assertEqual(
            {(r["contract_id"], r["artifact"]) for r in requests},
            {
                (cid, name)
                for cid in ["artifact-quality", "second"]
                for name in ["artifacts/one.md", "artifacts/two.md"]
            },
        )
        self.assertEqual(len({r["request_id"] for r in requests}), 4)

    def test_unrelated_changes_and_empty_commits_do_not_queue_unchanged_artifacts(self):
        self.commit()
        self.put("notes.txt", "Unrelated\n")
        sha = self.commit()
        self.assertEqual(run(self.root, commit=sha)["review_requests"], [])
        sha = self.commit()
        report = run(self.root, commit=sha)
        self.assertEqual(report["files_checked"], [])
        self.assertFalse(report["review_required"])

    def test_rename_uses_destination_and_deletion_does_not_queue_absent_artifact(self):
        self.commit()
        self.git("mv", "artifacts/one.md", "artifacts/renamed.md")
        sha = self.commit()
        self.assertEqual(
            [r["artifact"] for r in run(self.root, commit=sha)["review_requests"]],
            ["artifacts/renamed.md"],
        )
        self.git("rm", "artifacts/renamed.md")
        sha = self.commit()
        self.assertEqual(run(self.root, commit=sha)["review_requests"], [])

    def test_exclusions_apply_when_contract_change_expands_targets(self):
        self.contract["exclude"] = ["artifacts/two.md"]
        self.data(".repo-policy/contracts/artifact-quality.yaml", self.contract)
        self.commit()
        self.put(".repo-policy/rubrics/quality.md", "# Changed\n")
        sha = self.commit()
        self.assertEqual(
            [r["artifact"] for r in run(self.root, commit=sha)["review_requests"]],
            ["artifacts/one.md"],
        )

    def test_working_tree_requests_and_metadata_invalidation_ignore_explicit_file_filter(self):
        self.commit()
        report = run(self.root, files=["artifacts/one.md"])
        request = report["review_requests"][0]
        self.assertIsNone(request["commit"])
        self.assertEqual(request["snapshot"], "working_tree")
        self.put(".repo-policy/rubrics/quality.md", "# Changed rubric\n")
        report = run(self.root, files=[])
        self.assertEqual(
            [r["artifact"] for r in report["review_requests"]],
            ["artifacts/one.md", "artifacts/two.md"],
        )
        self.assertEqual(report["files_checked"], ["artifacts/one.md", "artifacts/two.md"])

    def test_pending_reviews_do_not_override_machine_failures_or_thresholds(self):
        self.manifest["rules"] = [
            {"id": "title", "kind": "required-text", "pattern": "NOPE", "files": ["artifacts/*"]}
        ]
        self.data(".repo-policy/policy.yaml", self.manifest)
        sha = self.commit()
        report = run(self.root, commit=sha)
        self.assertEqual(report["exit_code"], 1)
        self.assertTrue(report["review_required"])
        self.assertEqual({d["rule"] for d in report["diagnostics"]}, {"title"})
        self.manifest.pop("rules")
        self.data(".repo-policy/policy.yaml", self.manifest)
        self.assertEqual(run(self.root, fail_on="info")["exit_code"], 0)

    def test_base_comparison_invalidates_rubrics_even_when_policy_files_are_excluded(self):
        self.manifest["exclude"] = [".repo-policy/*"]
        self.data(".repo-policy/policy.yaml", self.manifest)
        self.commit()
        self.git("branch", "baseline")
        self.put(".repo-policy/rubrics/quality.md", "# Changed on branch\n")
        self.commit()
        report = run(self.root, mode="changed", base="baseline")
        self.assertEqual(len(report["review_requests"]), 2)
        self.assertEqual(report["files_checked"], ["artifacts/one.md", "artifacts/two.md"])

    def test_multiple_rubric_criteria_are_grouped_in_one_request_per_artifact(self):
        other = ".repo-policy/rubrics/other.md"
        self.put(other, "# Other rubric\n")
        self.contract["criteria"].append({"id": "other", "rubric": other})
        self.data(".repo-policy/contracts/artifact-quality.yaml", self.contract)
        requests = run(self.root, files=["artifacts/one.md"])["review_requests"]
        self.assertEqual(len(requests), 2)  # New/untracked contract invalidates both artifacts.
        self.assertEqual([c["id"] for c in requests[0]["criteria"]], ["other", "quality"])

    def test_machine_only_contract_edit_rechecks_unchanged_artifacts(self):
        self.manifest["rules"] = [
            {"id": "title", "kind": "required-text", "pattern": "^# ", "files": ["artifacts/*"]}
        ]
        self.contract["criteria"] = [{"id": "title", "rule": "title"}]
        self.data(".repo-policy/policy.yaml", self.manifest)
        path = self.data(".repo-policy/contracts/artifact-quality.yaml", self.contract)
        self.put("artifacts/two.md", "No heading\n")
        self.commit()
        path.write_bytes(path.read_bytes() + b"\n")
        sha = self.commit()
        report = run(self.root, commit=sha)
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["diagnostics"][0]["file"], "artifacts/two.md")
        self.assertEqual(report["review_requests"], [])

    def test_commit_plugins_may_write_standard_cache_files(self):
        self.put(
            ".repo-policy/scripts/cache.py",
            "from pathlib import Path\n"
            "Path('.ruff_cache').mkdir(exist_ok=True)\n"
            "Path('.ruff_cache/cache').write_text('cache')\nprint('[]')\n",
        )
        self.manifest["plugins"] = [
            {
                "id": "cache",
                "format": "json",
                "files": ["artifacts/*"],
                "command": [sys.executable, ".repo-policy/scripts/cache.py", "{files}"],
            }
        ]
        self.data(".repo-policy/policy.yaml", self.manifest)
        sha = self.commit()
        self.assertEqual(run(self.root, commit=sha, allow_plugins=True)["exit_code"], 0)
        self.assertFalse((self.root / ".ruff_cache").exists())

    def test_cli_lists_each_artifact_criterion_and_rubric_and_json_schema_is_additive(self):
        sha = self.commit()
        code, output, _ = self.cli("check", "--commit", sha)
        self.assertEqual(code, 0)
        for value in ("artifacts/one.md", "artifacts/two.md", "artifact-quality", "quality.md"):
            self.assertIn(value, output)
        self.assertIn("Subagent review required", output)
        code, output, _ = self.cli("check", "--commit", sha, "--format", "json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["schema_version"], 1)

    def test_invalid_commit_selection_and_fix_attempts_return_two_without_writes(self):
        sha = self.commit()
        before = (self.root / "artifacts/one.md").read_bytes()
        for args in (
            ("check", "--commit", sha, "--changed"),
            ("check", "--commit", sha, "--all"),
            ("check", "--commit", sha, "--files", "artifacts/one.md"),
        ):
            with self.subTest(args=args), self.assertRaises(SystemExit) as raised:
                self.cli(*args)
            self.assertEqual(raised.exception.code, 2)
        for args in (
            ("fix", "--commit", sha),
            ("fix", "--commit", sha, "--dry-run"),
            ("check", "--commit", sha, "--base", "main"),
            ("check", "--commit", "missing-ref"),
        ):
            self.assertEqual(self.cli(*args)[0], 2)
        with self.assertRaises(PolicyError):
            run(self.root, commit=sha, fix=True)
        with self.assertRaises(PolicyError):
            run(self.root, commit=sha, files=[])
        self.assertEqual((self.root / "artifacts/one.md").read_bytes(), before)

    def test_local_and_af_commit_requests_and_reports_are_identical(self):
        sha = self.commit()
        output = self.root.parent / "output"
        with contextlib.redirect_stdout(io.StringIO()):
            code = af_main(
                [
                    "--root",
                    str(self.root),
                    "--commit",
                    sha,
                    "--session-root",
                    str(self.root.parent),
                    "--output-dir",
                    str(output),
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads((output / "report.json").read_text()), run(self.root, commit=sha)
        )

    def test_binary_and_unicode_paths_are_hashed_without_decoding_artifacts(self):
        name = "artifacts/изображение с пробелом.bin"
        self.put(name, b"\0\xff\r\n")
        sha = self.commit()
        request = next(
            r for r in run(self.root, commit=sha)["review_requests"] if r["artifact"] == name
        )
        self.assertEqual(request["artifact_sha256"], hashlib.sha256(b"\0\xff\r\n").hexdigest())

    def test_request_ids_change_with_revision_artifact_contract_and_rubric_bytes(self):
        self.commit()
        first = run(self.root, files=["artifacts/one.md"])["review_requests"][0]["request_id"]
        for name in (
            "artifacts/one.md",
            ".repo-policy/contracts/artifact-quality.yaml",
            ".repo-policy/rubrics/quality.md",
        ):
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
                request = run(self.root, files=["artifacts/one.md"])["review_requests"][0]
                self.assertNotEqual(request["request_id"], first)
                path.write_bytes(original)

    def test_plugins_cannot_silently_change_snapshot_or_working_copy(self):
        self.put(
            ".repo-policy/scripts/mutate.py",
            "import json\nfrom pathlib import Path\n"
            "Path('artifacts/one.md').write_text('mutated')\nprint(json.dumps([]))\n",
        )
        self.manifest["plugins"] = [
            {
                "id": "mutate",
                "format": "json",
                "files": ["artifacts/*"],
                "command": [sys.executable, ".repo-policy/scripts/mutate.py", "{files}"],
            }
        ]
        self.data(".repo-policy/policy.yaml", self.manifest)
        sha = self.commit()
        with self.assertRaisesRegex(PolicyError, "changed the committed snapshot"):
            run(self.root, commit=sha, allow_plugins=True)
        self.assertEqual((self.root / "artifacts/one.md").read_bytes(), b"# One\n")

    def test_export_attributes_do_not_remove_or_substitute_committed_artifacts(self):
        self.put(
            ".gitattributes", "artifacts/one.md export-ignore\nartifacts/two.md export-subst\n"
        )
        self.put("artifacts/two.md", "$Format:%H$\n")
        sha = self.commit()
        requests = run(self.root, commit=sha)["review_requests"]
        self.assertEqual(len(requests), 2)
        self.assertEqual(
            requests[1]["artifact_sha256"], hashlib.sha256(b"$Format:%H$\n").hexdigest()
        )

    def test_missing_local_blob_returns_execution_error_without_false_success(self):
        sha = self.commit()
        oid = self.git("rev-parse", sha + ":artifacts/one.md").decode().strip()
        (self.root / ".git/objects" / oid[:2] / oid[2:]).unlink()
        code, output, _ = self.cli("check", "--commit", sha, "--format", "json")
        self.assertEqual(code, 2)
        self.assertIn("unavailable locally", json.loads(output)["error"])

    def test_shallow_missing_parent_is_not_treated_as_initial_commit(self):
        parent = self.commit()
        self.put("artifacts/one.md", "# Next\n")
        sha = self.commit()
        (self.root / ".git/shallow").write_text(sha + "\n")
        (self.root / ".git/objects" / parent[:2] / parent[2:]).unlink()
        with self.assertRaisesRegex(PolicyError, "required Git objects must be local"):
            run(self.root, commit=sha)

    def test_merge_commit_uses_first_parent(self):
        self.commit()
        self.git("checkout", "-b", "side")
        self.put("artifacts/two.md", "# Side\n")
        self.commit()
        self.git("checkout", "main")
        self.put("artifacts/one.md", "# Main\n")
        first_parent = self.commit()
        self.git("merge", "--no-ff", "side", "-m", "merge")
        sha = self.git("rev-parse", "HEAD").decode().strip()
        report = run(self.root, commit=sha)
        self.assertEqual(report["base_commit"], first_parent)
        self.assertEqual([r["artifact"] for r in report["review_requests"]], ["artifacts/two.md"])

    @unittest.skipUnless(os.name == "posix", "symlinks require privileges on Windows")
    def test_symlink_artifact_is_skipped_without_following_target(self):
        outside = self.root.parent / "outside"
        outside.write_bytes(b"must not read")
        (self.root / "artifacts/link.md").symlink_to(outside)
        sha = self.commit()
        report = run(self.root, commit=sha)
        self.assertIn({"file": "artifacts/link.md", "reason": "symlink"}, report["skipped"])
        self.assertNotIn("artifacts/link.md", [r["artifact"] for r in report["review_requests"]])


if __name__ == "__main__":
    unittest.main()
