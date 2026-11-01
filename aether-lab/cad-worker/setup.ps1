# Create the isolated CAD environment (Python 3.12 + CadQuery / OpenCascade) on Windows. Run from this folder:
#   powershell -ExecutionPolicy Bypass -File setup.ps1
# Needs `uv` (winget install astral-sh.uv) or the Python launcher with 3.12 installed (py -3.12).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (Get-Command uv -ErrorAction SilentlyContinue) {
  uv venv -p 3.12 .venv
  uv pip install -p .venv\Scripts\python.exe -r requirements.txt
} else {
  py -3.12 -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements.txt
}
.venv\Scripts\python.exe -c "import cadquery, OCP; print('CAD worker ready: cadquery', cadquery.__version__)"
