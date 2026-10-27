import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

from .files import safe_path
from .model import Diagnostic, PolicyError
from .rules import applies

OUTPUT_LIMIT = 4 * 1_048_576


def _run(command, root, timeout):
    # Windows otherwise searches the parent interpreter's directory before PATH.
    executable = (
        shutil.which(command[0]) if os.name == "nt" and not os.path.dirname(command[0]) else None
    )
    # File-backed capture prevents unbounded RAM use; inspect a bounded output only.
    # Disk/CPU/network containment belongs to the caller's OS/container sandbox.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            child = subprocess.Popen(
                command,
                executable=executable,
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                shell=False,
                start_new_session=(os.name == "posix"),
            )
            try:
                code = child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    os.killpg(child.pid, signal.SIGKILL)
                else:
                    child.kill()
                child.wait()
                raise PolicyError("plugin timed out") from None
        except OSError as exc:
            raise PolicyError("plugin executable unavailable or cannot start") from exc
        if stdout.tell() > OUTPUT_LIMIT or stderr.tell() > OUTPUT_LIMIT:
            raise PolicyError("plugin output exceeds 4 MiB")
        stdout.seek(0)
        return code, stdout.read().decode("utf-8")


def run_plugin(plugin, root, files, *, context=None):
    repository = plugin.get("scope", "files") == "repository"
    chosen = [name for name in files if applies(name, plugin)]
    if not chosen and not repository:
        return []
    command = []
    for arg in plugin["command"]:
        if arg == "{context}":
            if context is None:
                raise PolicyError("Git context is unavailable")
            command.append(str(context))
            continue
        # Prefix prevents filenames being treated as command-line options.
        command.extend(["./" + name for name in chosen] if arg == "{files}" else [arg])
    try:
        code, output = _run(command, root, plugin.get("timeout", 30))
        if code not in plugin.get("success_codes", [0]) + plugin.get("diagnostic_codes", [1]):
            raise PolicyError(f"plugin exited with execution code {code}")
        if plugin["format"] == "regex":
            entries = []
            for line in output.splitlines():
                if not line.strip():
                    continue
                match = re.fullmatch(plugin["pattern"], line)
                if not match:
                    raise PolicyError("unrecognized plugin output line")
                entries.append(match.groupdict())
        else:
            entries = json.loads(output)
        if not isinstance(entries, list):
            raise PolicyError("plugin output must be a JSON array")
        diagnostics = []
        for item in entries:
            if plugin["format"] == "ruff":
                name, line, column = (
                    item["filename"],
                    item["location"]["row"],
                    item["location"]["column"],
                )
            else:
                name, line, column = item["file"], int(item["line"]), int(item.get("column") or 1)
            if not isinstance(name, str):
                raise PolicyError("invalid plugin filename")
            if Path(name).is_absolute():
                name = Path(name).relative_to(root).as_posix()
            elif name.startswith("./"):
                name = name[2:]
            safe_path(root, name)
            if not (applies(name, plugin) if repository else name in chosen):
                raise PolicyError("plugin diagnostic outside selected file set")
            if type(line) is not int or type(column) is not int or line < 1 or column < 1:
                raise PolicyError("invalid plugin location")
            message = item["message"]
            if not isinstance(message, str) or not message:
                raise PolicyError("invalid plugin message")
            tool_code = item.get("code") or item.get("rule")
            if tool_code:
                message = f"{tool_code}: {message}"
            diagnostics.append(
                Diagnostic(
                    name, line, column, plugin["id"], plugin.get("severity", "error"), message
                )
            )
        if code in plugin.get("diagnostic_codes", [1]) and not diagnostics:
            raise PolicyError("plugin failed without diagnostics")
        return diagnostics
    except (ValueError, KeyError, TypeError, UnicodeError, OverflowError) as exc:
        raise PolicyError(f"{plugin['id']}: malformed or unsafe plugin output") from exc
