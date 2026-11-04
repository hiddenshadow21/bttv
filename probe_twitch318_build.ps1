# Diagnostic build with ONLY the last three failing patch files temporarily hidden.
# This is NOT a functional BTTV build. It is intended to expose compilation,
# linkage, and resource problems in the 62 patches that already apply.
# The original patch files are restored in the finally block.

$ErrorActionPreference = 'Stop'
$patchDir = Join-Path (Get-Location).Path 'patches\live'
$files = @('cl2.smali.patch', 'r2k.smali.patch', 'zy_gif_modes.patch')
foreach ($f in $files) {
    if (-not (Test-Path -LiteralPath (Join-Path $patchDir $f))) {
        throw "Missing patches\live\$f -- run this from the repository root."
    }
}
New-Item -ItemType Directory -Path '.\dist' -Force | Out-Null
$backup = Join-Path (Resolve-Path '.\dist').Path ('port-probe-stash-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $backup | Out-Null
$saved = @()
$previousOutput = [Environment]::GetEnvironmentVariable('BTTV_OUTPUT_DIR')
$exitCode = $null
$logFile = Join-Path (Resolve-Path '.\dist').Path 'twitch318-full-build-probe.log'
try {
    foreach ($f in $files) {
        $src = Join-Path $patchDir $f
        $dst = Join-Path $backup $f
        Move-Item -LiteralPath $src -Destination $dst -ErrorAction Stop
        $saved += $f
    }
    $env:BTTV_OUTPUT_DIR = './dist/docker-full-build-probe'
    Write-Host 'Running a diagnostic build with 3 hooks disabled. This output APK must NOT be used.'
    Write-Host "Build log: $logFile"
    & docker compose run --rm build 2>&1 | Tee-Object -FilePath $logFile
    $exitCode = $LASTEXITCODE
}
finally {
    foreach ($f in $saved) {
        $from = Join-Path $backup $f
        if (Test-Path -LiteralPath $from) {
            Move-Item -LiteralPath $from -Destination (Join-Path $patchDir $f) -Force
        }
    }
    if ($null -ne $previousOutput) {
        $env:BTTV_OUTPUT_DIR = $previousOutput
    } else {
        Remove-Item Env:BTTV_OUTPUT_DIR -ErrorAction SilentlyContinue
    }
    if ((Get-ChildItem -LiteralPath $backup -Force | Measure-Object).Count -eq 0) {
        Remove-Item -LiteralPath $backup -Force
    }
}
Write-Host "Docker exit code: $exitCode"
Write-Host 'The three original patch files have been restored.'
Write-Host 'Review the last 100 lines of dist\twitch318-full-build-probe.log.'
