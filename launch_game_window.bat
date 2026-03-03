@echo off
setlocal
cd /d "%~dp0"

set "EXE=release\windows\ProjectMoonlightEngine\ProjectMoonlightEngine.exe"
if not exist "%EXE%" (
    echo Game executable not found: %EXE%
    echo Build first with: build_game_exe.bat
    pause
    exit /b 1
)

start "Project Moonlight Engine" "%SystemRoot%\System32\conhost.exe" "%CD%\%EXE%"
exit /b 0
