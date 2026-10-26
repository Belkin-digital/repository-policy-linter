"""AF Runner bridge: same engine/config, caller-owned output collection."""

import argparse
import hashlib
import json
from pathlib import Path

from .cli import error_report, execute, selection_options
from .files import safe_path
from .model import PolicyError


def main(argv=None):
    parser = argparse.ArgumentParser(prog="repo-policy-af")
    selection_options(parser)
    parser.add_argument(
        "--session-root", required=True, help="host mount corresponding to /session"
    )
    parser.add_argument(
        "--output-dir", required=True, help="new/existing directory inside session root"
    )
    args = parser.parse_args(argv)
    try:
        session_input = Path(args.session_root).absolute()
        session = session_input.resolve()
        output = Path(args.output_dir).absolute()
        if (
            not session.is_dir()
            or not output.is_relative_to(session_input)
            or output == session_input
        ):
            raise PolicyError("output-dir must be inside the existing session-root")
        relative = output.relative_to(session_input).as_posix()
        output = safe_path(session, relative)
        # Do not allow diagnostics to overwrite repository files.
        if output.resolve().is_relative_to(Path(args.root).resolve()):
            raise PolicyError("output-dir must be outside the repository checkout")
        output.mkdir(parents=True, exist_ok=True)
        for name in ("report.json", "outputs.fragment.json"):
            if safe_path(session, f"{relative}/{name}").exists():
                raise PolicyError("output files already exist; choose a new output-dir")
        try:
            report = execute(args)
        except (PolicyError, OSError) as exc:
            report = error_report(str(exc) if isinstance(exc, PolicyError) else "filesystem error")
        content = (json.dumps(report, sort_keys=True, ensure_ascii=True, indent=2) + "\n").encode()
        with (output / "report.json").open("xb") as stream:
            stream.write(content)
        fragment = {
            "schema_version": "1.0",
            "outputs": [
                {
                    "session_path": f"/session/{relative}/report.json",
                    "semantic_role": "report",
                    "content_type": "application/json",
                    "checksum_sha256": hashlib.sha256(content).hexdigest(),
                    "publish": False,
                }
            ],
        }
        with (output / "outputs.fragment.json").open("x", encoding="utf-8") as stream:
            json.dump(fragment, stream, indent=2, sort_keys=True)
            stream.write("\n")
        print(json.dumps({"exit_code": report["exit_code"], "report": f"{relative}/report.json"}))
        return report["exit_code"]
    except (PolicyError, OSError) as exc:
        print(
            json.dumps(
                error_report(str(exc) if isinstance(exc, PolicyError) else "filesystem error")
            )
        )
        return 2
    except KeyboardInterrupt:
        return 130
