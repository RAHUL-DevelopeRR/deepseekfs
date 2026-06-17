param(
    [switch]$SkipPyInstaller,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Iss = Join-Path $Root "neuron_installer.iss"

function Find-Iscc {
    $cmd = Get-Command "iscc.exe" -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    throw "Inno Setup 6 compiler was not found. Install Inno Setup, then rerun this script."
}

Push-Location $Root
try {
    if (-not $SkipPyInstaller -and -not $SkipInstaller) {
        & "$PSScriptRoot\build_neucockpit_windows.ps1" -Arch x64 -Package installer
        return
    }

    if (-not $SkipPyInstaller) {
        if ($env:NEURON_SKIP_PIP_INSTALL -ne "1") {
            python -m pip install --upgrade pip
            $env:NEURON_SKIP_QWEN_GGUF = "0"
            & "$PSScriptRoot\build_neucockpit_windows.ps1" -Arch x64 -Package zip
            return
        }
        python -c "from services.model_manager import download_llm_model; download_llm_model()"
        $env:NEURON_SKIP_QWEN_GGUF = "0"
        pyinstaller neuron_onedir.spec --noconfirm
    }

    if (-not $SkipInstaller) {
        $iscc = Find-Iscc
        & $iscc $Iss
    }
}
finally {
    Pop-Location
}
