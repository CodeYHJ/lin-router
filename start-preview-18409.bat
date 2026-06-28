@echo off
cd /d "%~dp0"
echo Lin Router preview: http://127.0.0.1:18409
echo Config: lin-router-config.json
echo.
set "PYTHON_EXE=C:\Users\lqy\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
"%PYTHON_EXE%" app.py --host 127.0.0.1 --port 18409 --config lin-router-config.json
echo.
echo Preview server stopped. Press any key to close this window.
pause >nul
