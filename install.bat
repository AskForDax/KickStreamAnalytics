@echo off
setlocal enabledelayedexpansion
title Kick Report - Installer
color 0A
cls

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║         KICK REPORT - LOCAL ENVIRONMENT INSTALLER           ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.

set "ROOT=%~dp0"
set "PKGS=%ROOT%packages"
set "FOUND="

:: ─────────────────────────────────────────────────────────────
::  SCAN COMMON PYTHON LOCATIONS FOR TKINTER
:: ─────────────────────────────────────────────────────────────
echo  Searching for Python with tkinter...
echo.

for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
    "C:\ProgramData\miniconda3\python.exe"
    "%USERPROFILE%\miniconda3\python.exe"
    "%USERPROFILE%\anaconda3\python.exe"
    "C:\ProgramData\anaconda3\python.exe"
) do (
    if exist "%%~P" (
        "%%~P" -c "import tkinter" >nul 2>&1
        if !errorlevel! == 0 (
            set "FOUND=%%~P"
            echo  ✓ Found: %%~P
            goto :found_python
        )
    )
)

:: Try PATH
for /f "delims=" %%i in ('where python 2^>nul') do (
    "%%i" -c "import tkinter" >nul 2>&1
    if !errorlevel! == 0 (
        set "FOUND=%%i"
        echo  ✓ Found in PATH: %%i
        goto :found_python
    )
)

:: ─────────────────────────────────────────────────────────────
::  PYTHON NOT FOUND - DOWNLOAD AND INSTALL IT
:: ─────────────────────────────────────────────────────────────
echo  Python not found. Downloading installer...
echo.

set "PY_EXE=%TEMP%\python_setup.exe"
set "PY_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%PY_URL%', '%PY_EXE%')" >nul 2>&1

if not exist "%PY_EXE%" (
    curl -sL -o "%PY_EXE%" "%PY_URL%" >nul 2>&1
)

if not exist "%PY_EXE%" (
    echo.
    echo  [ERROR] Could not download Python automatically.
    echo.
    echo  Please download and install Python manually:
    echo  https://www.python.org/downloads/
    echo.
    echo  During install make sure to tick:
    echo    "Add python.exe to PATH"
    echo.
    echo  Then re-run install.bat
    echo.
    pause
    exit /b 1
)

echo  Download complete. Running Python installer...
echo.
echo  ════════════════════════════════════════════════════════
echo  IMPORTANT: When the installer opens -
echo    1. Tick "Add python.exe to PATH" at the bottom
echo    2. Click "Install Now"
echo    3. Wait for it to finish then click Close
echo    4. Come back here and press any key
echo  ════════════════════════════════════════════════════════
echo.
pause

start /wait "" "%PY_EXE%"
del "%PY_EXE%" >nul 2>&1

:: Refresh PATH from registry after install
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "PATH=%%B;%PATH%"
for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "PATH=%%B;%PATH%"

:: Re-scan for Python after install
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
) do (
    if exist "%%~P" (
        "%%~P" -c "import tkinter" >nul 2>&1
        if !errorlevel! == 0 (
            set "FOUND=%%~P"
            goto :found_python
        )
    )
)

for /f "delims=" %%i in ('where python 2^>nul') do (
    "%%i" -c "import tkinter" >nul 2>&1
    if !errorlevel! == 0 (
        set "FOUND=%%i"
        goto :found_python
    )
)

echo.
echo  [!] Python installed but could not be detected yet.
echo  Please close this window and re-run install.bat
echo.
pause
exit /b 1

:: ─────────────────────────────────────────────────────────────
::  INSTALL PACKAGES
:: ─────────────────────────────────────────────────────────────
:found_python
echo.
echo  Using: !FOUND!
echo.
echo  Installing packages into .\packages\ ...
echo.

:: ─────────────────────────────────────────────────────────────
::  PRE-FIX: Install typer system-wide to resolve huggingface-hub conflict
:: ─────────────────────────────────────────────────────────────
echo  Pre-fixing dependency conflicts...
"!FOUND!" -m pip install typer -q >nul 2>&1
echo  ✓ done

if not exist "%PKGS%" mkdir "%PKGS%"

echo  [1/6] typer (resolves dependency conflicts)...
"!FOUND!" -m pip install typer --target="%PKGS%" --no-warn-script-location -q
echo  ✓ done

echo  [2/6] websockets...
"!FOUND!" -m pip install websockets --target="%PKGS%" --no-warn-script-location -q
echo  ✓ done

echo  [3/6] colorama...
"!FOUND!" -m pip install colorama --target="%PKGS%" --no-warn-script-location -q
echo  ✓ done

echo  [4/6] tabulate...
"!FOUND!" -m pip install tabulate --target="%PKGS%" --no-warn-script-location -q
echo  ✓ done

echo  [5/6] curl_cffi...
"!FOUND!" -m pip install curl_cffi --target="%PKGS%" --no-warn-script-location -q
if !errorlevel! neq 0 (echo  [!] curl_cffi skipped - optional) else (echo  ✓ done)

echo  [6/6] keyring (secure API key storage)...
"!FOUND!" -m pip install keyring --target="%PKGS%" --no-warn-script-location -q
echo  ✓ done

echo  [+] GPUtil (GPU detection)...
"!FOUND!" -m pip install GPUtil --target="%PKGS%" --no-warn-script-location -q
echo  ✓ done

echo  [+] psutil (process detection)...
"!FOUND!" -m pip install psutil --target="%PKGS%" --no-warn-script-location -q
echo  ✓ done

:: ─────────────────────────────────────────────────────────────
::  WRITE run.bat WITH DETECTED PYTHON PATH
:: ─────────────────────────────────────────────────────────────
echo.
echo  Creating run.bat...

> "%ROOT%run.bat" echo @echo off
>> "%ROOT%run.bat" echo start "" "!FOUND!" "%%~dp0kick_report.py"
>> "%ROOT%run.bat" echo exit /b 0

echo  ✓ run.bat created.
echo.
echo  ════════════════════════════════════════════════════════
echo   ALL DONE - double-click run.bat to launch the GUI
echo  ════════════════════════════════════════════════════════
echo.
set /p "GO=  Launch GUI now? [Y/N]: "
if /i "!GO!"=="Y" start "" "!FOUND!" "%ROOT%kick_report.py"

echo.
pause
exit /b 0
