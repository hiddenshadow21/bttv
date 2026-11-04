# ADB diagnostics that verifies the actually installed APK and captures unfiltered logs.
# Does NOT install/uninstall or clear app data. Keeps raw log local; ZIP contains excerpts.
param(
    [string]$ApkPath = '',
    [string]$Serial = ''
)
$ErrorActionPreference = 'Stop'
$pkg = 'tv.twitch.bttvandroid.app'
$adb = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
if (-not (Test-Path $adb)) { throw "ADB not found: $adb" }
$scanner = Join-Path $PSScriptRoot 'check_twitch318_apk_instrumentation.py'
if (-not (Test-Path $scanner)) { throw "Marker checker not found: $scanner" }

$devices = @(& $adb devices -l | ForEach-Object {
    $m = [regex]::Match($_, '^\s*(\S+)\s+device(?:\s|$)')
    if ($m.Success) { $m.Groups[1].Value }
})
if ($Serial) {
    if ($devices -notcontains $Serial) { throw "Requested device '$Serial' isn't connected. Available: $($devices -join ', ')" }
} elseif ($devices.Count -eq 1) {
    $Serial = $devices[0]
} else {
    throw "Connect exactly one authorized device, or specify -Serial. Connected: $($devices -join ', ')"
}
Write-Host "Using Android device $Serial"
$adbArgs = @('-s', $Serial)
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$dir = Join-Path $PSScriptRoot "dist\twitch318-verified-runtime-$timestamp"
New-Item -ItemType Directory -Path $dir -Force | Out-Null
$report = Join-Path $dir 'summary.txt'
$info = Join-Path $dir 'device-info.txt'
$excerpts = Join-Path $dir 'excerpts.txt'
$raw = Join-Path $dir 'RAW-logcat-LOCAL-ONLY.txt'
"Device: $Serial`nPackage: $pkg`nCaptured: $(Get-Date -Format o)" | Set-Content $info -Encoding UTF8
& $adb @adbArgs shell getprop ro.build.version.release | Add-Content $info
& $adb @adbArgs shell getprop ro.product.cpu.abilist | Add-Content $info
& $adb @adbArgs shell dumpsys package $pkg |
    Select-String -Pattern 'versionName=|versionCode=|firstInstallTime=|lastUpdateTime=' |
    Select-Object -First 12 | Out-File $info -Append -Encoding utf8

# Check installed actual package, not just a local build.
$installedPaths = @(& $adb @adbArgs shell pm path $pkg | Where-Object { $_ -match '^package:' })
if ($installedPaths.Count -eq 0) { throw "Package $pkg not installed on selected device." }
$remoteBase = ($installedPaths | Where-Object { $_ -match '/base\.apk' } | Select-Object -First 1)
if (-not $remoteBase) { $remoteBase=$installedPaths[0] }
$remoteBase = ($remoteBase -replace '^package:', '').Trim()
$installed = Join-Path $dir 'installed-base.apk'
Write-Host "Pulling installed APK from $remoteBase (for local marker verification)"
& $adb @adbArgs pull $remoteBase $installed | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not pull installed APK; check device and retry.' }
$testApks = @($installed)
if ($ApkPath) {
    $resolved = (Resolve-Path -LiteralPath $ApkPath).Path
    $testApks += $resolved
}
& python $scanner @testApks --json (Join-Path $dir 'apk-marker-report.json') | Tee-Object -FilePath $report
if ($LASTEXITCODE -ne 0) { throw 'APK marker scanner failed' }

Write-Host 'Clearing log buffers (not app data), then restarting BTTV.'
& $adb @adbArgs logcat -c
& $adb @adbArgs shell am force-stop $pkg
& $adb @adbArgs shell monkey -p $pkg -c android.intent.category.LAUNCHER 1 | Out-Null
Write-Host 'Use the PHONE: open live chat with expected BTTV/7TV/FFZ emotes, open emote picker, visit Settings.'
Read-Host 'After reproducing these symptoms, press Enter here' | Out-Null
& $adb @adbArgs logcat -d -b main -b system -b crash -v threadtime | Out-File -FilePath $raw -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'Unfiltered logcat capture failed' }
$pattern = 'BTTV318Diag|BTTV31TRACE|BTTV_CAPTURE|bttvcompat|bttv[./]emote|FATAL EXCEPTION|VerifyError|NoSuchMethodError|NoSuchFieldError|ClassNotFoundException|IllegalAccessError|UnsatisfiedLinkError|AndroidRuntime|tv\.twitch\.bttvandroid\.app|Emote'
Get-Content -LiteralPath $raw | Select-String -Pattern $pattern -Context 2,5 |
    Out-File -FilePath $excerpts -Encoding utf8
$hits = @((Select-String -Path $raw -Pattern 'BTTV318Diag|BTTV31TRACE' -ErrorAction SilentlyContinue)).Count
$rawBytes=(Get-Item $raw).Length
$excerptBytes=(Get-Item $excerpts).Length
"Log raw bytes: $rawBytes`nDiagnostic-tag lines: $hits`nExcerpt bytes: $excerptBytes" | Add-Content $report
if ($hits -eq 0) { Write-Warning 'No diagnostic tags emitted. Use the APK-marker report to decide whether the hook was built or just did not execute.' }
if ($excerptBytes -eq 0) { Write-Warning 'No matching log excerpts; raw log retained locally for further analysis.' }
$zip=Join-Path $PSScriptRoot "dist\twitch318-verified-runtime-$timestamp.zip"
Compress-Archive -Path $report, $info, $excerpts, (Join-Path $dir 'apk-marker-report.json') -DestinationPath $zip -Force
Write-Host "Evidence ZIP (review for private data): $zip"
Write-Host "Full raw log kept locally: $raw"
Write-Host "Installed APK kept locally: $installed"
Write-Host 'Do not share the full raw log or installed APK unless you intentionally choose to.'
