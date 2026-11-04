# Diagnostic build of the currently applying patches; temporarily excludes
# cl2.smali.patch, r2k.smali.patch and zy_gif_modes.patch.
# Each run uses a unique output directory. Restores the original patches.
# The diagnostic APK is INCOMPLETE and must not be installed/distributed.

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false

$repo = (Get-Location).Path
$patchDir = Join-Path $repo 'patches\live'
$patchNames = @('cl2.smali.patch', 'r2k.smali.patch', 'zy_gif_modes.patch')
foreach ($name in $patchNames) {
    if (-not (Test-Path -LiteralPath (Join-Path $patchDir $name))) {
        throw "Missing patches\live\$name. Run this script from the repository root."
    }
}

# Catch the common case where the previous pb6 register fix was not installed.
$rewritePatch = Join-Path $patchDir 'z86.smali.patch'
if ((Test-Path -LiteralPath $rewritePatch) -and
    -not (Select-String -LiteralPath $rewritePatch -Pattern 'invoke-virtual/range' -Quiet)) {
    Write-Warning 'z86.smali.patch has no invoke-virtual/range. Verify the pb6 register fix is installed before this probe.'
}

$runId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$dist = Join-Path $repo 'dist'
New-Item -ItemType Directory -Path $dist -Force | Out-Null

# IMPORTANT: Do not create this path. The production builder requires a NEW
# workspace and output; a reused path fails before patching or compilation.
$outputRelative = "./dist/docker-full-build-probe-$runId"
$outputAbsolute = Join-Path $dist "docker-full-build-probe-$runId"
$stash = Join-Path $dist "port-probe-stash-$runId"
$consoleLog = Join-Path $dist "twitch318-probe-$runId-console.log"
$evidenceDir = Join-Path $dist "twitch318-probe-evidence-$runId"
$evidenceZip = Join-Path $dist "twitch318-build-evidence-$runId.zip"

New-Item -ItemType Directory -Path $stash | Out-Null
$previousOutput = [Environment]::GetEnvironmentVariable('BTTV_OUTPUT_DIR', 'Process')
$saved = @()
$exitCode = $null
$exceptionText = $null

try {
    foreach ($name in $patchNames) {
        Move-Item -LiteralPath (Join-Path $patchDir $name) `
            -Destination (Join-Path $stash $name) -ErrorAction Stop
        $saved += $name
    }

    $env:BTTV_OUTPUT_DIR = $outputRelative
    Write-Host "Run ID: $runId"
    Write-Host "Fresh Docker output: $outputRelative"
    Write-Warning 'The three failing patches are temporarily excluded. Any APK produced is incomplete.'
    & docker compose run --rm build 2>&1 | Tee-Object -FilePath $consoleLog
    $exitCode = $LASTEXITCODE
}
catch {
    $exceptionText = $_.ToString()
    Write-Warning "Probe command error: $exceptionText"
}
finally {
    foreach ($name in $saved) {
        $backupFile = Join-Path $stash $name
        if (Test-Path -LiteralPath $backupFile) {
            Move-Item -LiteralPath $backupFile `
                -Destination (Join-Path $patchDir $name) -Force
        }
    }
    if ($null -eq $previousOutput) {
        Remove-Item Env:BTTV_OUTPUT_DIR -ErrorAction SilentlyContinue
    }
    else {
        $env:BTTV_OUTPUT_DIR = $previousOutput
    }
    if (Test-Path -LiteralPath $stash) {
        $remaining = @(Get-ChildItem -LiteralPath $stash -Force)
        if ($remaining.Count -eq 0) {
            Remove-Item -LiteralPath $stash -Force
        }
        else {
            Write-Warning "Files remain in backup stash: $stash"
        }
    }
    Write-Host 'Original patch files restored (unless a stash warning was printed).'
}

# Package evidence from THIS run, not from any earlier, stale build directory.
New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
if (Test-Path -LiteralPath $consoleLog) {
    Copy-Item -LiteralPath $consoleLog `
        -Destination (Join-Path $evidenceDir 'probe-console.log')
}
$logs = @()
if (Test-Path -LiteralPath $outputAbsolute) {
    $logs = @(Get-ChildItem -LiteralPath $outputAbsolute -Recurse -File `
        -Filter 'build.log' -ErrorAction SilentlyContinue |
        Sort-Object -Property LastWriteTime -Descending)
}
$internalFound = $logs.Count -gt 0
if ($internalFound) {
    $log = $logs[0]
    Copy-Item -LiteralPath $log.FullName `
        -Destination (Join-Path $evidenceDir 'build.log')
    Write-Host "Internal log from THIS run: $($log.FullName)"
    Write-Host '---- Last 55 internal build-log lines ----'
    Get-Content -LiteralPath $log.FullName -Tail 55
}
else {
    Write-Warning "No internal build.log found for THIS run at: $outputAbsolute"
    if (Test-Path -LiteralPath $outputAbsolute) {
        Get-ChildItem -LiteralPath $outputAbsolute -Recurse -File |
            Select-Object -First 25 FullName, Length |
            Out-String | Write-Host
    }
}

@(
    "run_id=$runId"
    "output_relative=$outputRelative"
    "output_absolute=$outputAbsolute"
    "docker_exit_code=$exitCode"
    "internal_log_found=$internalFound"
    "command_exception=$exceptionText"
    'disabled_patches=cl2.smali.patch,r2k.smali.patch,zy_gif_modes.patch'
    'WARNING: diagnostic APK incomplete; do not install or distribute.'
) | Set-Content -LiteralPath (Join-Path $evidenceDir 'probe-metadata.txt') -Encoding UTF8

Compress-Archive -Path (Join-Path $evidenceDir '*') `
    -DestinationPath $evidenceZip -CompressionLevel Optimal
Write-Host "Docker exit code: $exitCode"
Write-Host "Upload evidence ZIP: $evidenceZip" -ForegroundColor Green
