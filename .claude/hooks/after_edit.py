"""Runs after Claude edits or writes a file, and checks it with the tool that belongs to it:

  tools/**.py ...... ruff and mypy over tools/            (the same checks as the `python` job of every PR)
  *.tf ............. terraform fmt on that file            (it rewrites the formatting in place)

Claude Code passes the edit as JSON on stdin. When a check fails, the problem goes to stderr and the exit code is 2, which gives the
output back to Claude so it fixes the file. Anything else exits 0 without a word. The logic lives here, not in settings.json.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def find_tool(name: str) -> Optional[str]:
    """The project's own copy (.venv/bin) if there is one, else whatever is on the PATH."""
    in_venv = os.path.join(ROOT, ".venv", "bin", name)
    return in_venv if os.path.exists(in_venv) else shutil.which(name)


def run(command: List[str]) -> Tuple[int, str]:
    """Run a command from the project root and return (exit code, its output)."""
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def check_python() -> List[str]:
    """ruff and mypy over tools/; one message per tool that complains."""
    problems = []
    for name, arguments in (("ruff", ["check", "tools"]), ("mypy", ["tools"])):
        tool = find_tool(name)
        if tool is None:
            continue                                  # not installed here: the PR's python job still runs it
        code, output = run([tool] + arguments)
        if code != 0:
            problems.append("{} {} failed:\n{}".format(name, " ".join(arguments), output))
    return problems


def format_terraform(path: str) -> List[str]:
    """terraform fmt on one file; a syntax error is reported, a formatting difference is fixed in place."""
    terraform = shutil.which("terraform")
    if terraform is None:
        return []
    code, output = run([terraform, "fmt", "-no-color", path])
    return ["terraform fmt could not format {}:\n{}".format(path, output)] if code != 0 else []


def main() -> int:
    """Read the edit from stdin, run the check for that kind of file, and report."""
    try:
        path = json.load(sys.stdin).get("tool_input", {}).get("file_path", "")
    except (ValueError, AttributeError):
        return 0
    if not path:
        return 0
    relative = os.path.relpath(path, ROOT)
    if relative.startswith(os.pardir):
        return 0                                      # a file outside this project is none of this hook's business

    problems: List[str] = []
    if relative.startswith("tools" + os.sep) and relative.endswith(".py"):
        problems = check_python()
    elif relative.endswith(".tf") and not relative.startswith((".history", ".terraform")):
        problems = format_terraform(path)

    if problems:
        print("\n\n".join(problems), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
