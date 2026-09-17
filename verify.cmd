@echo off
setlocal
cd /d "%~dp0"

echo [1/7] Compiling backend Python...
"backend\.venv\Scripts\python.exe" -m compileall -q backend scripts
if errorlevel 1 exit /b 1

echo [2/7] Running backend integration tests...
"backend\.venv\Scripts\python.exe" -m pytest backend\tests -q
if errorlevel 1 exit /b 1

echo [3/7] Verifying PostgreSQL content...
"backend\.venv\Scripts\python.exe" -m backend.scripts.verify
if errorlevel 1 exit /b 1

echo [4/7] Testing frontend API recovery...
pushd frontend
call npm.cmd test
set "api_exit=%errorlevel%"
popd
if not "%api_exit%"=="0" exit /b %api_exit%

echo [5/7] Testing voice lifecycle...
pushd frontend
call npm.cmd run test:voice
set "voice_exit=%errorlevel%"
popd
if not "%voice_exit%"=="0" exit /b %voice_exit%

echo [6/7] Testing maths pronunciation...
pushd voice-worker
call npm.cmd test
set "math_exit=%errorlevel%"
popd
if not "%math_exit%"=="0" exit /b %math_exit%
if errorlevel 1 exit /b 1

echo [7/7] Building frontend...
pushd frontend
call npm.cmd run build
set "frontend_exit=%errorlevel%"
popd
if not "%frontend_exit%"=="0" exit /b %frontend_exit%

echo Full-stack verification passed.
