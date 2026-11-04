# Captures BTTV Twitch 31.8.0 symptoms from a phone or emulator.
# Keeps raw Android logs local. Bundles only selected/redacted excerpts.
param(
    [ValidateSet('phone', 'emulator')]
    [string]$Mode = 'phone',
    [string]$Serial = ''
)

$ErrorActionPreference = 'Stop'

$adbCommand = Get-Command adb -ErrorAction SilentlyContinue
if ($adbCommand) {
    $adb = $adbCommand.Source
} else {
    $sdkRoot = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } elseif ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } else { Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
    $adb = Join-Path $sdkRoot 'platform-tools\adb.exe'
}
if (-not (Test-Path -LiteralPath $adb)) {
    throw "ADB not found: $adb. Set ANDROID_HOME or use the Android Studio SDK platform-tools directory."
}

$connected = @()
foreach ($line in @(& $adb devices)) {
    if ($line -match '^(\S+)\s+device(?:\s.*)?$') {
        $connected += $Matches[1]
    }
}
if ($connected.Count -eq 0) {
    throw 'No authorized ADB devices found. Enable USB debugging, accept the authorization prompt, and run adb devices.'
}
if (-not $Serial) {
    if ($Mode -eq 'phone') { $candidates = @($connected | Where-Object { $_ -notmatch '^emulator-' }) }
    else { $candidates = @($connected | Where-Object { $_ -match '^emulator-' }) }
    if ($candidates.Count -eq 1) { $Serial = $candidates[0] }
    else {
        Write-Host "Available devices: $($connected -join ', ')"
        throw 'Multiple devices connected. Rerun with -Serial YOUR_DEVICE_SERIAL.'
    }
}
if ($Serial -notin $connected) {
    throw "Selected device '$Serial' is not connected/authorized. Available: $($connected -join ', ')"
}

$root = $PSScriptRoot
if (-not $root) { $root = (Get-Location).Path }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$runDir = Join-Path $root ("dist\twitch318-runtime-$Mode-$stamp")
New-Item -ItemType Directory -Path $runDir -Force | Out-Null

$meta = Join-Path $runDir 'device-info.txt'
@(
    "Capture mode: $Mode",
    "Android version: $(& $adb -s $Serial shell getprop ro.build.version.release)",
    "SDK: $(& $adb -s $Serial shell getprop ro.build.version.sdk)",
    "Supported ABIs: $(& $adb -s $Serial shell getprop ro.product.cpu.abilist)",
    "Device model: $(& $adb -s $Serial shell getprop ro.product.model)",
    'Application package: tv.twitch.bttvandroid.app'
) | Set-Content -Path $meta -Encoding UTF8

$pattern = 'FATAL EXCEPTION|AndroidRuntime|DEBUG\s*:\s*\*\*\*|Fatal signal|Process: tv\.twitch\.bttvandroid\.app|NoSuchMethodError|NoSuchFieldError|ClassNotFoundException|ClassCastException|VerifyError|UnsatisfiedLinkError|NullPointerException|IllegalStateException|IllegalArgumentException|SecurityException|ExceptionInInitializerError|InflateException|SSLHandshakeException|UnknownHostException|SocketTimeoutException|HTTP 40[0-9]|HTTP 50[0-9]|bttv|betterttv|frankerfacez|7tv|seventv|emote|glide|imagewidget|Integrity|unsupported.*version'

function Capture-Scenario([string]$name, [string]$instruction) {
    Write-Host ""
    Write-Host "==== $name ====" -ForegroundColor Cyan
    & $adb -s $Serial logcat -c | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not clear Android logcat.' }
    Write-Host $instruction -ForegroundColor Yellow
    [void](Read-Host 'Press ENTER after reproducing the issue')

    $raw = Join-Path $runDir ("$name-RAW-LOCAL-ONLY.txt")
    & $adb -s $Serial logcat -d -b main -b system -b crash -v threadtime | Set-Content -Path $raw -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "Could not collect Android logcat for $name." }

    $excerpts = Join-Path $runDir ("$name-excerpts.txt")
    $hits = @(Select-String -Path $raw -Pattern $pattern -Context 10,40)
    if ($hits.Count -eq 0) {
        "No matching logcat lines. The full raw log remains LOCAL in $raw." | Set-Content -Path $excerpts -Encoding UTF8
    } else {
        $selected = ($hits | Out-String -Width 250)
        # Common secret redactions. Not exhaustive; manually review before sharing.
        $selected = [regex]::Replace($selected, '(?i)Bearer\s+[^\s,;]+', 'Bearer [REDACTED]')
        $selected = [regex]::Replace($selected, '(?i)(access_token|refresh_token|oauth_token|client_secret|password|authorization)(\s*[=:]\s*)[^\s&;,}]+', '$1$2[REDACTED]')
        $selected = [regex]::Replace($selected, '[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[EMAIL REDACTED]')
        $selected | Set-Content -Path $excerpts -Encoding UTF8
    }
    Write-Host "Captured $($hits.Count) relevant matches into $(Split-Path $excerpts -Leaf)."
    Write-Host "Raw full log saved locally only: $raw"
    return $excerpts
}

Write-Host "Using ADB device: $Serial" -ForegroundColor Green
Write-Host "Logs: $runDir"
$selectedFiles = @($meta)
if ($Mode -eq 'phone') {
    $selectedFiles += Capture-Scenario 'emotes' 'On the PHONE, open BTTV Twitch, enter a live channel where a known third-party emote should appear, wait about 15 seconds, and note whether you see the emote code or a blank image.'
    $selectedFiles += Capture-Scenario 'profile-crash' 'On the PHONE, reopen BTTV Twitch if needed and tap your profile to reproduce the crash.'
} else {
    $selectedFiles += Capture-Scenario 'emulator-login' 'In the EMULATOR, attempt to sign in until the unsupported app version/OS message appears. Do not type your password into this script.'
}

$zipPath = "$runDir-excerpts.zip"
Compress-Archive -LiteralPath $selectedFiles -DestinationPath $zipPath -Force
Write-Host ""
Write-Host "SHAREABLE-EXCERPT ZIP: $zipPath" -ForegroundColor Green
Write-Host 'IMPORTANT: Review the excerpts for passwords, tokens, URLs, usernames or other sensitive data before sharing.' -ForegroundColor Yellow
Write-Host "Full RAW logs were NOT included in the ZIP; they remain in $runDir."
