@echo off
cd /d "%~dp0"
echo Lin Router preview: http://127.0.0.1:18409
echo Config: lin-router-config.json
echo.
set "SERVER_PYTHON=%LINROUTER_SERVER_PYTHON%"
if not defined SERVER_PYTHON set "SERVER_PYTHON=python"
"%SERVER_PYTHON%" --version >nul 2>nul
if errorlevel 1 (
  echo 无法执行 Python：%SERVER_PYTHON%
  echo 请激活 Server 环境或设置 LINROUTER_SERVER_PYTHON，并安装 requirements\server.txt。
  exit /b 1
)
"%SERVER_PYTHON%" -m linrouter_server --host 127.0.0.1 --port 18409 --config lin-router-config.json
echo.
echo Preview server stopped. Press any key to close this window.
pause >nul
