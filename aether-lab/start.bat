@echo off
cd /d %~dp0
python -m pip install -q -r requirements.txt
rem the server opens the browser itself once the project is loaded (no blank page to reload)
set AETHER_OPEN_BROWSER=1
python server.py
