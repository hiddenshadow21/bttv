# Twitch 31.8.0 — runtime profile and emote bridges

## Observed issues

**Profile:** The uploaded 2026-11-02 21:21:32 phone stack trace has a `java.lang.VerifyError` for `bttvcompat.BrowserPurchaseBridge.profile(Object,Object)` and `.viewer(Object,Object)`: register `v0` carries `androidx.fragment.app.n`, not the expected `android.app.Activity`. Original 31.2.0 patch hard-coded an obsolete type. The 31.8.0 class index shows that `androidx.fragment.app.n` now extends `Object`, whereas `androidx.fragment.app.r` extends `bx9 -> ax9 -> android.app.Activity`.

**Profile and purchase source:** The 31.8.0 profile presenter is `plr`, not `nar`. Its `m` field is `Landroidx/fragment/app/r;`, its `S` field is `ChannelModel`, and its view delegate argument is `slr`. The two patched bridge classes are updated together.

**Emotes:** The original `LiveEmoteBridge` still calls old token classes `Limp` and `Lfmp`; in Twitch 31.8.0, `Limp` represents GiftSubscriptionsLoaded and `Lfmp` is CompletedPurchase, not chat tokens. 31.8.0's chat pipeline in `pb6` constructs `Lywp` for ordinary text and `Lvwp` for emote tokens, with matching `String` constructors. This is a strong explanation for third-party emotes remaining plain text: the old helper only processes instances of `Limp` and silently catches `Throwable`.

## Changes included (drop into repository root)

- `patches/live/bttvcompat.BrowserPurchaseBridge.smali.patch`: `plr`/`slr` types, `FragmentActivity r`, explicit Activity cast for the Java helper, corrected `getActivity()` return signature.
- `patches/live/bttvcompat.ProfilePurchaseSource.smali.patch`: `plr` presenter field and constructor.
- `patches/live/bttv.emote.LiveEmoteBridge.smali.patch`: `Lywp` text tokens and `Lvwp` emote tokens.

## Validation performed

- All three new-file patches passed sequential `git apply --check --index` and `git apply --index` in a fresh temporary Git workspace.
- Checked new profile field references against `plr.smali` in `twitch-port-reference.zip`.
- Verified the FragmentActivity inheritance chain and `Lywp` / `Lvwp` construction signatures from decoded 31.8.0 references.

## Known uncertainty

- **Not independently checked** whether `Lslr;->s:Landroidx/constraintlayout/widget/ConstraintLayout;` still names the intended profile view. The `plr` viewdelegate type (`slr`) is established, but the archive omitted the `slr` class's detailed field list. If this field changed, profile should not crash from the previous verifier mismatch, but the optional web-purchase row may not be added. Confirm with the new runtime log.
- Other purchase-helper classes still contain old obfuscated names. This package does **not** claim to fix all purchase functionality.
- Emote calls may have additional API/network or rendering issues; this corrects a structurally proven token mismatch but is not yet compiled or tested on device.
- There could be new verifier errors after these fixes. The only adequate end-to-end test is building and running the APK.

## Build commands (PowerShell, from repo root)

```powershell
Copy-Item .\patches\live .\live-backup-before-runtime-fix -Recurse -Force
Expand-Archive -LiteralPath .\twitch318-runtime-profile-emotes-fix.zip -DestinationPath . -Force
$run = Get-Date -Format 'yyyyMMdd-HHmmss'
$env:BTTV_OUTPUT_DIR = "./dist/docker-runtimefix-$run"
docker compose run --rm --entrypoint python3 build /source/audit_twitch_patches.py
# Use a NEW output on the actual build:
$run = Get-Date -Format 'yyyyMMdd-HHmmss'
$env:BTTV_OUTPUT_DIR = "./dist/docker-runtimefix-build-$run"
docker compose run --rm build
```

### Phone update warning

Use `adb install -r` **without uninstalling**. If Android reports a signing-identity mismatch (`INSTALL_FAILED_UPDATE_INCOMPATIBLE`), stop before uninstalling: uninstalling loses app data and can remove the logged-in session.

The original logs are not included in this ZIP, to avoid sharing unrelated device information.
