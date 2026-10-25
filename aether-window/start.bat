@echo off
chcp 65001 >nul
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo 没有找到 Node.js。请先安装 Node.js LTS：https://nodejs.org  （装完重新双击 start.bat）
  pause
  exit /b 1
)
echo 正在启动 AETHER Window ... 浏览器会自动打开 http://localhost:8787
start "" http://localhost:8787
node server.mjs
pause
