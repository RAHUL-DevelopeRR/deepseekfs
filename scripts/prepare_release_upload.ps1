param(
    [Parameter(Mandatory = $true)]
    [string]$AssetPath,

    [Parameter(Mandatory = $true)]
    [string]$UploadDir
)

$ErrorActionPreference = "Stop"
$chunkBytes = [int64]($env:NEUCOCKPIT_RELEASE_CHUNK_BYTES)
if ($chunkBytes -le 0) {
    $chunkBytes = 1900000000
}

$asset = Get-Item -LiteralPath $AssetPath
New-Item -ItemType Directory -Force -Path $UploadDir | Out-Null

$baseName = $asset.Name
$hash = Get-FileHash -LiteralPath $asset.FullName -Algorithm SHA256
"$($hash.Hash.ToLowerInvariant())  $baseName" |
    Set-Content -Encoding ascii -LiteralPath (Join-Path $UploadDir "$baseName.sha256")

if ($asset.Length -le $chunkBytes) {
    Copy-Item -LiteralPath $asset.FullName -Destination (Join-Path $UploadDir $baseName) -Force
} else {
    $buffer = New-Object byte[] (4MB)
    $inputStream = [System.IO.File]::OpenRead($asset.FullName)
    try {
        $part = 0
        while ($inputStream.Position -lt $inputStream.Length) {
            $partName = "{0}.part-{1:000}" -f $baseName, $part
            $partPath = Join-Path $UploadDir $partName
            $outputStream = [System.IO.File]::Create($partPath)
            try {
                $written = [int64]0
                while ($written -lt $chunkBytes -and $inputStream.Position -lt $inputStream.Length) {
                    $want = [Math]::Min($buffer.Length, $chunkBytes - $written)
                    $read = $inputStream.Read($buffer, 0, [int]$want)
                    if ($read -le 0) {
                        break
                    }
                    $outputStream.Write($buffer, 0, $read)
                    $written += $read
                }
            }
            finally {
                $outputStream.Dispose()
            }
            $part++
        }
    }
    finally {
        $inputStream.Dispose()
    }

    @"
NeuCockpit v1.0 asset is split because GitHub Release assets must be under 2 GiB.

Original file:
$baseName

Reassemble on Windows PowerShell:
Get-Content -Encoding Byte -ReadCount 0 $baseName.part-* | Set-Content -Encoding Byte $baseName
Get-FileHash $baseName -Algorithm SHA256

Reassemble on Linux/macOS:
cat $baseName.part-* > $baseName
shasum -a 256 -c $baseName.sha256

Expected SHA256 is in:
$baseName.sha256
"@ | Set-Content -Encoding ascii -LiteralPath (Join-Path $UploadDir "$baseName.REASSEMBLE.txt")
}

Get-ChildItem -LiteralPath $UploadDir -File | Sort-Object Name | Select-Object Name,Length
