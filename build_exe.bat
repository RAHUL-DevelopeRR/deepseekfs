@echo off
echo =============================================
echo   DeepSeekFS v2.0 - Windows EXE Builder
echo =============================================
echo.

echo [1/3] Installing desktop requirements...
pip install -r requirements-desktop.txt
if errorlevel 1 (
    echo ERROR: pip install failed. Activate your venv first!
    pause
    exit /b 1
)

echo.
echo [2/3] Building .exe with PyInstaller...
pyinstaller --noconfirm --onedir --windowed ^
    --name "DeepSeekFS" ^
    --add-data "core;core" ^
    --add-data "services;services" ^
    --add-data "app;app" ^
    --add-data ".env.example;." ^
    --hidden-import sentence_transformers ^
    --hidden-import faiss ^
    --hidden-import PyQt6 ^
    run_desktop.py

if errorlevel 1 (
    echo ERROR: PyInstaller build failed!
    pause
    exit /b 1
)

echo.
echo [3/3] Build complete!
echo.
echo Your .exe is located at:
echo   dist\DeepSeekFS\DeepSeekFS.exe
echo.
echo Share the entire 'dist\DeepSeekFS' folder with users.
pause
