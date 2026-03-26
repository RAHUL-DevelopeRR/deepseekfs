@echo off
setlocal
echo.
echo =====================================================
echo   DeepSeekFS v3.0 — Windows .exe Builder
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
echo     This may take several minutes on first run.
echo.
pyinstaller --noconfirm --onedir --windowed ^
    --name "DeepSeekFS" ^
    --add-data "core;core" ^
    --add-data "services;services" ^
    --add-data "app;app" ^
    --hidden-import "sentence_transformers" ^
    --hidden-import "sentence_transformers.models" ^
    --hidden-import "sentence_transformers.util" ^
    --hidden-import "faiss" ^
    --hidden-import "torch" ^
    --hidden-import "torch.nn" ^
    --hidden-import "torch.nn.functional" ^
    --hidden-import "transformers" ^
    --hidden-import "transformers.models" ^
    --hidden-import "tokenizers" ^
    --hidden-import "tqdm" ^
    --hidden-import "huggingface_hub" ^
    --hidden-import "sklearn" ^
    --hidden-import "sklearn.utils" ^
    --hidden-import "sklearn.metrics" ^
    --hidden-import "sklearn.metrics.pairwise" ^
    --hidden-import "PyQt6" ^
    --hidden-import "PyQt6.QtWidgets" ^
    --hidden-import "PyQt6.QtCore" ^
    --hidden-import "PyQt6.QtGui" ^
    --hidden-import "PyQt6.sip" ^
    --hidden-import "watchdog" ^
    --hidden-import "watchdog.observers" ^
    --hidden-import "watchdog.events" ^
    --hidden-import "dateparser" ^
    --hidden-import "orjson" ^
    --hidden-import "joblib" ^
    --hidden-import "docx" ^
    --hidden-import "fitz" ^
    --hidden-import "pdfminer" ^
    --hidden-import "openpyxl" ^
    --hidden-import "pptx" ^
    --collect-data "sentence_transformers" ^
    --collect-data "transformers" ^
    --collect-data "tokenizers" ^
    --collect-data "tqdm" ^
    run_desktop.py

if errorlevel 1 ( echo Build failed! See above for errors. & pause & exit /b 1 )

echo.
echo [3/3] Done!
echo.
echo   Your executable: dist\DeepSeekFS\DeepSeekFS.exe
echo   Distribute the entire folder: dist\DeepSeekFS\
echo.
echo   Just double-click DeepSeekFS.exe to run!
echo   Press Shift+Space to toggle the search panel.
echo.
pause
