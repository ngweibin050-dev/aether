#!/usr/bin/env sh
# Create the isolated CAD environment (Python 3.12 + CadQuery / OpenCascade) next to this script.
# Needs `uv` (https://docs.astral.sh/uv/) or a python3.12 with venv.
set -e
cd "$(dirname "$0")"
if command -v uv >/dev/null 2>&1; then
  uv venv -p 3.12 .venv
  uv pip install -p .venv/bin/python -r requirements.txt
else
  python3.12 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
fi
.venv/bin/python -c "import cadquery, OCP; print('CAD worker ready: cadquery', cadquery.__version__)"
