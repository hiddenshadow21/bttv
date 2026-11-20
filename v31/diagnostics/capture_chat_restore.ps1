# Capture a before/after view of the Twitch 31.8.0 minimized-player chat bug.
# This script DOES NOT patch or restart the app and DOES NOT export chat text.
param([string]$Serial = '')

$ErrorActionPreference = 'Stop'

$cmd = Get-Command adb -ErrorAction SilentlyContinue
if ($cmd) {
    $adb = $cmd.Source
} else {
    $sdkRoot = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } elseif ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } else { Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
    $adb = Join-Path $sdkRoot 'platform-tools\adb.exe'
}
if (-not (Test-Path -LiteralPath $adb)) { throw 'ADB not found. Install Android SDK platform-tools or put adb in PATH.' }

$devices = @(& $adb devices | ForEach-Object {
    if ($_ -match '^(\S+)\s+device(?:\s|$)') { $Matches[1] }
})
if (-not $Serial) {
    if ($devices.Count -ne 1) { throw "Expected one authorized device. Found: $($devices -join ', '). Rerun with -Serial DEVICE_SERIAL." }
    $Serial = $devices[0]
}
if ($Serial -notin $devices) { throw "ADB device $Serial is not connected and authorized." }

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$runDir = Join-Path $PSScriptRoot ("..\..\dist\chat-restore-$stamp")
$runDir = [System.IO.Path]::GetFullPath($runDir)
New-Item -ItemType Directory -Path $runDir -Force | Out-Null

$meta = @(
    'Scenario: video works, chat disappears after minimized player is restored',
    'Twitch baseline: 31.8.0 (confirm your installed version)',
    "Android: $(& $adb -s $Serial shell getprop ro.build.version.release)",
    "Screen size: $(& $adb -s $Serial shell wm size)",
    "Display density: $(& $adb -s $Serial shell wm density)"
)
$meta | Set-Content -Path (Join-Path $runDir 'device-info.txt') -Encoding UTF8

function Capture-Snapshot([string]$label) {
    Write-Host "Capturing $label ..." -ForegroundColor Cyan

    # Record IME state BEFORE uiautomator dump (the dump may disturb focus).
    $before = @(& $adb -s $Serial shell dumpsys input_method)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to capture IME state before UI hierarchy.' }
    $imeState = @($before | Select-String -Pattern 'mInputShown\s*=|mIsInputViewShown\s*=|mShowRequested\s*=|mImeWindowVis\s*=|mInputViewStarted\s*=' | ForEach-Object { $_.Line.Trim() })
    $imeState | Set-Content -Path (Join-Path $runDir "$label-ime-BEFORE-ui-dump.txt") -Encoding UTF8

    $keyboardShown = (@($imeState | Where-Object { $_ -match '(?:^|\s)mInputShown=true(?:\s|$)' }).Count -gt 0)
    Write-Host "Keyboard reported by input_method: $keyboardShown" -ForegroundColor Yellow
    if ($label -eq '02-broken-keyboard-open' -and -not $keyboardShown) {
        Write-Warning 'Keyboard is NOT reported open at capture time. The result will not prove the failing IME state.'
    }

    # Keep screenshots PRIVATE and LOCAL for checking what was actually shown.
    # They are NOT included in the ZIP and must be reviewed separately before sharing.
    $shotPhone = '/sdcard/bttv-chat-restore-snapshot.png'
    $shotLocal = Join-Path $runDir "$label-PRIVATE-LOCAL-screenshot.png"
    try {
        & $adb -s $Serial shell screencap -p $shotPhone | Out-Null
        if ($LASTEXITCODE -eq 0) {
            & $adb -s $Serial pull $shotPhone $shotLocal | Out-Null
        }
    } catch {
        Write-Warning "Screenshot skipped: $($_.Exception.Message)"
    } finally {
        & $adb -s $Serial shell rm -f $shotPhone 2>$null | Out-Null
    }

    # Sanitized accessibility hierarchy: NEVER write text/content-desc/password.
    $tempXml = Join-Path $runDir "$label-PRIVATE-DELETE.xml"
    $outputJson = Join-Path $runDir "$label-view-bounds.json"
    try {
        & $adb -s $Serial shell uiautomator dump /sdcard/bttv-chat-restore.xml | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'uiautomator dump failed' }
        & $adb -s $Serial pull /sdcard/bttv-chat-restore.xml $tempXml | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'adb pull failed' }
        [xml]$doc = Get-Content -LiteralPath $tempXml -Encoding UTF8 -Raw
        # Dynamic accessibility IDs sometimes contain channel names.
        # Retain only fixed IDs needed for theatre/chat layout comparison.
        $safeIds = @(
            'android:id/content', 'overlay-provider-root', 'overlay-host',
            'picker-overlay', 'theatre-screen', 'theatre-backdrop',
            'theatre-portrait-layout', 'theatre-video-zoom',
            'theatre-video-zoom-gesture-surface', 'theatre-video-zoom-clip',
            'theatre-video-zoom-video-layer', 'player-controls-tap-layer',
            'video-player', 'stage-inflow-metadata', 'channel-metadata',
            'theatre-chat', 'chat-area', 'chat-message-region',
            'chat-message-list-container', 'chat-message-list',
            'chat-message-list-reader-observer', 'chat-message-row',
            'chat-input-bar', 'chat-input-field-box', 'chat-input-field-group',
            'chat-composer-input', 'discovery-feed-screen', 'feed-list',
            'tv.twitch.bttvandroid.app:id/rn_theatre_container',
            'tv.twitch.bttvandroid.app:id/rn_theatre_draggable',
            'tv.twitch.bttvandroid.app:id/fragment_container',
            'tv.twitch.bttvandroid.app:id/viewer_landing_layout'
        )
        $nodes = @(
            foreach ($node in $doc.SelectNodes('//node')) {
                $id = $node.GetAttribute('resource-id')
                if ($id -notin $safeIds) { $id = '' }
                [pscustomobject]@{
                    class = $node.GetAttribute('class')
                    bounds = $node.GetAttribute('bounds')
                    resourceId = $id
                }
            }
        )
        ConvertTo-Json -InputObject $nodes -Depth 3 | Set-Content -Path $outputJson -Encoding UTF8
    } catch {
        "Accessibility view snapshot unavailable: $($_.Exception.Message)" |
            Set-Content -Path (Join-Path $runDir "$label-view-error.txt") -Encoding UTF8
    } finally {
        Remove-Item -LiteralPath $tempXml -Force -ErrorAction SilentlyContinue
        & $adb -s $Serial shell rm -f /sdcard/bttv-chat-restore.xml 2>$null | Out-Null
    }

    # Inspect foreground activity and IME/window focus without full dumpsys output.
    $window = @(& $adb -s $Serial shell dumpsys window windows)
    $activity = @(& $adb -s $Serial shell dumpsys activity activities)
    $window | Select-String -Pattern 'mCurrentFocus|mFocusedApp|mInputMethodTarget|mImeInputTarget|mImeLayeringTarget|mInputMethodWindow' |
        ForEach-Object { $_.Line.Trim() } |
        Set-Content -Path (Join-Path $runDir "$label-window.txt") -Encoding UTF8
    $activity | Select-String -Pattern 'topResumedActivity|mResumedActivity|ResumedActivity' |
        ForEach-Object { $_.Line.Trim() } |
        Set-Content -Path (Join-Path $runDir "$label-activity.txt") -Encoding UTF8

    # Record only IME visibility booleans; do not export input connections or text.
    $ime = @(& $adb -s $Serial shell dumpsys input_method)
    $ime | Select-String -Pattern 'mInputShown\s*=|mIsInputViewShown\s*=|mShowRequested\s*=|mImeWindowVis\s*=|mInputViewStarted\s*=' |
        ForEach-Object { $_.Line.Trim() } |
        Set-Content -Path (Join-Path $runDir "$label-ime-visibility.txt") -Encoding UTF8
}

Write-Host 'IMPORTANT: Keep the keyboard state in mind. The first reproduction had keyboard closed in working capture and open in broken capture.' -ForegroundColor Yellow
& $adb -s $Serial logcat -c
if ($LASTEXITCODE -ne 0) { throw 'Unable to clear logcat.' }
[void](Read-Host 'Open a stream with working VIDEO AND CHAT, with the keyboard CLOSED. Press Enter here')
Capture-Snapshot '01-working-keyboard-closed'
[void](Read-Host 'Minimize and restore the player, OPEN THE CHAT KEYBOARD until chat disappears and video keeps playing. KEEP THE KEYBOARD OPEN. Press Enter on your PC')
Capture-Snapshot '02-broken-keyboard-open'
[void](Read-Host 'Without closing/reopening the STREAM, DISMISS the keyboard if visible (use its hide arrow; avoid navigating away). Wait 2 seconds and press Enter here')
Capture-Snapshot '03-after-keyboard-hidden'

# Narrow logging scope. Do not collect raw IRC or GraphQL traffic.
$tags = @(
    'AndroidRuntime:E', 'ReactNative:E', 'ReactNativeJS:W',
    'ReactNativeJNI:W', 'ReactFabric:V', 'FabricMounting:V',
    'SurfaceMountingManager:V', 'LBTTVHooks:V', 'LBTTVIrcEmotes:V',
    'LBTTVSplitChat318:V', 'LBTTVSetBroadcasterId:V',
    'LBTTVVertical318:V', 'LBTTVClassic318:V',
    'BTTV318RN:V', 'BTTV318Diag:V', '*:S'
)
$lines = @(& $adb -s $Serial logcat -d -b main -b system -b crash -v threadtime -s @tags)
if ($LASTEXITCODE -ne 0) { throw 'Unable to capture logcat.' }
$lines | ForEach-Object {
    $clean = $_
    $clean = $clean -replace '(?i)(Bearer\s+)\S+', '$1[REDACTED]'
    $clean = $clean -replace '(?i)(access_token|refresh_token|oauth_token|authorization|password)(\s*[=:]\s*)\S+', '$1$2[REDACTED]'
    $clean = $clean -replace '[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[EMAIL REDACTED]'
    $clean
} | Set-Content -Path (Join-Path $runDir 'restore-filtered-logcat.txt') -Encoding UTF8

$files = @(Get-ChildItem -LiteralPath $runDir -File | Where-Object { $_.Extension -in @('.txt', '.json') } | ForEach-Object { $_.FullName })
$zip = "$runDir.zip"
Compress-Archive -LiteralPath $files -DestinationPath $zip -Force
Write-Host "Capture ready: $zip" -ForegroundColor Green
Write-Host 'Inspect the ZIP before sharing. Logs may still contain channel names or other personal data.' -ForegroundColor Yellow
Write-Host 'No app sources, chat text, raw accessibility XML or screenshots are included in the ZIP.' -ForegroundColor Yellow
Write-Host "Private screenshots (not in ZIP) are in $runDir, for your own confirmation." -ForegroundColor Yellow
