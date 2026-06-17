param(
    [ValidateSet("x64", "arm64")]
    [string]$Arch = "x64"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $Root
try {
    python -m pip install --upgrade pip

    $req = Join-Path $env:TEMP "requirements-windows-$Arch.txt"
    Get-Content requirements.txt |
        Where-Object {
            $_ -notmatch '^\s*pyaudiowpatch' -and
            $_ -notmatch '^\s*vosk' -and
            $_ -notmatch '^\s*pywin32\b'
        } |
        Set-Content -Encoding ascii $req

    python -m pip install -r $req pyinstaller

    if ($env:NEURON_SKIP_QWEN_GGUF -ne "1") {
        python -c "from services.model_manager import download_llm_model; download_llm_model()"
    }

    python -m PyInstaller neuron_onedir.spec --noconfirm

    New-Item -ItemType Directory -Force -Path dist\release | Out-Null
    $zip = "dist\release\NeuCockpit-v1.0-windows-$Arch.zip"
    if (Test-Path $zip) {
        Remove-Item -LiteralPath $zip -Force
    }

    $sevenZip = Get-Command 7z.exe -ErrorAction SilentlyContinue
    if ($sevenZip) {
        & $sevenZip.Source a -tzip -mx=5 $zip ".\dist\Neuron\*" | Out-Host
    } else {
        python -c "import pathlib, zipfile; root=pathlib.Path('dist/Neuron'); out=pathlib.Path(r'$zip'); z=zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,allowZip64=True); [z.write(p, p.relative_to(root.parent).as_posix()) for p in root.rglob('*') if p.is_file()]; z.close()"
    }

    $uploadDir = "dist\release\upload"
    if (Test-Path $uploadDir) {
        Remove-Item -LiteralPath $uploadDir -Recurse -Force
    }
    & "$PSScriptRoot\prepare_release_upload.ps1" -AssetPath $zip -UploadDir $uploadDir
}
finally {
    Pop-Location
}
