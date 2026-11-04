param([string]$OutDirectory = '.\dist\twitch318-settings-ui')
$ErrorActionPreference = 'Stop'
$adb = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
if (-not (Test-Path $adb)) { throw "adb not found: $adb" }
New-Item -ItemType Directory -Force $OutDirectory | Out-Null
Write-Host 'Open Twitch 31.8.0 Settings and scroll to where Twitch version is displayed, then press Enter.'
[void](Read-Host)
& $adb shell uiautomator dump /sdcard/bttv318-window.xml
if ($LASTEXITCODE -ne 0) { throw 'uiautomator dump failed' }
& $adb pull /sdcard/bttv318-window.xml (Join-Path $OutDirectory 'full-window.xml') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'adb pull failed' }
[xml]$doc = Get-Content -Raw (Join-Path $OutDirectory 'full-window.xml')
$selected = foreach ($node in $doc.SelectNodes('//node')) {
  $text = [string]$node.GetAttribute('text')
  $description = [string]$node.GetAttribute('content-desc')
  if (($text + ' ' + $description) -match '(?i)twitch|bttv|version|31\.8') {
    [pscustomobject]@{Class=$node.GetAttribute('class');Text=$text;Description=$description;ResourceId=$node.GetAttribute('resource-id');Bounds=$node.GetAttribute('bounds')}
  }
}
$selected | Format-List | Out-String | Set-Content -Encoding UTF8 (Join-Path $OutDirectory 'version-widgets.txt')
Write-Host 'Relevant widgets:'
$selected | Format-Table -AutoSize
Write-Host 'Share only version-widgets.txt after reviewing it; full-window.xml may include private account content.'
