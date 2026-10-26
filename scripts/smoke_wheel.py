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
            "repository-policy-linter @ "
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
        assert not (target / ".repo-policy.yaml").exists()
        subprocess.run([*setup, "--apply"], check=True, env=env, capture_output=True)
        before = {p.name: p.read_bytes() for p in target.iterdir() if p.is_file()}
        subprocess.run([*setup, "--apply"], check=True, env=env, capture_output=True)
        assert before == {p.name: p.read_bytes() for p in target.iterdir() if p.is_file()}
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "-r",
                str(target / ".repo-policy-requirements.txt"),
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
