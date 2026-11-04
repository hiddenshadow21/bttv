# Repair missing BTTV 31.8.0 Java diagnostic instrumentation

The `zzzz_bttv_runtime_diagnostics.patch` file is already present/tracked, but the three required Java diagnostic edits are missing. The original installer refuses to run while that probe patch exists. This script safely applies only the missing Java edits using the original installer’s exact `EDITORS` transformations.

## Prerequisites
- Run from the `bttv-pr` repository root on Windows / PowerShell.
- Keep `install_twitch318_runtime_diagnostics.py` from the earlier kit in the root.
- Keep `patches/live/zzzz_bttv_runtime_diagnostics.patch` in place and tracked.

## Commands

```powershell
python .\repair_twitch318_java_diagnostics.py --check
python .\repair_twitch318_java_diagnostics.py --apply
python .\twitch318_diagnostics_preflight.py

git add -- `
  mod/app/src/main/java/bttv/settings/SettingsNavigation.java `
  mod/app/src/main/java/bttv/emote/LiveEmotes.java `
  mod/app/src/main/java/bttv/emote/LiveEmoteGlobals.java

$run = Get-Date -Format 'yyyyMMdd-HHmmss'
$env:BTTV_OUTPUT_DIR = "./dist/docker-runtime-diag-repair-$run"
docker compose run --rm build

$apk = Join-Path $env:BTTV_OUTPUT_DIR 'build/twitch.apk'
python .\twitch318_diagnostics_preflight.py --apk $apk
```

Install with ADB **only if** the APK verification prints `PASS: BTTV318Diag exists`.

## Safety and rollback
- The script refuses to edit Java when expected anchors have changed.
- All edits are validated before the first file is written.
- It backs up original Java files in a timestamped `dist/twitch318-java-diag-backup-*` directory.
- It does **not** touch the already committed diagnostic smali patch, the Git index, or your signing setup.
- To undo *only these three Java edits* manually, copy the corresponding three files from the printed backup directory back into their original `mod/app/src/main/java/...` paths. Do not use the old diagnostic installer's `--revert` unless its own backup manifest accurately matches your current source.

This is temporary instrumentation, not a fix for missing external emotes or BTTV settings themselves. Those require runtime results after the marker is embedded in the installed APK.
