# Runs Apktool + JADX entirely in Docker Desktop. Nothing is installed on Windows.
# Usage (from anywhere):
# powershell -ExecutionPolicy Bypass -File .\v31\diagnostics\decompile\run.ps1
# Optional: -InputPath C:\path\twitch.apkm -OutputDirectory C:\path\decoded
param(
    [string]$InputPath = '',
    [string]$OutputDirectory = ''
)
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $scriptDir '..\..\..'))
if (-not $InputPath) {
    foreach ($name in @('twitch.zip', 'twitch.apkm', 'twitch.apk')) {
        $candidate = Join-Path $repoRoot $name
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $InputPath = $candidate
            break
        }
    }
}
if (-not $InputPath) {
    throw "No input found. Put the ORIGINAL Twitch 31.8.0 twitch.zip / twitch.apkm / twitch.apk in $repoRoot or pass -InputPath."
}
$source = Get-Item -LiteralPath $InputPath -ErrorAction Stop
if ($source.PSIsContainer) { throw 'Input must be an APK/APKM/ZIP file, not a directory.' }
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repoRoot 'dist\twitch318-decompiled'
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$destination = Get-Item -LiteralPath $OutputDirectory -ErrorAction Stop
$inputMount = "type=bind,source=$($source.FullName),target=/input/twitch.zip,readonly"
$outputMount = "type=bind,source=$($destination.FullName),target=/out"
$image = 'bttv-twitch-decompiler:31.8.0'

Write-Host "Input: $($source.FullName)"
Write-Host "Output: $($destination.FullName)"
Write-Host 'Building isolated decompiler tool image (no changes to BTTV builder)...'
& docker build -f (Join-Path $scriptDir 'Dockerfile') -t $image $scriptDir
if ($LASTEXITCODE -ne 0) { throw 'Docker decompiler image build failed.' }

Write-Host 'Running Apktool and JADX against the original input bundle...'
& docker run --rm --mount $inputMount --mount $outputMount $image --input /input/twitch.zip --output /out
if ($LASTEXITCODE -ne 0) { throw 'Decompilation failed. Check the logs in the output folder.' }

Write-Host ''
Write-Host "DONE. Full decompilation: $($destination.FullName)" -ForegroundColor Green
Write-Host "Upload this file after inspection: $(Join-Path $destination.FullName 'chat-restore-review.zip')" -ForegroundColor Green
Write-Host 'The original APK was mounted read-only and no user data was read from the phone.'
