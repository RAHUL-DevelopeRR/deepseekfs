@echo off
:: ═══════════════════════════════════════════════════════════════
:: DeepSeekFS — Encyl AI Setup Script
:: ═══════════════════════════════════════════════════════════════
:: This script installs Ollama and pulls the llama3.2:3b model
:: for the Encyl intelligent file summarization engine.
:: Run this during installation or first launch.
:: ═══════════════════════════════════════════════════════════════

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║     DeepSeekFS — Encyl AI Engine Setup          ║
echo  ║     Powered by Ollama + Llama 3.2               ║
echo  ╚══════════════════════════════════════════════════╝
echo.

:: ── Step 1: Check if Ollama is already installed ──────────────
echo [1/4] Checking for Ollama installation...
where ollama >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo       ✓ Ollama is already installed.
    goto :check_running
)

:: ── Step 2: Download and install Ollama ───────────────────────
echo       Ollama not found. Downloading installer...
echo.

set OLLAMA_INSTALLER=%TEMP%\OllamaSetup.exe
set OLLAMA_URL=https://ollama.com/download/OllamaSetup.exe

:: Download using PowerShell (reliable on all Windows versions)
powershell -Command "& { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%OLLAMA_URL%' -OutFile '%OLLAMA_INSTALLER%' -UseBasicParsing }"

if not exist "%OLLAMA_INSTALLER%" (
    echo       ✗ Download failed. Please install Ollama manually from:
    echo         https://ollama.com/download
    echo.
    pause
    exit /b 1
)

echo [2/4] Installing Ollama (this may take a minute)...
echo       Please follow the Ollama installer prompts.
start /wait "" "%OLLAMA_INSTALLER%"

:: Verify installation
where ollama >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    :: Try adding default install path
    set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Ollama"
    where ollama >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo       ✗ Ollama installation not detected.
        echo         Please restart your terminal and try again.
        pause
        exit /b 1
    )
)

echo       ✓ Ollama installed successfully.
echo.

:: ── Step 3: Start Ollama server if not running ────────────────
:check_running
echo [3/4] Starting Ollama server...

:: Check if already running
powershell -Command "try { (Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -UseBasicParsing -TimeoutSec 3).StatusCode } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo       ✓ Ollama server is already running.
    goto :pull_model
)

:: Start Ollama in background
start "" /B ollama serve
echo       Waiting for server to start...
timeout /t 5 /nobreak >nul

:: Verify it's running
powershell -Command "try { (Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -UseBasicParsing -TimeoutSec 5).StatusCode } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo       ⚠ Server didn't start. Trying again...
    timeout /t 5 /nobreak >nul
)

echo       ✓ Ollama server running.
echo.

:: ── Step 4: Pull the AI model ─────────────────────────────────
:pull_model
echo [4/4] Downloading Encyl AI model (llama3.2:3b, ~2GB)...
echo       This is a one-time download. Please wait...
echo.

ollama pull llama3.2:3b

if %ERRORLEVEL% EQU 0 (
    echo.
    echo  ╔══════════════════════════════════════════════════╗
    echo  ║     ✓ Encyl AI Engine installed successfully!   ║
    echo  ║                                                  ║
    echo  ║     How to use:                                  ║
    echo  ║     • Type ? before your query to ask Encyl     ║
    echo  ║     • Press Tab on any result to summarize      ║
    echo  ║     • Encyl understands your files locally      ║
    echo  ╚══════════════════════════════════════════════════╝
    echo.
) else (
    echo.
    echo       ✗ Model download failed. You can retry later:
    echo         ollama pull llama3.2:3b
    echo.
)

del "%OLLAMA_INSTALLER%" 2>nul
pause
