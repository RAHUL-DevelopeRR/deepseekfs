$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$sourceRoots = @(
    "app",
    "core",
    "docs",
    "scripts",
    "services",
    "tests",
    "ui"
)

$topLevelGenerated = @(
    ".pytest_cache",
    "build",
    "dist",
    "installer_output"
)

foreach ($name in $topLevelGenerated) {
    $target = Join-Path $repoRoot $name
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
        Write-Host "Removed $target"
    }
}

foreach ($name in $sourceRoots) {
    $root = Join-Path $repoRoot $name
    if (-not (Test-Path -LiteralPath $root)) {
        continue
    }

    Get-ChildItem -LiteralPath $root -Recurse -Directory -Force |
        Where-Object { $_.Name -eq "__pycache__" } |
        ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force
            Write-Host "Removed $($_.FullName)"
        }

    Get-ChildItem -LiteralPath $root -Recurse -File -Force -Filter *.pyc |
        ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Force
            Write-Host "Removed $($_.FullName)"
        }
}
