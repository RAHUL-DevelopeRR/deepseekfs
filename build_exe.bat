@echo off
setlocal
echo.
echo =====================================================
echo   DeepSeekFS v2.0 — Windows .exe Builder
echo =====================================================
echo.

REM ─ Step 1: verify we are in the project root
if not exist run_desktop.py (
    echo ERROR: run this script from the deepseekfs project root.
    pause & exit /b 1
)

REM ─ Step 2: install deps
echo [1/3] Installing requirements...
pip install -r requirements-desktop.txt
if errorlevel 1 ( echo Install failed. Activate your venv first! & pause & exit /b 1 )

REM ─ Step 3: build
echo.
echo [2/3] Building executable with PyInstaller...
pyinstaller --noconfirm --onedir --windowed ^
    --name "DeepSeekFS" ^
    --add-data "core;core" ^
    --add-data "services;services" ^
    --add-data "app;app" ^
    --add-data ".env.example;." ^
    --hidden-import "sentence_transformers" ^
    --hidden-import "faiss" ^
    --hidden-import "PyQt6" ^
    --hidden-import "PyQt6.QtWidgets" ^
    --hidden-import "PyQt6.QtCore" ^
    --hidden-import "PyQt6.QtGui" ^
    run_desktop.py

if errorlevel 1 ( echo Build failed! See above for errors. & pause & exit /b 1 )

echo.
echo [3/3] Done!
echo.
echo   Your executable: dist\DeepSeekFS\DeepSeekFS.exe
echo   Distribute the entire folder: dist\DeepSeekFS\
echo.
pause
