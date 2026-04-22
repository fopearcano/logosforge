@echo off
REM Build Logosforge.exe for Windows 10/11 (x86_64).
REM
REM Usage:
REM   build_win.bat
REM
REM Prerequisites:
REM   - Windows 10 or 11 (64-bit)
REM   - Python 3.10+
REM   - pip

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..\.." ) do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"

echo === Logosforge Windows Build ===
echo Target: Windows 10/11, x86_64
echo.

REM --- 1. Create or reuse virtual environment ---
set "VENV_DIR=%PROJECT_ROOT%\build_venv"
if not exist "%VENV_DIR%" (
    echo [1/5] Creating build virtual environment...
    python -m venv "%VENV_DIR%"
) else (
    echo [1/5] Reusing existing build virtual environment...
)

call "%VENV_DIR%\Scripts\activate.bat"

REM --- 2. Install dependencies ---
echo [2/5] Installing dependencies...
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install "pyinstaller>=6.0" -q

REM --- 3. Convert PNG icon to ICO (if not already done) ---
set "ICON_PNG=%PROJECT_ROOT%\assets\icon.png"
set "ICON_ICO=%PROJECT_ROOT%\assets\icon.ico"
if not exist "%ICON_ICO%" (
    if exist "%ICON_PNG%" (
        echo [3/5] Converting icon PNG to ICO...
        pip install Pillow -q
        python -c "from PIL import Image; img = Image.open(r'%ICON_PNG%'); img.save(r'%ICON_ICO%', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
        if errorlevel 1 (
            echo   Warning: Icon conversion failed, building without custom icon
        )
    ) else (
        echo [3/5] No icon source found, building without custom icon.
    )
) else (
    echo [3/5] Icon ICO already exists.
)

REM --- 4. Run PyInstaller ---
echo [4/5] Building with PyInstaller...
pyinstaller "%SCRIPT_DIR%\logosforge.spec" ^
    --noconfirm ^
    --clean ^
    --distpath "%PROJECT_ROOT%\dist" ^
    --workpath "%PROJECT_ROOT%\build"

REM --- 5. Verify ---
set "EXE_PATH=%PROJECT_ROOT%\dist\Logosforge\Logosforge.exe"
if exist "%EXE_PATH%" (
    echo.
    echo [5/5] Build successful!
    echo.
    echo   Exe: %EXE_PATH%
    echo   Dir: %PROJECT_ROOT%\dist\Logosforge\
    echo.
    echo To run:  dist\Logosforge\Logosforge.exe
    echo To distribute: zip the dist\Logosforge folder or create an installer.
    echo.
    echo === Create ZIP ^(optional^) ===
    echo   powershell Compress-Archive -Path dist\Logosforge -DestinationPath dist\Logosforge-win-x64.zip
) else (
    echo.
    echo [5/5] Build failed — dist\Logosforge\Logosforge.exe not found.
    exit /b 1
)

call deactivate 2>nul

endlocal
