#!/usr/bin/env python3
"""Invoke the Windows native agent-browser CLI without cmd argument parsing."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


NATIVE_NAME = "agent-browser-win32-x64.exe"


def validate_session(session: str) -> str:
    if session.lower() == "default" or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", session):
        raise ValueError("Use a task-owned, non-default session (letters, digits, _ or -).")
    return session


def resolve_binary(explicit: str | None = None) -> Path:
    configured = explicit or os.environ.get("AGENT_BROWSER_BIN")
    if configured:
        binary = Path(configured).expanduser().resolve()
        if binary.is_file() and binary.suffix.lower() == ".exe":
            return binary
        raise FileNotFoundError("AGENT_BROWSER_BIN/--bin must point to the native .exe.")

    candidates: list[Path] = []
    direct = shutil.which(NATIVE_NAME)
    if direct:
        candidates.append(Path(direct))
    for launcher in ("agent-browser", "agent-browser.cmd"):
        installed = shutil.which(launcher)
        if installed:
            base = Path(installed).resolve().parent
            candidates.extend([
                base / "node_modules" / "agent-browser" / "bin" / NATIVE_NAME,
                base / NATIVE_NAME,
            ])
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "npm" / "node_modules" / "agent-browser" / "bin" / NATIVE_NAME)
    for binary in candidates:
        if binary.is_file():
            return binary.resolve()
    raise FileNotFoundError(
        "Native agent-browser not found. Inspect the installation or set AGENT_BROWSER_BIN."
    )


def run_agent(
    session: str,
    command: list[str],
    *,
    binary: str | None = None,
    capture: bool = False,
    stdin: bytes | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    validate_session(session)
    if not command:
        raise ValueError("An agent-browser command is required after --.")
    # Prevent command-level flags from overriding the task-owned session.
    if any(item == "--session" or item.startswith("--session=") for item in command):
        raise ValueError("Specify the session once, in the wrapper's --session option.")
    argv = [str(resolve_binary(binary)), "--session", session, *command]
    options = {"shell": False, "capture_output": capture, "timeout": timeout}
    if stdin is not None:
        options["input"] = stdin
    # With no explicit input, inherit stdin so eval --stdin also works in a pipe.
    return subprocess.run(argv, **options)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--bin", dest="binary", help="Path to native agent-browser .exe")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        return run_agent(args.session, command, binary=args.binary).returncode
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"agent-browser wrapper: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
