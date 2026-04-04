param (
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$false)]
    [string]$BaseBranch = "dv-4"
)

# 1. Update version.py
Write-Host "[1/9] Bumping version to $Version..."
$versionFile = "version.py"
if (Test-Path $versionFile) {
    (Get-Content $versionFile) -replace '^__version__\s*=.*', "__version__ = `"$Version`"" | Set-Content $versionFile
} else {
    Out-File -FilePath $versionFile -InputObject "__version__ = `"$Version`"" -Encoding utf8
}

# 2. Branching
$branchName = "dv-$Version"
Write-Host "[2/9] Creating or switching to branch $branchName..."
# Fetch the latest so we base off main if we want, or just branch from current
git checkout -b $branchName

# 3. Generate ISS
Write-Host "[3/9] Generating neuron_installer.iss from template..."
python scripts\generate_iss.py
if ($LASTEXITCODE -ne 0) { Write-Error "ISS generation failed"; exit 1 }

# 4. Build Pyinstaller app
Write-Host "[4/9] Building PyInstaller package (this will take a while)..."
pyinstaller neuron.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller build failed"; exit 1 }

# 5. Compile Inno Setup
Write-Host "[5/9] Compiling Inno Setup installer..."
$isccPath = ""
$possiblePaths = @(
    "C:\Users\$env:USERNAME\AppData\Local\Programs\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
foreach ($p in $possiblePaths) {
    if (Test-Path $p) {
        $isccPath = $p
        break
    }
}
if ($isccPath -eq "") {
    Write-Error "ISCC.exe not found! Please ensure Inno Setup 6 is installed."
    exit 1
}

& $isccPath "neuron_installer.iss"
if ($LASTEXITCODE -ne 0) { Write-Error "Inno Setup compilation failed"; exit 1 }

# 6. Commit changes (only code files, not the binary)
Write-Host "[6/9] Committing version changes..."
git add version.py neuron_installer.iss scripts/generate_iss.py neuron_installer.iss.template scripts/release.ps1
git commit -m "build: automated release preparation for v$Version"

# 7. Push branch
Write-Host "[7/9] Pushing to GitHub..."
git push --set-upstream origin $branchName

# 8. Create PR
Write-Host "[8/9] Creating Pull Request..."
gh pr create --base $BaseBranch --head $branchName --title "Release v$Version" --body "Automated release build for version $Version."

# 9. GitHub Release (Published)
Write-Host "[9/9] Creating GitHub Release with installer..."
$installerExe = "installer_output\NeuronSetup_v$Version.exe"
if (Test-Path $installerExe) {
    gh release create "v$Version" $installerExe --title "Neuron v$Version" --notes "Release v$Version" -R "RAHUL-DevelopeRR/deepseekfs"
    Write-Host "✅ Release published successfully!"
} else {
    Write-Error "Installer executable not found at $installerExe"
    exit 1
}

Write-Host "🎉 Pipeline complete!"
