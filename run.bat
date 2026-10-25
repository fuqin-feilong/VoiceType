@echo off
rem Launch VoiceType without console
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo [ERROR] .venv not found. See README.md
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m voicetype
