#!/usr/bin/env bash
#
# BeeswaxBind setup: installs project dependencies and the `beeswaxbind`
# console entry point, then EXITS. It never starts a server and never touches
# system packages.
#
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "==> Upgrading pip, setuptools and wheel (old pip silently breaks editable installs)"
"$PYTHON" -m pip install --upgrade pip setuptools wheel

echo "==> Installing project dependencies from requirements.txt"
"$PYTHON" -m pip install -r requirements.txt

echo "==> Installing the beeswaxbind console entry point"
"$PYTHON" -m pip install --no-build-isolation --editable .

echo "==> Self-check: importing the module and printing its version"
"$PYTHON" -c 'import beeswaxbind; print("beeswaxbind", beeswaxbind.__version__, "imported from", beeswaxbind.__file__)'
"$PYTHON" beeswaxbind.py --version

echo
echo "Setup complete. Nothing is running in the background."
echo "Run:  python3 beeswaxbind.py --help      (no install needed at all)"
echo "  or: beeswaxbind --help                 (console entry point)"
echo "Tests: python3 -m unittest discover -s tests"
