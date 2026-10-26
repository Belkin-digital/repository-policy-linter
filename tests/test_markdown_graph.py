import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from repo_policy.af import main as af_main
from repo_policy.cli import main
from repo_policy.engine import run
from repo_policy.model import PolicyError


class MarkdownGraphTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repo"
        self.root.mkdir()
        self.config()
        self.put("AGENTS.md", "# Entry\n")

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
        return path

    def config(self, roots=None, **options):
        extra = options.pop("config_options", {})
        rule = {
            "id": "navigation",
            "kind": "markdown-reachable",
            "files": ["**/*.md"],
            "roots": ["AGENTS.md"] if roots is None else roots,
            **options,
        }
        self.put(
            ".repo-policy/policy.yaml", yaml.safe_dump({"version": 2, "rules": [rule], **extra})
        )

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args], check=True, capture_output=True
        ).stdout

    def commit(self):
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "tests@example.invalid")
        self.git("add", ".")
        self.git("-c", "core.hooksPath=/dev/null", "commit", "-m", "fixture")

    def orphans(self, **kwargs):
        return [d["file"] for d in run(self.root, **kwargs)["diagnostics"]]

    def test_multihop_and_disconnected_cycles(self):
        self.put("AGENTS.md", "[Index](docs/index.md)\n")
        self.put("docs/index.md", "[Page](page.md)\n")
        self.put("docs/page.md", "[Back](index.md)\n")
        self.put("a.md", "[B](b.md)\n")
        self.put("b.md", "[A](a.md)\n")
        self.assertEqual(self.orphans(), ["a.md", "b.md"])
        self.assertEqual(run(self.root), run(self.root))

    def test_commonmark_links_references_tables_and_encoded_paths(self):
        names = ["space name.md", "part(1).md", "кириллица.md", "reference.md", "table.md"]
        for name in names:
            self.put("docs/" + name, "# Page\n")
        self.put(
            "AGENTS.md",
            """[Space](docs/space%20name.md?view=1#heading)
[Balanced](docs/part(1).md)
[Unicode](docs/кириллица.md)
[Reference][]

[Reference]: docs/reference.md

| Page |
| --- |
| [Table](/docs/table.md) |
""",
        )
        self.assertEqual(self.orphans(), [])

    def test_code_metadata_comments_images_and_unused_definitions_are_not_edges(self):
        self.put("unreachable.md", "# Orphan\n")
        self.put(
            "AGENTS.md",
            """---
description: '[Metadata](unreachable.md)'
---
`[Inline](unreachable.md)`

```md
[Fenced](unreachable.md)
```

    [Indented](unreachable.md)

<!-- [Comment](unreachable.md) <a href="unreachable.md">hidden</a> -->
![[Image alternative](unreachable.md)](image.png)

[unused]: unreachable.md
""",
        )
        self.assertEqual(self.orphans(), ["unreachable.md"])
        self.put("AGENTS.md", "---\ninvalid: '[Metadata](unreachable.md)'\n")
        self.assertEqual(self.orphans(), ["unreachable.md"])

    def test_html_links_and_directory_readme(self):
        self.put("AGENTS.md", '<a href="docs/?q=1&amp;x=2">Docs</a>\n')
        self.put("docs/README.md", '<a href="page.md#heading">Page</a>\n')
        self.put("docs/page.md", "# Page\n")
        self.assertEqual(self.orphans(), [])

    def test_html_code_blocks_do_not_supply_edges(self):
        self.put("orphan.md", "# Orphan\n")
        for html in (
            '<pre><a href="orphan.md">Code</a></pre>',
            '<code><code>x</code><a href="orphan.md">Code</a></code>',
            '<script><a href="orphan.md">Script</a></script>',
            '<style><a href="orphan.md">Style</a></style>',
            "<code>[Code](orphan.md)</code>",
        ):
            with self.subTest(html=html):
                self.put("AGENTS.md", html + "\n")
                self.assertEqual(self.orphans(), ["orphan.md"])

    def test_explicit_installed_skill_root_and_no_implicit_skill_discovery(self):
        skill = ".agents/skills/chosen/SKILL.md"
        self.config(roots=["AGENTS.md", skill])
        self.put(skill, "[Instructions](references/integration.md)\n")
        self.put(".agents/skills/chosen/references/integration.md", "# Instructions\n")
        self.put(".claude/skills/unselected/SKILL.md", "# Not a root\n")
        self.assertEqual(self.orphans(), [".claude/skills/unselected/SKILL.md"])

    def test_missing_excluded_and_symlink_roots_fail_closed(self):
        self.config(roots=["AGENTS.md", "missing.md"])
        report = run(self.root)
        self.assertEqual(report["exit_code"], 1)
        self.assertIn("root is missing", report["diagnostics"][0]["message"])
        self.config(config_options={"exclude": ["AGENTS.md"]})
        self.assertEqual(self.orphans(), ["AGENTS.md"])
        self.config()
        (self.root / "AGENTS.md").unlink()
        outside = self.root.parent / "outside.md"
        outside.write_text("[Outside](secret.md)\n")
        try:
            (self.root / "AGENTS.md").symlink_to(outside)
        except OSError:
            self.skipTest("symlinks unavailable")
        self.assertEqual(self.orphans(), ["AGENTS.md"])

    def test_invalid_roots_are_configuration_errors(self):
        for roots in (
            [],
            ["../a.md"],
            ["/a.md"],
            ["**/*.md"],
            ["a.txt"],
            ["AGENTS.md", "AGENTS.md"],
            ["./AGENTS.md"],
            "AGENTS.md",
        ):
            with self.subTest(roots=roots):
                self.config(roots=roots)
                with self.assertRaises(PolicyError):
                    run(self.root)

    def test_rule_exclusions_and_exceptions_preserve_transit_nodes(self):
        self.put("AGENTS.md", "[Bridge](bridge.md)\n")
        self.put("bridge.md", "[Target](docs/target.md)\n")
        self.put("docs/target.md", "# Target\n")
        self.put("allowed.md", "# Allowed\n")
        self.put("docs/orphan.md", "# Orphan\n")
        self.config(
            exclude=["bridge.md"],
            config_options={
                "exceptions": [{"rule": "navigation", "files": ["allowed.md"], "reason": "Fixture"}]
            },
        )
        self.assertEqual(self.orphans(), ["docs/orphan.md"])
        self.config(files=["docs/*.md"], config_options={"exclude": ["bridge.md"]})
        self.assertEqual(self.orphans(), ["docs/orphan.md", "docs/target.md"])

    def test_external_urls_and_escaping_paths_never_make_local_edges(self):
        self.put("orphan.md", "# Orphan\n")
        self.put(
            "AGENTS.md",
            """[HTTPS](https://example.invalid/orphan.md)
[Protocol relative](//example.invalid/orphan.md)
[File](file:///orphan.md)
[Outside](../orphan.md)
[Encoded outside](%2e%2e/orphan.md)
[Anchor](#orphan.md)
[Double encoded](%256frphan.md)
""",
        )
        self.assertEqual(self.orphans(), ["orphan.md"])

    def test_changed_and_explicit_selection_detect_unchanged_orphan(self):
        self.put("AGENTS.md", "[Page](docs/page.md)\n")
        self.put("docs/page.md", "# Unchanged\n")
        self.commit()
        self.put("AGENTS.md", "# Link removed\n")
        for options in ({"mode": "changed"}, {"files": ["AGENTS.md"]}):
            with self.subTest(options=options):
                report = run(self.root, **options)
                self.assertEqual(report["files_checked"], ["AGENTS.md"])
                self.assertEqual(report["diagnostics"][0]["file"], "docs/page.md")
                self.assertIn("docs/page.md", report["repository_checks"][0]["files_checked"])

    def test_deletion_only_selection_detects_disconnected_descendant(self):
        self.put("AGENTS.md", "[Bridge](bridge.md)\n")
        self.put("bridge.md", "[Leaf](leaf.md)\n")
        self.put("leaf.md", "# Leaf\n")
        self.commit()
        (self.root / "bridge.md").unlink()
        report = run(self.root, mode="changed")
        self.assertEqual(report["files_checked"], [])
        self.assertEqual(report["diagnostics"][0]["file"], "leaf.md")
        self.assertEqual(report["exit_code"], 1)

    def test_graph_input_is_bounded_utf8_and_no_partial_success(self):
        for content, extra in ((b"\xff", {}), (b"nul\0", {}), ("x" * 101, {"max_file_bytes": 100})):
            with self.subTest(content=content):
                self.config(config_options=extra)
                self.put("orphan.md", content)
                with self.assertRaises(PolicyError):
                    run(self.root, files=["AGENTS.md"])

    def test_missing_optional_dependency_is_actionable_and_old_policies_work(self):
        with patch.dict("sys.modules", {"markdown_it": None}):
            with self.assertRaisesRegex(PolicyError, r"repository-policy-linter\[markdown\]"):
                run(self.root)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["check", "--root", str(self.root), "--format", "json"])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output.getvalue())["exit_code"], 2)
            self.put(".repo-policy/policy.yaml", "version: 2\nrules: []\n")
            report = run(self.root)
            self.assertEqual(report["exit_code"], 0)
            self.assertNotIn("repository_checks", report)

    def test_fix_does_not_invent_navigation_and_diagnostics_contract_is_compatible(self):
        page = self.put("orphan.md", b"# Orphan\r\n")
        report = run(self.root, fix=True)
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["fixed"], [])
        self.assertEqual(page.read_bytes(), b"# Orphan\r\n")
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(
            report["diagnostics"],
            [
                {
                    "file": "orphan.md",
                    "line": 1,
                    "column": 1,
                    "rule": "navigation",
                    "severity": "error",
                    "message": "Markdown file is unreachable from configured roots",
                    "fixable": False,
                }
            ],
        )

    def test_af_report_is_identical_to_local_graph_report(self):
        self.put("orphan.md", "# Orphan\n")
        output = self.root.parent / "output"
        with contextlib.redirect_stdout(io.StringIO()):
            code = af_main(
                [
                    "--root",
                    str(self.root),
                    "--all",
                    "--session-root",
                    str(self.root.parent),
                    "--output-dir",
                    str(output),
                ]
            )
        self.assertEqual(code, 1)
        self.assertEqual(json.loads((output / "report.json").read_text()), run(self.root))

    def test_uppercase_and_markdown_suffix_are_graph_nodes(self):
        self.config(files=["**/*"])
        self.put("AGENTS.md", "[Upper](UPPER.MD) [Long](long.markdown)\n")
        self.put("UPPER.MD", "# Upper\n")
        self.put("long.markdown", "# Long\n")
        self.assertEqual(self.orphans(), [])


if __name__ == "__main__":
    unittest.main()
