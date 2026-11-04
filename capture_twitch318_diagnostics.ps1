# Capture only BTTV diagnostic tags and Android runtime failures from a connected device.
# Run from the bttv-pr repository root after installing the diagnostic APK.
$ErrorActionPreference = 'Stop'
$adb = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
if (-not (Test-Path $adb)) { throw "ADB not found at $adb" }
& $adb devices -l
if ($LASTEXITCODE -ne 0) { throw 'adb devices failed' }
Write-Host 'Please ensure only your intended phone is connected (or set ANDROID_SERIAL).'
& $adb logcat -c
if ($LASTEXITCODE -ne 0) { throw 'adb logcat -c failed' }
Read-Host 'On the PHONE: force-close BTTV, reopen, enter a channel chat with external emotes, open its emote picker, then visit Twitch Settings. Press Enter here afterward'
New-Item -ItemType Directory -Path '.\dist' -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = Join-Path '.\dist' "twitch318-diagnostics-$stamp.txt"
& $adb logcat -d -v time -s BTTV318Diag:V BTTV31TRACE:V AndroidRuntime:E 2>&1 | Out-File -Encoding utf8 -FilePath $out
if ($LASTEXITCODE -ne 0) { throw 'adb logcat failed' }
Write-Host "Diagnostic excerpts written to $out"
Write-Host 'Review the file for any sensitive data before sharing.'
Get-Content $out -Tail 95
