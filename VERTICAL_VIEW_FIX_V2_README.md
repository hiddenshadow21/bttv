# Twitch 31.8.0 — Vertical View verifier mitigation v2

## Why v1 fails

The file `patches/live/bttvcompat.EmoteDetailsBridge.smali.patch` contains more than one Git `diff --git` section: the bridge, `EmoteDetailsClick`, and `EmoteDetailsSheet`. The v1 installer wrongly required the *entire patch* to have only one `@@` hunk, so it stops even though the bridge itself has one new-file hunk.

## What v2 changes

The new installer searches for exactly one `smali_classes7/bttvcompat/EmoteDetailsBridge.smali` diff section. Within that section, it replaces only:

- `open(View,String,String,boolean)`: the verifier-invalid Fragment/Activity interaction is replaced with `return-void`.
- `clear(ImageView)`: the verifier-invalid `new-instance wte` / `kgl.<init>` interaction is replaced with a null-guarded `setImageDrawable(null)`.

Everything else in the patch, including the complete `EmoteDetailsClick` and `EmoteDetailsSheet` sections and the `wrap` method, is preserved byte-for-byte. The temporary trade-off is that the old emote details popup no longer opens.

The script backs up the original file before editing, detects repeat runs, refuses unknown method bodies and refuses incorrect hunk counts. React Native emotes, Settings, version string and other patches are not modified.

## Installation (Windows PowerShell, repository root)

The ZIP contains a drop-in replacement named `fix_vertical_view_verifier_318.py`:

```powershell
Expand-Archive -LiteralPath .\twitch318-vertical-view-crash-fix-v2.zip -DestinationPath . -Force
python .\fix_vertical_view_verifier_318.py --check
if ($LASTEXITCODE -ne 0) { throw 'Bridge patch preflight failed. Do not build.' }

python .\fix_vertical_view_verifier_318.py --apply
if ($LASTEXITCODE -ne 0) { throw 'Bridge patch repair failed.' }

python .\fix_vertical_view_verifier_318.py --check
git add -- patches/live/bttvcompat.EmoteDetailsBridge.smali.patch
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw 'Git patch diff check failed.' }

$run = Get-Date -Format 'yyyyMMdd-HHmmss'
$env:BTTV_OUTPUT_DIR = "./dist/docker-vertical-v2-$run"
docker compose run --rm build
if ($LASTEXITCODE -ne 0) {
    Get-Content (Join-Path $env:BTTV_OUTPUT_DIR 'build/build.log') -Tail 130
    throw 'APK build failed; do not install.'
}

$apk = Join-Path $env:BTTV_OUTPUT_DIR 'build/twitch.apk'
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb install -r $apk
if ($LASTEXITCODE -ne 0) { throw 'APK installation failed.' }
```

Then open a channel that supports Vertical View. The prior `bttvcompat.EmoteDetailsBridge` verifier error should be gone if this build is the one installed. If another crash occurs, gather a *fresh* stack trace:

```powershell
& $adb logcat -c
# reproduce the Vertical View crash now
& $adb logcat -d -v time -s 'AndroidRuntime:E' 'BTTV318RN:I' 'BTTV318Net:I' '*:S' > .\dist\twitch318-vertical-v2-log.txt
```

Upload that text if the app still crashes. **A new VerifyError in a different class requires separate diagnosis.** This patch is not a general fix for every vertical-view failure.

## Rollback

Restore the backup from `dist/twitch318-vertical-view-backups/EmoteDetailsBridge.smali.patch.TIMESTAMP.bak` to `patches/live/bttvcompat.EmoteDetailsBridge.smali.patch`, then `git add` and rebuild.

## Validation performed

The v2 logic was tested on a representative three-section new-file patch; the resulting patch passed `git apply --check` and `git apply`. Automated tests cover unchanged neighboring classes, repeat-run behavior, backup creation, and rejection of unknown method bodies. It has not been run against the user's current local patch or built and installed on their device.

This patch does not address (1) timestamps appearing after the username or (2) static GIF/animated WebP emotes. They require separate React Native renderer/decoder changes.
