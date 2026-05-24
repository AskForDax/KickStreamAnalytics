@echo off
setlocal EnableDelayedExpansion
title Kick Analytics - Build FOLDER Version

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║     KICK ANALYTICS - EXE BUILDER (Folder / OneDIR)         ║
echo  ║     Output: dist\KickAnalytics\ folder                      ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.

set "ROOT=%~dp0"

:: ── Find Python — check real installs before Windows Store stub ───────────
set "FOUND="

:: 1. Miniconda / Anaconda (most common for this app)
for %%P in (
    "C:\ProgramData\miniconda3\python.exe"
    "C:\ProgramData\miniconda\python.exe"
    "%USERPROFILE%\miniconda3\python.exe"
    "%USERPROFILE%\Anaconda3\python.exe"
    "%USERPROFILE%\AppData\Local\miniconda3\python.exe"
) do (
    if exist %%P if not defined FOUND set "FOUND=%%~P"
)

:: 2. Standard Python installs
if not defined FOUND (
    for %%P in (
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
        "C:\Python312\python.exe"
        "C:\Python311\python.exe"
        "C:\Python310\python.exe"
        "C:\Python39\python.exe"
    ) do (
        if exist %%P if not defined FOUND set "FOUND=%%~P"
    )
)

:: 3. Check PATH but skip the Windows Store stub
if not defined FOUND (
    for /f "tokens=*" %%i in ('where python 2^>nul') do (
        if not defined FOUND (
            echo %%i | findstr /i "WindowsApps" >nul
            if !errorlevel! neq 0 set "FOUND=%%i"
        )
    )
)

:: 4. Check packages folder for a Python used by install.bat
if not defined FOUND (
    if exist "%ROOT%packages\pip" (
        for /f "tokens=*" %%i in ('where python 2^>nul') do (
            if not defined FOUND set "FOUND=%%i"
        )
    )
)

if not defined FOUND (
    echo.
    echo  [!] Could not find a valid Python installation.
    echo.
    echo  Please install Python first:
    echo    Option A: Download from https://python.org
    echo              IMPORTANT: Tick "Add Python to PATH" during install
    echo    Option B: Download Miniconda from https://docs.conda.io
    echo.
    echo  Then run install.bat first, then try build_folder.bat again.
    echo.
    pause & exit /b 1
)

echo  Using Python: %FOUND%
echo.

:: Verify it actually works
"%FOUND%" --version >nul 2>&1
if !errorlevel! neq 0 (
    echo  [!] Python found but not working: %FOUND%
    echo  Please run install.bat first to set up Python correctly.
    pause & exit /b 1
)

:: ── Install PyInstaller if needed ─────────────────────────────
echo  Checking PyInstaller...
"%FOUND%" -m pip show pyinstaller >nul 2>&1
if !errorlevel! neq 0 (
    echo  Installing PyInstaller...
    "%FOUND%" -m pip install pyinstaller -q --no-warn-script-location
    if !errorlevel! neq 0 (
        echo  [!] Failed to install PyInstaller.
        echo  Try running install.bat first then retry.
        pause & exit /b 1
    )
)
echo  ✓ PyInstaller ready
echo.

echo  Building KickAnalytics FOLDER version - please wait...
echo.

"%FOUND%" "%ROOT%build_spec_folder.py"

if !errorlevel! neq 0 (
    echo.
    echo  [!] Build FAILED. See errors above.
    pause & exit /b 1
)

echo.
echo  ══════════════════════════════════════════════════════════════
echo   ✓ BUILD SUCCESSFUL - FOLDER VERSION
echo   Output: %ROOT%dist\KickAnalytics\
echo.
echo   To distribute:
echo     ZIP the entire dist\KickAnalytics\ folder
echo     Users extract and run KickAnalytics.exe inside it
echo     NEVER separate KickAnalytics.exe from the _internal folder
echo  ══════════════════════════════════════════════════════════════
echo.

set /p OPEN="Open output folder? [Y/N]: "
if /i "!OPEN!"=="Y" explorer "%ROOT%dist\KickAnalytics"

endlocal
pause
