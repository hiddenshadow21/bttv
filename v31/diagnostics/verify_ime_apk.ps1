# Verify that a built APK contains the CURRENT experimental keyboard hook.
# Usage: powershell -ExecutionPolicy Bypass -File .\v31\diagnostics\verify_ime_apk.ps1 -ApkPath .\dist\bttv-31.8.0.apk
param([Parameter(Mandatory=$true)][string]$ApkPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$path = (Resolve-Path -LiteralPath $ApkPath -ErrorAction Stop).Path
$needle = 'install invoked; root='
$zip = [System.IO.Compression.ZipFile]::OpenRead($path)
$found = @()
try {
    foreach ($entry in $zip.Entries) {
        if ($entry.Name -notmatch '^classes\d*\.dex$') { continue }
        $stream = $entry.Open()
        $memory = New-Object System.IO.MemoryStream
        try {
            $stream.CopyTo($memory)
            $bytes = $memory.ToArray()
            # DEX strings use modified UTF-8. This ASCII marker is byte-identical.
            $buffer = [System.Text.Encoding]::ASCII.GetString($bytes)
            if ($buffer.Contains($needle)) { $found += $entry.Name }
        } finally {
            $memory.Dispose()
            $stream.Dispose()
        }
    }
} finally {
    $zip.Dispose()
}
if ($found.Count -eq 0) {
    throw "EXPERIMENTAL HOOK NOT FOUND in $path. You may have built the old branch or an old cached APK."
}
Write-Host "Current experimental hook found in DEX: $($found -join ', ')" -ForegroundColor Green
Write-Host 'This checks the built APK, NOT whether it was installed or executed on the phone.'
