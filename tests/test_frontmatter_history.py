import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from repo_policy.af import main as af_main
from repo_policy.engine import run
from repo_policy.model import PolicyError


class FrontmatterHistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repo"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "core.autocrlf", "false")
        self.rule = {
            "id": "dates",
            "kind": "frontmatter",
            "files": ["*.md"],
            "keys": ["created", "updated"],
            "preserve_keys": ["created"],
        }
        self.config()
        self.document()

    def put(self, name, text):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text if isinstance(text, bytes) else text.encode())

    def config(self, **options):
        self.put(
            ".repo-policy/policy.yaml",
            yaml.safe_dump({"version": 2, "rules": [self.rule], **options}),
        )

    def document(self, created="2026-10-26", updated="2026-10-26", name="page.md"):
        self.put(name, f"---\ncreated: {created}\nupdated: {updated}\n---\n# Page\n")

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
            "-m",
            "fixture",
        )
        return self.git("rev-parse", "HEAD").decode().strip()

    def test_initial_metadata_and_new_file_are_allowed(self):
        self.assertEqual(run(self.root)["exit_code"], 0)
        self.commit()
        self.document(name="new.md")
        self.assertEqual(run(self.root)["exit_code"], 0)

    def test_created_cannot_change_but_updated_and_body_may(self):
        self.commit()
        self.document(updated="2026-10-27")
        self.assertEqual(run(self.root)["exit_code"], 0)
        self.document(created="2026-10-27", updated="2026-10-27")
        report = run(self.root)
        self.assertEqual(report["exit_code"], 1)
        self.assertIn("retain its previous value: created", report["diagnostics"][0]["message"])
        self.document(created="'2026-10-26'")
        self.assertEqual(run(self.root)["exit_code"], 1)  # Typed YAML values are preserved.

    def test_nested_skill_metadata_uses_same_preservation(self):
        self.rule["mapping_path"] = ["metadata"]
        self.config()
        self.put(
            "page.md", "---\nmetadata:\n  created: '2026-10-26'\n  updated: '2026-10-26'\n---\n"
        )
        self.commit()
        self.put(
            "page.md", "---\nmetadata:\n  created: '2026-10-27'\n  updated: '2026-10-27'\n---\n"
        )
        self.assertEqual(run(self.root)["exit_code"], 1)

    def test_null_value_cannot_be_removed_when_not_a_required_key(self):
        self.rule["keys"] = []
        self.config()
        self.put("page.md", "---\ncreated: null\n---\n")
        self.commit()
        self.put("page.md", "---\nupdated: '2026-10-27'\n---\n")
        self.assertEqual(run(self.root)["exit_code"], 1)

    def test_existing_file_without_metadata_can_be_initialized(self):
        self.put("page.md", "# Before metadata\n")
        self.commit()
        self.document()
        self.assertEqual(run(self.root)["exit_code"], 0)

    def test_exact_commit_ignores_dirty_working_metadata(self):
        self.commit()
        self.document(created="2026-10-27")
        sha = self.commit()
        self.document()
        self.assertEqual(run(self.root, commit=sha)["exit_code"], 1)
        self.document(created="2026-10-27")
        self.assertEqual(run(self.root)["exit_code"], 1)  # Clean HEAD vs its first parent.

    def test_invalid_or_oversized_baseline_fails_closed(self):
        for old in (
            b"---\ncreated: [\n---\n",
            b"---\ncreated: a\ncreated: b\n---\n",
            b"---\ncreated: &a value\nother: *a\n---\n",
            b"---\ncreated: \xff\n---\n",
        ):
            with self.subTest(old=old):
                self.put("page.md", old)
                self.commit()
                self.document()
                with self.assertRaisesRegex(PolicyError, "frontmatter baseline"):
                    run(self.root)
        self.put("page.md", "---\ncreated: 2026-10-26\n---\n" + "x" * 128)
        self.commit()
        self.document()
        self.config(max_file_bytes=64)
        with self.assertRaisesRegex(PolicyError, "baseline exceeds max_file_bytes"):
            run(self.root)

    def test_absent_option_preserves_non_git_behavior(self):
        self.git("rev-parse", "--git-dir")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / ".repo-policy").mkdir()
            (root / "page.md").write_bytes((self.root / "page.md").read_bytes())
            self.rule.pop("preserve_keys")
            (root / ".repo-policy/policy.yaml").write_text(
                yaml.safe_dump({"version": 2, "rules": [self.rule]})
            )
            self.assertEqual(run(root)["exit_code"], 0)
            self.rule["preserve_keys"] = ["created"]
            (root / ".repo-policy/policy.yaml").write_text(
                yaml.safe_dump({"version": 2, "rules": [self.rule]})
            )
            with self.assertRaises(PolicyError):
                run(root)

    def test_local_af_commit_reports_match(self):
        self.commit()
        self.document(created="2026-10-27")
        sha = self.commit()
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
                    "--commit",
                    sha,
                ]
            )
        self.assertEqual(code, 1)
        self.assertEqual(
            json.loads((output / "report.json").read_text()), run(self.root, commit=sha)
        )

    def test_invalid_preservation_schema_is_rejected(self):
        for keys in (None, "created", ["created", "created"], [42], [""]):
            with self.subTest(keys=keys):
                self.rule["preserve_keys"] = keys
                self.config()
                with self.assertRaises(PolicyError):
                    run(self.root)
