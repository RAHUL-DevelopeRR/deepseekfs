param(
    [ValidateSet("x64", "arm64")]
    [string]$Arch = "x64"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $Root
try {
    python -m pip install --upgrade pip setuptools wheel

    $req = Join-Path $env:TEMP "requirements-windows-$Arch.txt"
    $lines = Get-Content requirements.txt |
        Where-Object {
            $_ -notmatch '^\s*pyaudiowpatch' -and
            $_ -notmatch '^\s*vosk' -and
            $_ -notmatch '^\s*pywin32\b'
        }

    if ($Arch -eq "arm64") {
        $lines = $lines | Where-Object {
            $_ -notmatch '^\s*--extra-index-url' -and
            $_ -notmatch '^\s*numpy==' -and
            $_ -notmatch '^\s*PyMuPDF==' -and
            $_ -notmatch '^\s*watchdog==' -and
            $_ -notmatch '^\s*PyYAML==' -and
            $_ -notmatch '^\s*cryptography==' -and
            $_ -notmatch '^\s*torch==' -and
            $_ -notmatch '^\s*transformers==' -and
            $_ -notmatch '^\s*sentence-transformers==' -and
            $_ -notmatch '^\s*safetensors==' -and
            $_ -notmatch '^\s*spacy' -and
            $_ -notmatch '^\s*tokenizers==' -and
            $_ -notmatch '^\s*llama-cpp-python'
        }
    }

    $lines | Set-Content -Encoding ascii $req

    if ($Arch -eq "arm64") {
        python -m pip install --prefer-binary `
            numpy `
            PyQt6==6.10.2 `
            PyQt6-Qt6==6.10.2 `
            PyQt6_sip==13.11.1 `
            onnxruntime `
            tokenizers `
            faiss-cpu==1.13.2 `
            scipy==1.17.1 `
            scikit-learn==1.8.0 `
            cryptography `
            huggingface_hub==0.36.2 `
            pyinstaller `
            cmake `
            ninja
    }

    python -m pip install -r $req pyinstaller

    if ($Arch -eq "arm64") {
        $clang = Get-Command clang-cl.exe -ErrorAction SilentlyContinue
        if (-not $clang) {
            $clang = Get-ChildItem "${env:ProgramFiles}\Microsoft Visual Studio" -Recurse -Filter clang-cl.exe -ErrorAction SilentlyContinue |
                Where-Object { $_.FullName -match '\\Llvm\\ARM64\\bin\\clang-cl\.exe$' } |
                Select-Object -First 1
        }
        if (-not $clang) {
            throw "clang-cl.exe was not found. Windows ARM64 llama.cpp builds require clang."
        }
        $clangPath = if ($clang.Source) { $clang.Source } else { $clang.FullName }
        $env:CC = $clangPath
        $env:CXX = $clangPath
        $env:CMAKE_GENERATOR = "Ninja"
        $env:CMAKE_ARGS = "-DGGML_NATIVE=OFF -DGGML_OPENMP=OFF -DCMAKE_C_COMPILER=`"$clangPath`" -DCMAKE_CXX_COMPILER=`"$clangPath`""
        $env:FORCE_CMAKE = "1"
        python -m pip install --no-cache-dir llama-cpp-python
    }

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
