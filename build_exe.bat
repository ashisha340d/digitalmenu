@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Digital Menu - Building DigitalMenuLauncher.exe
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b 1
)

echo Installing build dependencies...
python -m pip install --quiet --upgrade pyinstaller pystray Pillow openpyxl
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

echo Building...
python -m PyInstaller --noconsole --onefile --name DigitalMenuLauncher ^
    --distpath . --workpath build --specpath build ^
    TrayLauncher.pyw
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo Done. DigitalMenuLauncher.exe was created in this folder.
echo   - menu_server.py, Menu.xlsx, admin.html, digital-menu.html, images\, config.json
echo     must stay alongside the .exe (they are not bundled into it).
echo   - The "build" folder can be deleted; it is build scratch space only.
echo.
pause
endlocal
