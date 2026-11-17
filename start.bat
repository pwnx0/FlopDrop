@echo off
setlocal

rem Run from the directory containing this script, even if launched elsewhere.
cd /d "%~dp0"
set "PROJECT_DIR=%~dp0"
set "PYTHON="

rem Prefer the Windows Python launcher, then fall back to python on PATH.
where py >nul 2>nul
if not errorlevel 1 (
    py -3 --version >nul 2>nul
    if not errorlevel 1 set "PYTHON=py -3"
)
if not defined PYTHON (
    where python >nul 2>nul
    if not errorlevel 1 (
        python --version >nul 2>nul
        if not errorlevel 1 set "PYTHON=python"
    )
)

if not defined PYTHON (
    where winget >nul 2>nul
    if not errorlevel 1 (
        echo Python was not found. Attempting installation with winget...
        winget install --id Python.Python.3.12 --exact --scope user --silent --accept-package-agreements --accept-source-agreements
        if errorlevel 1 goto :python_missing
        rem Refresh PATH for this process after the installer completes.
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
        where py >nul 2>nul
        if not errorlevel 1 (
            py -3 --version >nul 2>nul
            if not errorlevel 1 set "PYTHON=py -3"
        )
        if not defined PYTHON (
            where python >nul 2>nul
            if not errorlevel 1 (
                python --version >nul 2>nul
                if not errorlevel 1 set "PYTHON=python"
            )
        )
    )
)
if not defined PYTHON goto :python_missing

rem Verify that this Python meets the documented minimum version.
%PYTHON% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo ERROR: Python 3.10 or newer is required.
    echo Install Python 3.10+ from https://www.python.org/downloads/windows/
    echo Then follow the dependency installation commands in README.md:
    echo   python -m pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "%PROJECT_DIR%requirements.txt" (
    echo ERROR: requirements.txt was not found in "%PROJECT_DIR%".
    pause
    exit /b 1
)

echo Installing or verifying Python dependencies...
%PYTHON% -m pip install -r "%PROJECT_DIR%requirements.txt"
if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    echo See README.md for setup instructions. The documented command is:
    echo   python -m pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "%PROJECT_DIR%.env" if exist "%PROJECT_DIR%.env.example" (
    copy "%PROJECT_DIR%.env.example" "%PROJECT_DIR%.env" >nul
    if errorlevel 1 (
        echo ERROR: Could not create .env from .env.example.
        echo Follow the environment setup instructions in README.md.
        pause
        exit /b 1
    )
    echo Created .env from .env.example. Set FLOP_PRIVATE_KEY before running the bot.
    %PYTHON% main.py --generate-wallet
    pause
    exit /b 0
)

%PYTHON% main.py %*
set "EXIT_CODE=%ERRORLEVEL%"
pause
exit /b %EXIT_CODE%

:python_missing
echo ERROR: Python 3.10 or newer could not be found or installed automatically.
echo Install Python 3.10+ from https://www.python.org/downloads/windows/
echo Then follow the dependency installation commands in README.md:
echo   python -m pip install -r requirements.txt
pause
exit /b 1
