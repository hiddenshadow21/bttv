# Twitch 31.8.0 — read-only React Native timestamp renderer map

The previous `generate_rn_timestamp_style_patch_318.py` stopped safely with
`Expected exactly one ReactTextView.smali, found 0`. It assumed an un-obfuscated
class filename. The React Native package index in the 31.8.0 context refers to
`ReactTextViewManager` **and** `PreparedLayoutTextViewManager`, so we need to
inspect both factories and their actual view classes before patching anything.

## Run from the BTTV repository root (PowerShell)

```powershell
Expand-Archive -LiteralPath .\twitch318-timestamp-renderer-mapper.zip -DestinationPath . -Force

$run = Get-Date -Format 'yyyyMMdd-HHmmss'
$env:BTTV_OUTPUT_DIR = "./dist/timestamp-map-$run"

docker compose run --rm --entrypoint python3 build `
    /source/collect_twitch318_timestamp_renderers.py `
    --new /source/twitch.zip `
    --output /output/twitch318-rn-text-renderer-map.zip

if ($LASTEXITCODE -ne 0) { throw 'Text renderer mapping failed' }

$map = Join-Path $env:BTTV_OUTPUT_DIR 'twitch318-rn-text-renderer-map.zip'
Get-Item $map
```

Upload `twitch318-rn-text-renderer-map.zip`. The archive contains the relevant
smali and a JSON report with concrete text manager factory types, onDraw
implementations and inheritance information. It does not copy the entire APK.

**Do not build a new APK yet.** The failed prior generator did not create its
patch. This collector does not modify the working emotes, chat, settings or
vertical-view fixes.

## What this mapping will and won't solve

A native text-view styling hook may be able to change color and remove
brackets from the injected time. It **cannot guarantee history-style layout**
(`22:15` before badges, with a separately colored username); that ordering is
controlled by React Native's chat-row UI. After identifying the renderer we
need to assess whether to patch the RN component rather than styling
`display-name` through a native span.
