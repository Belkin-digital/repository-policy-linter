import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import DEFAULT_CONFIG, KINDS, load_config
from .engine import run
from .files import safe_path
from .model import PolicyError


def selection_options(parser):
    parser.add_argument("--root", default=".", help="repository root (default: current directory)")
    parser.add_argument("--config", default=".repo-policy.yaml", help="path relative to root")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--all", action="store_true", help="all tracked and unignored files (default)"
    )
    selection.add_argument(
        "--changed", action="store_true", help="staged, unstaged and untracked files"
    )
    selection.add_argument("--files", nargs="+", help="explicit root-relative filenames")
    parser.add_argument("--base", help="with --changed: merge-base with this Git ref")
    parser.add_argument(
        "--allow-plugins", action="store_true", help="permit reviewed external commands"
    )
    parser.add_argument("--fail-on", choices=["error", "warning", "info"], default="error")


def execute(args):
    if args.base and not args.changed:
        raise PolicyError("--base requires --changed")
    return run(
        args.root,
        config_name=args.config,
        mode="changed" if args.changed else "all",
        base=args.base,
        files=args.files,
        allow_plugins=args.allow_plugins,
        fail_on=args.fail_on,
        fix=getattr(args, "command", None) == "fix" and not args.dry_run,
    )


def error_report(message):
    return {
        "schema_version": 1,
        "engine_version": __version__,
        "diagnostics": [],
        "error": message,
        "exit_code": 2,
    }


def print_report(report, output):
    if output == "json":
        print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
        return
    for item in report.get("diagnostics", []):
        # Escape control characters in untrusted filenames/tool messages for terminals.
        def clean(value):
            return json.dumps(value, ensure_ascii=True)[1:-1]

        print(
            f"{clean(item['file'])}:{item['line']}:{item['column']}: "
            f"{item['severity']} [{item['rule']}] {clean(item['message'])}"
        )
    if "error" in report:
        print("repo-policy: " + json.dumps(report["error"], ensure_ascii=True), file=sys.stderr)
    else:
        print(
            f"{len(report['files_checked'])} files; {len(report['diagnostics'])} diagnostics; "
            f"{len(report['fixed'])} fixed; {len(report['skipped'])} skipped"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="repo-policy", description="Local repository policy checks"
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "fix"):
        command = commands.add_parser(name)
        selection_options(command)
        command.add_argument("--format", choices=["text", "json"], default="text")
        command.add_argument("--dry-run", action="store_true", help="check without writing")
    init = commands.add_parser(
        "init", help="write a starter config, never replace an existing file"
    )
    init.add_argument("--root", default=".")
    init.add_argument("--config", default=".repo-policy.yaml")
    explain = commands.add_parser(
        "explain", help="describe built-in kinds or a configured rule/plugin"
    )
    explain.add_argument("rule", nargs="?")
    explain.add_argument("--root", default=".")
    explain.add_argument("--config", default=".repo-policy.yaml")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            path = safe_path(Path(args.root).resolve(), args.config)
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(DEFAULT_CONFIG)
            print(f"Created {args.config}")
            return 0
        if args.command == "explain":
            if args.rule is None or args.rule in KINDS:
                print(json.dumps({args.rule: KINDS[args.rule]} if args.rule else KINDS, indent=2))
            else:
                config = load_config(safe_path(Path(args.root).resolve(), args.config))
                rule = next(
                    (
                        r
                        for r in config.get("rules", []) + config.get("plugins", [])
                        if r["id"] == args.rule
                    ),
                    None,
                )
                if rule is None:
                    raise PolicyError("unknown rule/plugin id")
                print(
                    json.dumps(
                        {
                            "configuration": rule,
                            "description": KINDS.get(
                                rule.get("kind"),
                                "External command; enable only after reviewing command and config.",
                            ),
                        },
                        indent=2,
                        ensure_ascii=True,
                        sort_keys=True,
                    )
                )
            return 0
        report = execute(args)
    except (PolicyError, OSError) as exc:
        message = (
            str(exc) if isinstance(exc, PolicyError) else f"filesystem error: {type(exc).__name__}"
        )
        report = error_report(message)
    except KeyboardInterrupt:
        return 130
    print_report(report, getattr(args, "format", "text"))
    return report["exit_code"]
