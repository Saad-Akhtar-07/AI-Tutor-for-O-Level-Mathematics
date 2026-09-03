@echo off
setlocal
cd /d "%~dp0.."
"%~dp0.venv\Scripts\python.exe" -m uvicorn backend.app.main:app --reload --reload-dir backend --host 127.0.0.1 --port 8000
