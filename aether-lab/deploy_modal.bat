@echo off
rem Redeploy the AETHER engine to Modal (GPU). Run this every time the engine changes.
cd /d %~dp0
set PYTHONUTF8=1
modal deploy modal_app.py
echo.
echo Done. The running server notices the new engine within a minute (no restart needed).
pause
