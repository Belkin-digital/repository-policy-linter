import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import CONFIG_NAME, DEFAULT_CONFIG, DEFAULT_REGISTRY, KINDS, SYSTEM_CHECKS
from .engine import run
from .files import safe_path
from .model import PolicyError
from .policy import load_policy, read_text


def selection_options(parser):
    parser.add_argument("--root", default=".", help="repository root (default: current directory)")
    parser.add_argument("--config", default=CONFIG_NAME, help="manifest path relative to root")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--all", action="store_true", help="all tracked and unignored files (default)"
    )
    selection.add_argument(
        "--changed", action="store_true", help="staged, unstaged and untracked files"
    )
    selection.add_argument("--files", nargs="+", help="explicit root-relative filenames")
    selection.add_argument(
        "--commit", help="check the exact commit snapshot against its first parent"
    )
    parser.add_argument("--base", help="with --changed: merge-base with this Git ref")
    parser.add_argument(
        "--allow-plugins", action="store_true", help="permit reviewed external commands"
    )
    parser.add_argument("--fail-on", choices=["error", "warning", "info"], default="error")


def execute(args):
    if args.base and not args.changed:
        raise PolicyError("--base requires --changed")
    if args.commit is not None and getattr(args, "command", None) == "fix":
        raise PolicyError("--commit is only available for check")
    return run(
        args.root,
        config_name=args.config,
        mode="changed" if args.changed else "all",
        base=args.base,
        files=args.files,
        allow_plugins=args.allow_plugins,
        fail_on=args.fail_on,
        fix=getattr(args, "command", None) == "fix" and not args.dry_run,
        commit=args.commit,
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
        for request in report.get("review_requests", []):
            print("Subagent review required: " + json.dumps(request["artifact"], ensure_ascii=True))
            print(
                "  Contract: "
                + json.dumps(request["contract_id"], ensure_ascii=True)
                + " ("
                + request["request_id"]
                + ")"
            )
            for criterion in request["criteria"]:
                print(
                    "  Criterion: "
                    + json.dumps(criterion["id"], ensure_ascii=True)
                    + "; rubric: "
                    + json.dumps(criterion["rubric"], ensure_ascii=True)
                )
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
    init.add_argument("--config", default=CONFIG_NAME)
    explain = commands.add_parser(
        "explain", help="describe built-ins or resolve a check/contract ID"
    )
    explain.add_argument("rule", nargs="?")
    explain.add_argument("--root", default=".")
    explain.add_argument("--config", default=CONFIG_NAME)
    explain.add_argument("--kind", action="store_true", help="explicitly explain a built-in kind")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            root = Path(args.root).resolve()
            path = safe_path(root, args.config)
            directory = path.parent.relative_to(root).as_posix()
            if directory == ".":
                raise PolicyError("the manifest must be inside a policy directory")
            registry = safe_path(root, directory + "/checks/common.yaml")
            if path.exists() or registry.exists():
                raise PolicyError("policy files already exist; init never overwrites")
            if path.parent.exists() and any(path.parent.iterdir()):
                raise PolicyError("policy directory is not empty; reconcile existing contents")
            for target, content in (
                (path, DEFAULT_CONFIG.replace(".repo-policy/", directory + "/")),
                (registry, DEFAULT_REGISTRY),
            ):
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(content)
            print(f"Created {args.config}")
            return 0
        if args.command == "explain":
            descriptions = KINDS | SYSTEM_CHECKS
            policy, rule = None, None
            root = Path(args.root).resolve()
            if args.rule and not args.kind and args.rule not in SYSTEM_CHECKS:
                if args.rule not in KINDS or safe_path(root, args.config).is_file():
                    policy = load_policy(root, args.config)
                    rule = policy.contracts.get(args.rule) or policy.definitions.get(args.rule)
            if args.rule is None or (args.rule in descriptions and rule is None):
                print(
                    json.dumps(
                        {args.rule: descriptions[args.rule]} if args.rule else descriptions,
                        indent=2,
                    )
                )
            else:
                if rule is None:
                    raise PolicyError("unknown check/contract ID or built-in kind")
                description_path = policy.directory + "/readme/" + args.rule + ".md"
                explanation = {}
                if args.rule in policy.contracts:
                    explanation["contract_path"] = (
                        policy.directory + "/contracts/" + args.rule + ".yaml"
                    )
                    if safe_path(root, description_path).is_file():
                        explanation.update(
                            explanation_path=description_path,
                            explanation=read_text(root, description_path),
                        )
                print(
                    json.dumps(
                        {
                            "configuration": rule,
                            **explanation,
                            "description": "Artifact acceptance contract"
                            if args.rule in policy.contracts
                            else KINDS.get(
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
