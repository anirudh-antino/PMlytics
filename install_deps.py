#!/usr/bin/env python3
"""Install dependencies after verifying Python >= 3.10 (required by gemini-analyzer)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MIN_PY = (3, 10)


def _too_old_message() -> str:
    current = sys.version.split()[0]
    head = (
        f"Python {MIN_PY[0]}.{MIN_PY[1]}+ required (you have {current}).\n"
        "Do this, then run this script again with the new Python:\n"
    )
    if sys.platform == "darwin":
        steps = """
  1) Install Python 3.12 (pick one):
     • Homebrew:  brew install python@3.12
     • Or download an installer:  https://www.python.org/downloads/macos/
  2) Check it:    /opt/homebrew/bin/python3.12 --version   (Homebrew Apple Silicon)
                  /usr/local/bin/python3.12 --version       (Homebrew Intel)
                  or:           python3.12 --version
  3) From this project folder:
                  python3.12 -m venv .venv
                  .venv/bin/python install_deps.py
                  .venv/bin/python app.py
"""
    elif sys.platform == "win32":
        steps = """
  1) Install Python 3.12:  https://www.python.org/downloads/windows/
     (check "Add python.exe to PATH", or note the install path.)
  2) Open a new terminal and check:  py -3.12 --version
     If that works:  py -3.12 -m venv .venv
                     .venv\\Scripts\\python.exe install_deps.py
                     .venv\\Scripts\\python.exe app.py
"""
    else:
        steps = """
  1) Install Python 3.10+ with your distro (examples):
       Ubuntu/Debian:  sudo apt update && sudo apt install python3.12 python3.12-venv
       Fedora:         sudo dnf install python3.12
  2) Check:           python3.12 --version
  3) From this project folder:
                      python3.12 -m venv .venv
                      .venv/bin/python install_deps.py
                      .venv/bin/python app.py
"""
    return head + steps


def main() -> int:
    if sys.version_info < MIN_PY:
        print(_too_old_message(), file=sys.stderr)
        return 1

    root = Path(__file__).resolve().parent
    req = root / "requirements.txt"
    if not req.is_file():
        print(f"Missing {req}", file=sys.stderr)
        return 1

    return subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req)],
        cwd=root,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
