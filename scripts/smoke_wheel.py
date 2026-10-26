#!/usr/bin/env python3
"""Install the wheel and its dependency into a fresh non-editable environment."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def main():
    project = Path(__file__).resolve().parents[1]
    wheels = sorted((project / "dist").glob("repository_policy_linter-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("build exactly one release wheel first")
    wheel = wheels[0]
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary).resolve()
        environment = directory / "env"
        venv.EnvBuilder(with_pip=False).create(environment)
        binary = environment / ("Scripts" if os.name == "nt" else "bin")
        python = binary / ("python.exe" if os.name == "nt" else "python")
        command = binary / ("repo-policy.exe" if os.name == "nt" else "repo-policy")
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
        subprocess.run(
            ["uv", "pip", "install", "--python", str(python), str(wheel)],
            env=env,
            check=True,
        )
        fixture = directory / "repo"
        fixture.mkdir()
        (fixture / "README.md").write_text("fixture without newline", encoding="utf-8")
        subprocess.run([str(command), "init"], cwd=fixture, env=env, check=True)
        result = subprocess.run(
            [str(command), "check", "--all", "--format", "json"],
            cwd=fixture,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, result.stderr
        assert json.loads(result.stdout)["diagnostics"][0]["rule"] == "text-newline"
        subprocess.run([str(command), "fix", "--all"], cwd=fixture, env=env, check=True)
        subprocess.run(
            [str(python), "-m", "repo_policy", "check", "--all"], cwd=fixture, env=env, check=True
        )
        location = subprocess.check_output(
            [str(python), "-c", "import repo_policy; print(repo_policy.__file__)"],
            cwd=fixture,
            env=env,
            text=True,
        ).strip()
        assert Path(location).is_relative_to(environment), location
        # The distributed package must understand nested frontmatter policies too.
        (fixture / ".repo-policy/policy.yaml").write_text(
            "version: 2\nregistries: [.repo-policy/checks/common.yaml]\nrules:\n  - id: skill-dates\n    kind: frontmatter\n"
            "    files: ['SKILL.md']\n    mapping_path: [metadata]\n"
            "    keys: [created, updated]\n",
            encoding="utf-8",
        )
        dates = fixture / "SKILL.md"
        dates.write_text(
            "---\nname: packaged-test\ndescription: Test nested dates\nmetadata:\n"
            "  created: '2026-10-26'\n  updated: '2026-10-26'\n---\nBody\n",
            encoding="utf-8",
        )
        subprocess.run([str(command), "check", "--all"], cwd=fixture, env=env, check=True)
        dates.write_text(dates.read_text().replace("  updated: '2026-10-26'\n", ""))
        result = subprocess.run(
            [str(command), "check", "--all", "--format", "json"],
            cwd=fixture,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, result.stderr
        assert json.loads(result.stdout)["diagnostics"][0]["rule"] == "skill-dates"
        print("Installed wheel enforces nested frontmatter dates.")
        # A base install stays lightweight; the graph dependency is explicit.
        (fixture / ".repo-policy/policy.yaml").write_text(
            "version: 2\nregistries: [.repo-policy/checks/common.yaml]\nrules:\n  - id: navigation\n    kind: markdown-reachable\n"
            "    files: ['**/*.md']\n    roots: [AGENTS.md]\n",
            encoding="utf-8",
        )
        (fixture / "AGENTS.md").write_text(
            "[Overview](README.md) [Skill](SKILL.md)\n", encoding="utf-8"
        )
        result = subprocess.run(
            [str(command), "check", "--all", "--format", "json"],
            cwd=fixture,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2, result.stderr
        assert "[markdown]" in json.loads(result.stdout)["error"]
        subprocess.run(
            ["uv", "pip", "install", "--python", str(python), str(wheel) + "[markdown]"],
            env=env,
            check=True,
        )
        subprocess.run([str(command), "check", "--all"], cwd=fixture, env=env, check=True)
        orphan = fixture / "orphan.md"
        orphan.write_bytes(b"# Disconnected\r\n")
        result = subprocess.run(
            [str(command), "fix", "--all", "--format", "json"],
            cwd=fixture,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, result.stderr
        graph = json.loads(result.stdout)
        assert graph["repository_checks"][0]["unreachable"] == ["orphan.md"]
        assert graph["fixed"] == []
        assert orphan.read_bytes() == b"# Disconnected\r\n"
        print("Optional Markdown extra enforces graph policies without invented link fixes.")
        # Contract/ID navigation must work in the actual installed distribution too.
        policy_dir = fixture / ".repo-policy"
        (policy_dir / "contracts").mkdir()
        (policy_dir / "readme").mkdir()
        contract_path = policy_dir / "contracts/installed-document.yaml"
        contract_text = (
            "contract_version: 1\nid: installed-document\nfiles: [SKILL.md]\n"
            "entrypoints: [AGENTS.md]\ncriteria:\n"
            "  - id: metadata\n    rule: installed-metadata\n"
        )
        contract_path.write_text(contract_text)
        (policy_dir / "readme/installed-document.md").write_text("# Installed contract\n")
        (fixture / "AGENTS.md").write_text(
            "---\nrepo_policy_root: .repo-policy\n"
            "repo_policy_contracts: [installed-document]\n---\n# Navigation\n"
        )
        (policy_dir / "policy.yaml").write_text(
            "version: 2\nregistries: [.repo-policy/checks/common.yaml]\n"
            "contracts: [.repo-policy/contracts/installed-document.yaml]\nrules:\n"
            "  - id: installed-metadata\n    kind: frontmatter\n"
            "    files: [SKILL.md]\n    keys: [name, description]\n"
        )
        result = subprocess.run(
            [str(command), "check", "--all", "--format", "json"],
            cwd=fixture,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        assert json.loads(result.stdout)["contracts"][0]["status"] == "satisfied"
        result = subprocess.run(
            [str(command), "explain", "installed-document"],
            cwd=fixture,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        assert json.loads(result.stdout)["explanation_path"].endswith("installed-document.md")
        contract_path.write_text(
            contract_text.replace("id: installed-document", "id: installed-metadata")
        )
        result = subprocess.run(
            [str(command), "check", "--all", "--format", "json"],
            cwd=fixture,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2, result.stderr
        assert "system-unique-ids" in json.loads(result.stdout)["error"]
        print("Installed wheel enforces contract acceptance, ID navigation and system uniqueness.")
        # Exercise immutable review requests in the installed wheel, not source imports.
        (policy_dir / "rubrics").mkdir()
        rubric = policy_dir / "rubrics/installed-quality.md"
        rubric.write_text("# Quality\nExplain the setup steps completely.\n")
        contract_path.write_text(
            contract_text + "  - id: quality\n"
            "    rubric: .repo-policy/rubrics/installed-quality.md\n"
        )
        subprocess.run(
            ["git", "init", "-b", "main", str(fixture)], check=True, capture_output=True, env=env
        )
        subprocess.run(
            ["git", "-C", str(fixture), "config", "core.autocrlf", "false"], check=True, env=env
        )

        def fixture_commit():
            subprocess.run(["git", "-C", str(fixture), "add", "."], check=True, env=env)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(fixture),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=tests@example.invalid",
                    "-c",
                    "commit.gpgsign=false",
                    "-c",
                    "core.hooksPath=/dev/null",
                    "commit",
                    "-m",
                    "fixture",
                ],
                check=True,
                capture_output=True,
                env=env,
            )
            return subprocess.check_output(
                ["git", "-C", str(fixture), "rev-parse", "HEAD"], text=True, env=env
            ).strip()

        fixture_commit()
        rubric.write_text(rubric.read_text() + "Include a concrete example.\n")
        sha = fixture_commit()
        committed_hash = hashlib.sha256(dates.read_bytes()).hexdigest()
        dates.write_text("Uncommitted content that fails frontmatter\n")
        result = subprocess.run(
            [str(command), "check", "--commit", sha, "--format", "json"],
            cwd=fixture,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        review = json.loads(result.stdout)
        assert review["review_required"] and review["exit_code"] == 0
        assert review["review_requests"][0]["artifact_sha256"] == committed_hash
        assert review["review_requests"][0]["commit"] == sha
        assert "SKILL.md" not in review["changed_files"]
        print("Installed wheel checks exact commits and queues reviews after rubric-only changes.")
        # Exercise the distribution path: install skill -> configure target twice ->
        # install external requirement -> run linter, without copying engine sources.
        installed_skill = directory / "skills/repo-policy-setup"
        subprocess.run(
            [
                sys.executable,
                str(project / "scripts/install_skill.py"),
                "--destination",
                str(installed_skill),
            ],
            env=env,
            check=True,
        )
        target = directory / "skill-target"
        target.mkdir()
        subprocess.run(["git", "init", "-b", "main", str(target)], check=True, capture_output=True)
        (target / "README.md").write_text("Pilot\n", encoding="utf-8")
        (target / "AGENTS.md").write_text("Existing rules.\n", encoding="utf-8")
        requirement = (
            "repository-policy-linter[markdown] @ "
            + wheel.as_uri()
            + "#sha256="
            + hashlib.sha256(wheel.read_bytes()).hexdigest()
        )
        setup = [
            sys.executable,
            str(installed_skill / "scripts/configure.py"),
            "--root",
            str(target),
            "--engine",
            requirement,
            "--instructions",
            "AGENTS.md",
        ]
        subprocess.run(setup, check=True, env=env, capture_output=True)
        assert not (target / ".repo-policy/policy.yaml").exists()
        subprocess.run([*setup, "--apply"], check=True, env=env, capture_output=True)
        before = {
            p.relative_to(target).as_posix(): p.read_bytes()
            for p in target.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(target).parts
        }
        subprocess.run([*setup, "--apply"], check=True, env=env, capture_output=True)
        assert before == {
            p.relative_to(target).as_posix(): p.read_bytes()
            for p in target.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(target).parts
        }
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "-r",
                str(target / ".repo-policy/requirements.txt"),
            ],
            check=True,
            env=env,
        )
        subprocess.run([str(command), "check", "--all"], cwd=target, env=env, check=True)
        assert not (target / "src/repo_policy").exists()
        print(
            "Skill distribution and target integration smoke test passed (repeat setup unchanged)."
        )
        print("Wheel smoke test passed (isolated, non-editable installation).")
        print("SHA256: " + hashlib.sha256(wheel.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
