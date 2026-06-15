@echo off
setlocal EnableExtensions

REM Git AI live demo — works on AllSigned / GPO-locked PowerShell.
REM Run from repo root:
REM   scripts\git-ai-demo.cmd
REM   scripts\git-ai-demo.cmd skip-install
REM   scripts\git-ai-demo.cmd skip-commit
REM   scripts\git-ai-demo.cmd keep-branch

set "SKIP_INSTALL=0"
set "SKIP_COMMIT=0"
set "KEEP_BRANCH=0"

:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="skip-install" set "SKIP_INSTALL=1"
if /i "%~1"=="skip-commit" set "SKIP_COMMIT=1"
if /i "%~1"=="keep-branch" set "KEEP_BRANCH=1"
shift
goto parse_args
:args_done

cd /d "%~dp0.."
if errorlevel 1 (
	echo Failed to cd to repo root.
	exit /b 1
)

set "DEMO_BRANCH=demo/git-ai-presentation"
set "DEMO_FILE=scripts\git-ai-demo-sample.py"
set "GIT_AI_BIN=%USERPROFILE%\.git-ai\bin"
set "GIT_AI_EXE=%GIT_AI_BIN%\git-ai.exe"

call :step "0. Install / update Git AI (v1.5.8)"
if "%SKIP_INSTALL%"=="0" call :ensure_git_ai
if not exist "%GIT_AI_EXE%" (
	echo.
	echo git-ai.exe not found. Install manually:
	echo   powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://github.com/git-ai-project/git-ai/releases/download/v1.5.8/install.ps1 ^| iex"
	exit /b 1
)

call :step "1. Version and hooks" "git ai --version"
call :run git ai --version
call :run git ai install-hooks

for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set "PREV_BRANCH=%%b"

git branch --list %DEMO_BRANCH% | findstr /i "%DEMO_BRANCH%" >nul
if errorlevel 1 (
	call :run git checkout -b %DEMO_BRANCH%
) else (
	call :run git checkout %DEMO_BRANCH%
)

call :step "2. Baseline checkpoint (human)" "git ai checkpoint"
call :run git ai checkpoint

call :step "3. Create sample file + AI checkpoint (mock_ai)"
> "%DEMO_FILE%" (
echo """Sample module for Git AI demo — safe to delete after presentation."""
echo.
echo def greet(name: str^) -^> str:
echo     return f"Hello, {name}!"
)
call :run git ai checkpoint mock_ai

call :step "4. Working tree attribution" "git ai status"
call :run git ai status

call :step "5. Working log detail" "git ai checkpoint --show-working-log"
call :run git ai checkpoint --show-working-log

if "%SKIP_COMMIT%"=="1" (
	echo.
	echo skip-commit set — stopping before commit.
	goto done
)

call :step "6. Commit (attribution -^> git note)"
call :run git add %DEMO_FILE%
call :run git commit -m "demo: add git-ai sample module"

call :step "7. Post-commit stats" "git ai stats"
call :run git ai stats
call :run git ai stats --json

call :step "8. AI blame" "git ai blame %DEMO_FILE%"
call :run git ai blame %DEMO_FILE%

call :step "9. Annotated diff" "git ai diff HEAD"
call :run git ai diff HEAD

call :step "10. Raw authorship note" "git ai show HEAD"
call :run git ai show HEAD

call :step "11. Git log with AI notes" "git log --show-notes=ai -1"
call :run git log --show-notes=ai -1

if "%KEEP_BRANCH%"=="0" (
	call :run git checkout %PREV_BRANCH%
	echo.
	echo Returned to branch: %PREV_BRANCH%
	echo Demo branch kept as: %DEMO_BRANCH%
)

:done
echo.
echo Demo complete.
exit /b 0

:ensure_git_ai
if not exist "%GIT_AI_BIN%" mkdir "%GIT_AI_BIN%"
if exist "%GIT_AI_EXE%" (
	"%GIT_AI_EXE%" --version 2>nul | findstr /i "1.5.8" >nul
	if not errorlevel 1 (
		echo Already on v1.5.8
		goto :eof
	)
)
echo Downloading git-ai v1.5.8 ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://github.com/git-ai-project/git-ai/releases/download/v1.5.8/git-ai-windows-x64.exe' -OutFile '%GIT_AI_EXE%'"
goto :eof

:step
echo.
echo ======================================================================
echo %~1
if not "%~2"=="" echo   ^> %~2
echo ======================================================================
goto :eof

:run
echo.
echo ^>^>^> %*
echo.
call %*
if errorlevel 1 (
	echo.
	echo Command failed: %*
	exit /b 1
)
goto :eof
