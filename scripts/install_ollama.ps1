# ═══════════════════════════════════════════════════════════
# Neuron — Smart Ollama Installer
# ═══════════════════════════════════════════════════════════
# Checks if Ollama is already installed anywhere on the system.
# If found, skips download. If not found, downloads and installs.
# Runs silently during Neuron installation.
# ═══════════════════════════════════════════════════════════

param(
    [string]$TempDir = $env:TEMP
)

$ErrorActionPreference = "SilentlyContinue"

Write-Host "═══════════════════════════════════════"
Write-Host "  Neuron — Ollama Detection & Install"
Write-Host "═══════════════════════════════════════"

# ── Step 1: Check if ollama is already in PATH ──
$ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaCmd) {
    Write-Host "[OK] Ollama found in PATH: $($ollamaCmd.Source)"
    Write-Host "Skipping download."
    exit 0
}

# ── Step 2: Search common install locations ──
Write-Host "[...] Ollama not in PATH. Searching common locations..."

$searchPaths = @(
    "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",
    "$env:LOCALAPPDATA\Ollama\ollama.exe",
    "$env:ProgramFiles\Ollama\ollama.exe",
    "${env:ProgramFiles(x86)}\Ollama\ollama.exe",
    "$env:USERPROFILE\Ollama\ollama.exe",
    "$env:USERPROFILE\AppData\Local\Programs\Ollama\ollama.exe",
    "C:\Ollama\ollama.exe",
    "D:\Ollama\ollama.exe"
)

$foundPath = $null
foreach ($path in $searchPaths) {
    if (Test-Path $path) {
        $foundPath = $path
        break
    }
}

# ── Step 3: Deep search (registry) ──
if (-not $foundPath) {
    Write-Host "[...] Checking Windows registry..."
    $regPaths = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )
    foreach ($regPath in $regPaths) {
        $entries = Get-ItemProperty $regPath -ErrorAction SilentlyContinue | 
                   Where-Object { $_.DisplayName -like "*Ollama*" }
        if ($entries) {
            $installLoc = $entries[0].InstallLocation
            if ($installLoc -and (Test-Path "$installLoc\ollama.exe")) {
                $foundPath = "$installLoc\ollama.exe"
                break
            }
        }
    }
}

# ── Step 4: Quick filesystem scan ──
if (-not $foundPath) {
    Write-Host "[...] Quick filesystem scan..."
    $found = Get-ChildItem -Path "C:\Users\$env:USERNAME" -Filter "ollama.exe" -Recurse -Depth 5 -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) {
        $foundPath = $found.FullName
    }
}

# ── Result ──
if ($foundPath) {
    Write-Host ""
    Write-Host "[OK] Ollama FOUND at: $foundPath"
    Write-Host "Skipping download. Adding to PATH for this session..."
    $ollamaDir = Split-Path $foundPath -Parent
    $env:Path = "$ollamaDir;$env:Path"
    Write-Host "[OK] Ollama is ready."
    exit 0
}

# ── Step 5: Not found — download and install ──
Write-Host ""
Write-Host "[!!] Ollama NOT found on this system."
Write-Host "[...] Downloading Ollama installer..."

$downloadUrl = "https://ollama.com/download/OllamaSetup.exe"
$installerPath = Join-Path $TempDir "OllamaSetup.exe"

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $downloadUrl -OutFile $installerPath -UseBasicParsing
    Write-Host "[OK] Downloaded to: $installerPath"
} catch {
    Write-Host "[ERROR] Download failed: $_"
    Write-Host "You can install Ollama manually from: https://ollama.com/download"
    exit 1
}

# Verify download
if (-not (Test-Path $installerPath)) {
    Write-Host "[ERROR] Installer file not found after download."
    exit 1
}

$fileSize = [math]::Round((Get-Item $installerPath).Length / 1MB, 1)
Write-Host "[OK] Installer size: $fileSize MB"

if ($fileSize -lt 5) {
    Write-Host "[ERROR] Download appears incomplete (< 5MB). Aborting."
    exit 1
}

# Install silently
Write-Host "[...] Installing Ollama silently..."
try {
    Start-Process $installerPath -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" -Wait -NoNewWindow
    Write-Host "[OK] Ollama installed successfully!"
} catch {
    Write-Host "[ERROR] Installation failed: $_"
    exit 1
}

# Verify installation
Start-Sleep 3
$verifyCmd = Get-Command ollama -ErrorAction SilentlyContinue
if ($verifyCmd) {
    Write-Host "[OK] Verified: ollama is now available at $($verifyCmd.Source)"
} else {
    Write-Host "[WARN] Ollama installed but not yet in PATH. A restart may be needed."
}

Write-Host ""
Write-Host "═══════════════════════════════════════"
Write-Host "  Installation complete!"
Write-Host "═══════════════════════════════════════"
exit 0
