@echo off
setlocal
cd /d "%~dp0"

echo [1/5] Compiling backend Python...
"backend\.venv\Scripts\python.exe" -m compileall -q backend scripts
if errorlevel 1 exit /b 1

echo [2/5] Running backend integration tests...
"backend\.venv\Scripts\python.exe" -m pytest backend\tests -q
if errorlevel 1 exit /b 1

echo [3/5] Verifying PostgreSQL content...
"backend\.venv\Scripts\python.exe" -m backend.scripts.verify
if errorlevel 1 exit /b 1

echo [4/5] Testing frontend API recovery...
call npm.cmd --prefix frontend test
if errorlevel 1 exit /b 1

echo [5/5] Building frontend...
pushd frontend
call npm.cmd run build
set "frontend_exit=%errorlevel%"
popd
if not "%frontend_exit%"=="0" exit /b %frontend_exit%

echo Full-stack verification passed.
