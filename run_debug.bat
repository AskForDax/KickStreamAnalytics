@echo off
setlocal EnableDelayedExpansion
title Kick Stream Analytics - Debug Mode

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║     KICK STREAM ANALYTICS - DEBUG LAUNCHER                  ║
echo  ║     Console stays open to show any error messages           ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.

set "ROOT=%~dp0"
set "PKGS=%ROOT%packages"

:: ── Find Python — skip Windows Store stub ────────────────────
set "FOUND="

for %%P in (
    "C:\ProgramData\miniconda3\python.exe"
    "C:\ProgramData\miniconda\python.exe"
    "%USERPROFILE%\miniconda3\python.exe"
    "%USERPROFILE%\Anaconda3\python.exe"
    "%USERPROFILE%\AppData\Local\miniconda3\python.exe"
) do (
    if exist %%P if not defined FOUND set "FOUND=%%~P"
)

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

if not defined FOUND (
    for /f "tokens=*" %%i in ('where python 2^>nul') do (
        if not defined FOUND (
            echo %%i | findstr /i "WindowsApps" >nul
            if !errorlevel! neq 0 set "FOUND=%%i"
        )
    )
)

if not defined FOUND (
    echo  [!] Python not found. Run install.bat first.
    pause & exit /b 1
)

echo  Using Python: %FOUND%
echo  Packages: %PKGS%
echo.
echo  ── Starting app in debug mode ─────────────────────────────────
echo  Any errors will appear below. Copy and paste them when seeking help.
echo  ───────────────────────────────────────────────────────────────
echo.

set PYTHONPATH=%PKGS%
"%FOUND%" "%ROOT%kick_report.py"

echo.
echo  ── App closed ──────────────────────────────────────────────────
echo  Exit code: %errorlevel%
if %errorlevel% neq 0 (
    echo.
    echo  App exited with an error. See messages above.
    echo  Copy the error text and seek support.
)
echo  ───────────────────────────────────────────────────────────────
echo.
pause
endlocal
