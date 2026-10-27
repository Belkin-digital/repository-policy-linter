import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from repo_policy.engine import run
from repo_policy.model import PolicyError


class GitContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        self.root = self.directory / "repo"
        self.root.mkdir()
        self.output = self.directory / "observed.json"
        self.git("init", "-q")
        self.write("item.md", "original\n")
        self.write(".gitignore", "ignored/\n__pycache__/\n")
        self.write(
            "inspect.py",
            "import json,sys\nfrom pathlib import Path\nc=json.loads(Path(sys.argv[1]).read_text())\nPath("
            + repr(str(self.output))
            + ').write_text(json.dumps(c))\nprint("[]")\n',
        )
        plugin = dict(
            id="history",
            scope="repository",
            context="git",
            command=[sys.executable, "inspect.py", "{context}", "{files}"],
            format="json",
            files=["**"],
        )
        self.write(
            ".repo-policy/checks/history.yaml", yaml.safe_dump(dict(version=2, plugins=[plugin]))
        )
        self.write(
            ".repo-policy/policy.yaml",
            "version: 2\nregistries: [.repo-policy/checks/history.yaml]\nchecks: [history]\ncontracts: []\nexclude: [ignored/**]\n",
        )
        self.commit("Initial")

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def git(self, *args):
        return subprocess.run(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "commit.gpgsign=false",
                "-C",
                str(self.root),
                *args,
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def commit(self, message):
        self.git("add", "-A")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@localhost",
            "commit",
            "-qm",
            message,
        )
        return self.git("rev-parse", "HEAD")

    def inspect(self, **kwargs):
        report = run(self.root, allow_plugins=True, **kwargs)
        return report, json.loads(self.output.read_text())

    def test_exact_revision_and_baseline_without_git_in_commit(self):
        old = self.git("rev-parse", "HEAD")
        self.write("item.md", "new\n")
        new = self.commit("Update")
        report, ctx = self.inspect(commit=new)
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(ctx["baseline_commit"]["sha"], old)
        self.assertEqual(ctx["current_commit"]["sha"], new)
        self.assertNotEqual(ctx["baseline_commit"]["tree"], ctx["current_commit"]["tree"])
        self.assertFalse(Path(ctx["current_root"]).exists())
        self.assertEqual(
            next(x for x in ctx["changes"] if x["path"] == "item.md")["status"], "modified"
        )

    def test_staged_worktree_and_commit_have_equal_changes_including_rename_delete(self):
        self.write("other.md", "will be deleted\n")
        self.commit("Second")
        (self.root / "item.md").rename(self.root / "renamed.md")
        (self.root / "other.md").unlink()
        self.git("add", "-A")
        _, working = self.inspect(mode="changed")
        commit = self.commit("Third")
        _, frozen = self.inspect(commit=commit)
        self.assertEqual(working["changes"], frozen["changes"])

    def test_untracked_only_change_uses_head_and_empty_changed_still_runs(self):
        head = self.git("rev-parse", "HEAD")
        self.write("new.md", "New\n")
        _, ctx = self.inspect(mode="changed")
        self.assertEqual(ctx["baseline_commit"]["sha"], head)
        self.assertFalse(ctx["after"]["new.md"]["versioned"])
        self.commit("Add")
        report, _ = self.inspect(mode="changed")
        self.assertEqual(report["files_checked"], [])
        self.assertTrue(any(x["kind"] == "git-context" for x in report["repository_checks"]))

    def test_staged_removal_with_kept_bytes_is_deletion(self):
        self.git("rm", "--cached", "item.md")
        self.assertTrue((self.root / "item.md").exists())
        _, ctx = self.inspect()
        self.assertNotIn("item.md", ctx["after"])
        self.assertEqual(
            next(x for x in ctx["changes"] if x["path"] == "item.md")["status"], "deleted"
        )

    def test_global_exclusions_do_not_hide_tracked_protected_paths(self):
        self.write("ignored/secret.json", "opaque secret\n")
        self.git("add", "-f", "ignored/secret.json")
        report, ctx = self.inspect()
        self.assertNotIn("ignored/secret.json", report["files_checked"])
        self.assertTrue(ctx["after"]["ignored/secret.json"]["versioned"])

    def test_symlink_is_hashed_without_following_target(self):
        target = self.directory / "outside"
        target.write_text("secret")
        (self.root / "link").symlink_to(target)
        _, ctx = self.inspect()
        self.assertEqual(ctx["after"]["link"]["kind"], "symlink")
        self.assertNotEqual(ctx["after"]["link"]["size"], target.stat().st_size)

    def test_gitlink_pointer_change_is_visible_without_opening_a_submodule(self):
        first = self.git("rev-parse", "HEAD")
        (self.root / "module").mkdir()
        self.git("update-index", "--add", "--cacheinfo", "160000," + first + ",module")
        second = self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@localhost",
            "commit",
            "-qm",
            "Gitlink",
        )
        second = self.git("rev-parse", "HEAD")
        self.git("update-index", "--cacheinfo", "160000," + second + ",module")
        _, context = self.inspect()
        change = next(item for item in context["changes"] if item["path"] == "module")
        self.assertEqual(change["before"]["git_oid"], first)
        self.assertEqual(change["after"]["git_oid"], second)

    def test_initial_commit_and_unborn_repository_are_explicit(self):
        _, ctx = self.inspect(commit="HEAD")
        self.assertEqual(ctx["comparison"], "initial")
        self.assertIsNone(ctx["baseline_root"])
        self.assertEqual(ctx["before"], {})
        self.git("update-ref", "-d", "HEAD")
        _, ctx = self.inspect()
        self.assertIsNone(ctx["current_commit"])

    def test_missing_history_is_error_not_initial_commit(self):
        self.write("item.md", "new")
        self.commit("Second")
        clone = self.directory / "shallow"
        subprocess.run(
            ["git", "clone", "-q", "--no-local", "--depth=1", str(self.root), str(clone)],
            check=True,
        )
        with self.assertRaises(PolicyError):
            run(clone, commit="HEAD", allow_plugins=True)

    def test_two_commit_depth_is_sufficient_for_two_tree_comparison(self):
        self.write("item.md", "second")
        self.commit("Second")
        self.write("item.md", "third")
        self.commit("Third")
        clone = self.directory / "shallow"
        subprocess.run(
            ["git", "clone", "-q", "--no-local", "--depth=2", str(self.root), str(clone)],
            check=True,
        )
        self.assertEqual(run(clone, commit="HEAD", allow_plugins=True)["exit_code"], 0)

    def test_non_git_root_fails(self):
        import shutil

        shutil.rmtree(self.root / ".git")
        with self.assertRaises(PolicyError):
            self.inspect()

    def test_mutation_of_baseline_current_or_context_fails(self):
        for target in ("current", "baseline", "context"):
            with self.subTest(target=target):
                program = "import json,sys\nfrom pathlib import Path\np=Path(sys.argv[1]);c=json.loads(p.read_text())\n"
                if target == "context":
                    program += 'p.chmod(0o600);p.write_text("{}")\n'
                else:
                    program += '(Path(c["' + target + '_root"])/"item.md").write_text("tampered")\n'
                program += 'print("[]")\n'
                self.write("inspect.py", program)
                with self.assertRaises(PolicyError):
                    run(self.root, allow_plugins=True)
                self.git("checkout", "--", "item.md", "inspect.py")

    def test_fix_refuses_before_any_newline_write(self):
        path = self.write("item.md", "no newline")
        with self.assertRaises(PolicyError):
            run(self.root, fix=True, allow_plugins=True)
        self.assertEqual(path.read_bytes(), b"no newline")

    def test_old_plugin_and_report_schema_work_without_context(self):
        path = self.root / ".repo-policy/checks/history.yaml"
        bundle = yaml.safe_load(path.read_text())
        plugin = bundle["plugins"][0]
        plugin.pop("context")
        plugin["command"] = [sys.executable, "-c", 'print("[]")', "{files}"]
        path.write_text(yaml.safe_dump(bundle))
        report = run(self.root, allow_plugins=True)
        self.assertEqual(report["schema_version"], 1)
        self.assertFalse(any(x["kind"] == "git-context" for x in report["repository_checks"]))

    def test_context_declaration_requires_scope_and_standalone_placeholder(self):
        path = self.root / ".repo-policy/checks/history.yaml"
        original = yaml.safe_load(path.read_text())
        for field, value in [
            ("scope", "files"),
            ("context", "unknown"),
            ("command", [sys.executable, "inspect.py", "prefix{context}", "{files}"]),
        ]:
            bundle = json.loads(json.dumps(original))
            bundle["plugins"][0][field] = value
            path.write_text(yaml.safe_dump(bundle))
            with self.assertRaises(PolicyError):
                run(self.root, allow_plugins=True)

    def input(self, value):
        path = self.directory / "caller.json"
        path.write_text(json.dumps(value))
        return path

    def test_external_context_input_and_exact_local_commit_queries(self):
        parent = self.git("rev-parse", "HEAD")
        self.write("item.md", "next")
        head = self.commit("Second")
        path = self.input(
            dict(
                context_input_version=1,
                extensions={"workflow": {"receipt": "opaque"}},
                git_queries=[
                    dict(kind="commit", commit=head),
                    dict(kind="ancestor", ancestor=parent, descendant=head),
                ],
            )
        )
        report, ctx = self.inspect(context_input=path)
        self.assertEqual(ctx["git_facts"][0]["object"]["sha"], head)
        self.assertTrue(ctx["git_facts"][1]["is_ancestor"])
        self.assertIsNotNone(
            next(x for x in report["repository_checks"] if x["kind"] == "git-context")[
                "input_sha256"
            ]
        )

    def test_author_document_cannot_supply_caller_input(self):
        path = self.write(
            "approval.json", '{"context_input_version":1,"extensions":{"approved":true}}'
        )
        with self.assertRaises(PolicyError):
            self.inspect(context_input=path)

    def test_missing_or_abbreviated_query_commit_fails_without_fetch(self):
        for sha in ("0" * 40, "abcdef"):
            path = self.input(
                dict(context_input_version=1, git_queries=[dict(kind="commit", commit=sha)])
            )
            with self.assertRaises(PolicyError):
                self.inspect(context_input=path)

    def test_context_input_invalid_duplicate_and_oversized_rejected(self):
        path = self.input({})
        for raw in ('{"context_input_version":1,"context_input_version":1}', "x" * (1_048_576 + 1)):
            path.write_text(raw)
            with self.assertRaises(PolicyError):
                self.inspect(context_input=path)

    def test_boolean_context_version_does_not_alias_version_one(self):
        path = self.input({"context_input_version": True})
        with self.assertRaises(PolicyError):
            self.inspect(context_input=path)

    def test_attributes_clean_filter_is_never_run_by_git_context(self):
        marker = self.directory / "executed"
        self.git("config", "filter.trap.clean", f"touch {marker}")
        self.write(".gitattributes", "item.md filter=trap\n")
        self.write("item.md", "changed\n")
        self.inspect()
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
