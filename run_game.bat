@echo off
setlocal
cd /d "%~dp0"

if /I not "%~1"=="--launched" (
    start "" /max "%ComSpec%" /c ""%~f0" --launched"
    exit /b
)
shift

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m rpg
) else (
    python -m rpg
)

if errorlevel 1 (
    echo.
    echo Game exited with an error. Press any key to close.
    pause >nul
)
