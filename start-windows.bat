@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    set "WORKBENCH_PY=py -3"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3.12 or newer is required. Install Python, then run this file again.
        pause
        exit /b 1
    )
    set "WORKBENCH_PY=python"
)
%WORKBENCH_PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)"
if errorlevel 1 (
    echo Python 3.12 or newer is required. Update Python, then run this file again.
    pause
    exit /b 1
)
echo Starting the local content workbench. Keep this window open.
echo Address: http://127.0.0.1:8765
%WORKBENCH_PY% -m workbench serve --open-browser
if errorlevel 1 (
    echo Startup failed. Copy the error text above and send it for troubleshooting.
    pause
)
endlocal
