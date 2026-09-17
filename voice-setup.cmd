@echo off
setlocal
cd /d "%~dp0"
"backend\.venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 exit /b 1
pushd voice-worker
call npm.cmd ci
if errorlevel 1 (popd & exit /b 1)
call npm.cmd run setup
set "voice_exit=%errorlevel%"
popd
exit /b %voice_exit%
