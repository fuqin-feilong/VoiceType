@echo off
rem Dev mode: keep console for logs
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" -m voicetype
