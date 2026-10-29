import contextlib
import io
import json
import os
import stat
import sys
import unittest
from unittest.mock import patch

from skill_fixtures import SkillFixture, load_helper

from repo_policy import __version__
from repo_policy.engine import run


class SetupFeedbackTests(SkillFixture):
    def setUp(self):
        super().setUp()
        self.helper = load_helper()
        self.engine = "repository-policy-linter==" + __version__

    def test_preview_distinguishes_source_syntax_from_unperformed_verification(self):
        self.put("README.md", "Existing\n")
        sources = {
            "registry": "repository-policy-linter==99.98.97",
            "https_wheel": "repository-policy-linter @ https://example.invalid/no.whl#sha256="
            + "a" * 64,
            "local_wheel": "repository-policy-linter @ file:///missing/no.whl#sha256=" + "a" * 64,
        }
        before = self.snapshot()
        for kind, requirement in sources.items():
            with self.subTest(kind=kind):
                report = self.helper.configure(self.root, requirement)
                self.assertEqual(report["source_kind"], kind)
                self.assertEqual(
                    report["verification"],
                    {"availability": "not_verified", "cold_install": "not_run", "ci": "not_run"},
                )
                self.assertEqual(report["portable_source"], kind != "local_wheel")
                self.assertFalse(report["applied"])
                self.assertEqual(report["completed_writes"], [])
                self.assertEqual(self.snapshot(), before)

    def test_append_preserves_dirty_bytes_line_endings_mode_index_and_unrelated_files(self):
        original = b"\xef\xbb\xbf# Existing instructions\r\nKeep these.\r\n\r\n\r\n"
        agents = self.put("AGENTS.md", original)
        self.put("README.md", "Original\n")
        self.put(".github/workflows/custom.yml", "jobs: &jobs {}\ncopy: *jobs\n")
        self.commit()
        self.put("README.md", "Staged user edit\n")
        self.git("add", "README.md")
        self.put("README.md", "Unstaged user edit\n")
        self.put("raw/input.bin", b"\xff\xfe\0untracked raw")
        if os.name == "posix":
            agents.chmod(0o640)
            (self.root / "CLAUDE.md").symlink_to("AGENTS.md")
        before, index = self.snapshot(), (self.root / ".git/index").read_bytes()
        mode = stat.S_IMODE(agents.stat().st_mode)
        self.helper.configure(self.root, self.engine, instructions="AGENTS.md")
        self.assertEqual(self.snapshot(), before)
        applied = self.helper.configure(self.root, self.engine, True, "AGENTS.md")
        self.assertTrue(applied["applied"])
        self.assertEqual(applied["reconciliation_required"], [])
        self.assertTrue(agents.read_bytes().startswith(original))
        self.assertNotIn(b"\n", agents.read_bytes()[len(original) :].replace(b"\r\n", b""))
        self.assertEqual(stat.S_IMODE(agents.stat().st_mode), mode)
        after = self.snapshot()
        for name, value in before.items():
            if name != "AGENTS.md":
                self.assertEqual(after[name], value, name)
        self.assertEqual((self.root / ".git/index").read_bytes(), index)
        again = self.helper.configure(self.root, self.engine, True, "AGENTS.md")
        self.assertEqual(again["completed_writes"], [])
        self.assertEqual(again["reconciliation_required"], [])
        self.assertEqual(self.snapshot(), after)
        self.assertEqual((self.root / ".git/index").read_bytes(), index)

    def test_preserved_differences_are_explicit_for_bundle_dependency_and_managed_block(self):
        self.put(
            ".repo-policy/policy.yaml", b"version: 2\r\n# Accepted custom policy\r\nrules: []\r\n"
        )
        self.put(".repo-policy/requirements.txt", "repository-policy-linter==0.1.0\n")
        self.put(
            "AGENTS.md",
            "Before\n<!-- repo-policy:begin -->\nCustom approved guidance\n<!-- repo-policy:end -->\nAfter\n",
        )
        before = self.snapshot()
        report = self.helper.configure(self.root, self.engine, True, "AGENTS.md", True)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(
            set(report["reconciliation_required"]),
            {".repo-policy/policy.yaml", ".repo-policy/requirements.txt", "AGENTS.md"},
        )
        self.assertEqual(report["completed_writes"], [])
        self.assertTrue(all(not action["matches"] for action in report["actions"]))
        self.assertFalse((self.root / ".repo-policy/checks/common.yaml").exists())

    def test_byte_comparison_does_not_hide_crlf_dependency_drift(self):
        self.helper.configure(self.root, self.engine, True)
        requirement = self.put(".repo-policy/requirements.txt", (self.engine + "\r\n").encode())
        before = requirement.read_bytes()
        report = self.helper.configure(self.root, self.engine, True)
        self.assertIn(".repo-policy/requirements.txt", report["reconciliation_required"])
        self.assertEqual(requirement.read_bytes(), before)

    def test_rubric_delivery_is_opt_in_and_neither_mode_creates_review_contracts(self):
        self.put("README.md", "Pilot\n")
        first = self.helper.configure(self.root, self.engine, True, "AGENTS.md")
        default = (self.root / "AGENTS.md").read_bytes()
        self.assertFalse(first["rubric_handoff"])
        self.assertEqual(run(self.root)["review_requests"], [])
        request = self.helper.configure(self.root, self.engine, True, "AGENTS.md", True)
        self.assertIn("AGENTS.md", request["reconciliation_required"])
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), default)
        full = self.helper.configure(self.root, self.engine, True, "CLAUDE.md", True)
        self.assertTrue(full["rubric_handoff"])
        self.assertNotEqual((self.root / "CLAUDE.md").read_bytes(), default)
        self.assertEqual(run(self.root)["review_requests"], [])
        with self.assertRaisesRegex(ValueError, "requires --instructions"):
            self.helper.configure(self.root, self.engine, rubric_handoff=True)

    def test_known_denied_destination_blocks_all_writes_and_preview_reports_it(self):
        agents = self.put("AGENTS.md", "User instructions\n")
        before = self.snapshot()
        real_access = self.helper.os.access

        def access(path, mode):
            return False if path == agents else real_access(path, mode)

        with patch.object(self.helper.os, "access", side_effect=access):
            preview = self.helper.configure(self.root, self.engine, instructions="AGENTS.md")
            self.assertEqual(preview["write_preflight"]["status"], "blocked")
            with self.assertRaises(self.helper.SetupError) as error:
                self.helper.configure(self.root, self.engine, True, "AGENTS.md")
        self.assertEqual(error.exception.report["completed_writes"], [])
        self.assertEqual(self.snapshot(), before)

    def test_partial_io_failure_has_json_exit_2_and_never_claims_rollback(self):
        actual_write = self.helper.write_file

        def interrupted(path, content, original):
            if path.name == "policy.yaml":
                raise OSError("SECRET source data must not be rendered")
            return actual_write(path, content, original)

        output, errors = io.StringIO(), io.StringIO()
        args = ["configure.py", "--root", str(self.root), "--engine", self.engine, "--apply"]
        with (
            patch.object(self.helper, "write_file", side_effect=interrupted),
            patch.object(sys, "argv", args),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(errors),
            self.assertRaises(SystemExit) as exit_result,
        ):
            self.helper.main()
        self.assertEqual(exit_result.exception.code, 2)
        report = json.loads(output.getvalue())
        self.assertFalse(report["applied"])
        self.assertEqual(report["completed_writes"], [".repo-policy/checks/common.yaml"])
        self.assertEqual(report["uncertain_write"], ".repo-policy/policy.yaml")
        self.assertIn(".repo-policy/requirements.txt", report["remaining_writes"])
        self.assertTrue((self.root / ".repo-policy/checks/common.yaml").is_file())
        self.assertFalse((self.root / ".repo-policy/requirements.txt").exists())
        self.assertNotIn("SECRET", output.getvalue() + errors.getvalue())
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "no manifest"):
            self.helper.configure(self.root, self.engine, True)
        self.assertEqual(self.snapshot(), before)

    def test_concurrent_instruction_edit_is_not_overwritten(self):
        agents = self.put("AGENTS.md", "Initial\n")
        actual_write = self.helper.write_file

        def edit_before_append(path, content, original):
            if path == agents:
                agents.write_bytes(b"Concurrent user work\n")
            actual_write(path, content, original)

        with patch.object(self.helper, "write_file", side_effect=edit_before_append):
            with self.assertRaises(self.helper.SetupError) as error:
                self.helper.configure(self.root, self.engine, True, "AGENTS.md")
        self.assertEqual(agents.read_bytes(), b"Concurrent user work\n")
        self.assertEqual(error.exception.report["uncertain_write"], "AGENTS.md")

    def test_invalid_instruction_bytes_or_markers_fail_before_scaffolding(self):
        for data in [b"\xffsecret", b"<!-- repo-policy:begin -->", b"<!-- repo-policy:end -->"]:
            with self.subTest(data=data):
                self.put("AGENTS.md", data)
                before = self.snapshot()
                with self.assertRaises(ValueError):
                    self.helper.configure(self.root, self.engine, True, "AGENTS.md")
                self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
