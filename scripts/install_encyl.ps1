# ═══════════════════════════════════════════════════════════════
# DeepSeekFS — Encyl AI Setup Script (PowerShell)
# ═══════════════════════════════════════════════════════════════
# This script installs Ollama and pulls the llama3.2:3b model
# for the Encyl intelligent file summarization engine.
# Can be called from Inno Setup, NSIS, or PyInstaller post-install.
# ═══════════════════════════════════════════════════════════════

param(
    [switch]$Silent,           # Run without user prompts
    [switch]$SkipInstall,      # Skip Ollama installation (just pull model)
    [string]$Model = "llama3.2:3b"   # Model to install
)

$ErrorActionPreference = "Continue"
$OllamaUrl = "https://ollama.com/download/OllamaSetup.exe"
$OllamaInstaller = Join-Path $env:TEMP "OllamaSetup.exe"

function Write-Header {
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║     DeepSeekFS — Encyl AI Engine Setup          ║" -ForegroundColor Cyan
    Write-Host "  ║     Powered by Ollama + Llama 3.2               ║" -ForegroundColor Cyan
    Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Test-OllamaInstalled {
    try {
        $null = Get-Command ollama -ErrorAction Stop
        return $true
    } catch {
        # Also check default install location
        $defaultPath = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
        if (Test-Path $defaultPath) {
            $env:PATH += ";$(Split-Path $defaultPath)"
            return $true
        }
        return $false
    }
}

function Test-OllamaRunning {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Test-ModelInstalled {
    param([string]$ModelName)
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 3
        $data = $response.Content | ConvertFrom-Json
        foreach ($m in $data.models) {
            if ($m.name -like "*$ModelName*") { return $true }
        }
        return $false
    } catch {
        return $false
    }
}

function Install-Ollama {
    Write-Host "  [1/4] Downloading Ollama installer..." -ForegroundColor Yellow
    
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $OllamaUrl -OutFile $OllamaInstaller -UseBasicParsing
    } catch {
        Write-Host "  ✗ Download failed: $_" -ForegroundColor Red
        Write-Host "  Please install manually: https://ollama.com/download" -ForegroundColor Yellow
        return $false
    }
    
    if (-not (Test-Path $OllamaInstaller)) {
        Write-Host "  ✗ Installer not found after download." -ForegroundColor Red
        return $false
    }
    
    Write-Host "  [2/4] Installing Ollama..." -ForegroundColor Yellow
    
    if ($Silent) {
        Start-Process -FilePath $OllamaInstaller -ArgumentList "/S" -Wait -NoNewWindow
    } else {
        Start-Process -FilePath $OllamaInstaller -Wait
    }
    
    # Refresh PATH
    $env:PATH += ";$env:LOCALAPPDATA\Programs\Ollama"
    
    # Clean up installer
    Remove-Item $OllamaInstaller -Force -ErrorAction SilentlyContinue
    
    if (Test-OllamaInstalled) {
        Write-Host "  ✓ Ollama installed successfully." -ForegroundColor Green
        return $true
    } else {
        Write-Host "  ✗ Installation verification failed." -ForegroundColor Red
        return $false
    }
}

function Start-OllamaServer {
    Write-Host "  [3/4] Starting Ollama server..." -ForegroundColor Yellow
    
    if (Test-OllamaRunning) {
        Write-Host "  ✓ Server already running." -ForegroundColor Green
        return $true
    }
    
    # Start Ollama serve in background
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    
    # Wait for server to be ready (up to 15 seconds)
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        if (Test-OllamaRunning) {
            Write-Host "  ✓ Server started." -ForegroundColor Green
            return $true
        }
    }
    
    Write-Host "  ⚠ Server start timeout. It may still be loading." -ForegroundColor Yellow
    return $false
}

function Install-Model {
    param([string]$ModelName)
    
    if (Test-ModelInstalled -ModelName $ModelName) {
        Write-Host "  ✓ Model '$ModelName' already installed." -ForegroundColor Green
        return $true
    }
    
    Write-Host "  [4/4] Pulling model: $ModelName (~2GB, one-time download)..." -ForegroundColor Yellow
    Write-Host ""
    
    & ollama pull $ModelName
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "  ✓ Model installed successfully." -ForegroundColor Green
        return $true
    } else {
        Write-Host "  ✗ Model pull failed. Retry: ollama pull $ModelName" -ForegroundColor Red
        return $false
    }
}

# ═══════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════

Write-Header

$success = $true

# Step 1-2: Install Ollama if needed
if (-not $SkipInstall) {
    if (Test-OllamaInstalled) {
        Write-Host "  [1/4] ✓ Ollama already installed." -ForegroundColor Green
        Write-Host "  [2/4] Skipping installation." -ForegroundColor DarkGray
    } else {
        if (-not (Install-Ollama)) {
            $success = $false
        }
    }
}

# Step 3: Start server
if ($success) {
    if (-not (Start-OllamaServer)) {
        Write-Host "  ⚠ Continuing anyway..." -ForegroundColor Yellow
    }
}

# Step 4: Pull model
if ($success) {
    if (-not (Install-Model -ModelName $Model)) {
        $success = $false
    }
}

# Summary
Write-Host ""
if ($success) {
    Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "  ║  ✓ Encyl AI Engine installed successfully!      ║" -ForegroundColor Green
    Write-Host "  ║                                                  ║" -ForegroundColor Green
    Write-Host "  ║  Usage in DeepSeekFS:                           ║" -ForegroundColor Green
    Write-Host "  ║  • Type ? before query to ask Encyl             ║" -ForegroundColor Green
    Write-Host "  ║  • Press Tab on any result to summarize         ║" -ForegroundColor Green
    Write-Host "  ║  • Press Ctrl+I as alternate summarize key      ║" -ForegroundColor Green
    Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Green
} else {
    Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Yellow
    Write-Host "  ║  ⚠ Setup completed with warnings.              ║" -ForegroundColor Yellow
    Write-Host "  ║  DeepSeekFS will work without AI features.      ║" -ForegroundColor Yellow
    Write-Host "  ║  Re-run this script to retry AI setup.          ║" -ForegroundColor Yellow
    Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Yellow
}
Write-Host ""

if (-not $Silent) {
    Read-Host "  Press Enter to continue"
}

# Return status for installer integration
exit ([int](-not $success))
