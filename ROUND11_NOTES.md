# BTTV PR #741 → Twitch 31.8.0 — Round 11

**Status:** Three candidate replacement patches and a rebalancer v2.  **Not a released or runtime-verified APK.**

## Contents

- `patches/live/cl2.smali.patch`: replaces the obsolete `Lcl2;->R(La120;)V` callback. Adds a distinct `Lxoz;->BTTV` enum, extends the 31.8.0 native settings row builder `NativeSettingsBridge.appendLegacy` to construct `Len20`, and replaces the dead old callback / Compose bridge implementations with `handleCompose(Lxoz;Ljava/lang/Object;)Z`. The already-applied Round 7 `ffo` patch calls `appendLegacy` from `Lxpo;->A2()`; **do not insert that call a second time**.
- `patches/live/r2k.smali.patch`: intercepts the actual `Lqnc;->q(Lxoz;)V` settings menu navigation callback. The previously requested `Lr2k` Compose target is unrelated in Twitch 31.8.0, so the feature is represented as a new settings row rather than injected into the obsolete Compose function.
- `patches/live/zy_gif_modes.patch`: ports the animation hook onto `Lxjj`, `Lva6`, `Lfv1`, `Lpqf`, `Ldv60`, and two BTTV bridge classes. Updates Glide types `Li0x → Llix`, `Lzk2 → Lbn2`, request manager `Ll1x → Lojx`, drawable `Lr360 → Ldv60`, and native emote options `Lqz0 → Lo01` / `Len6 → Lwp6`. This is an integration candidate and not proof that each GIF renders correctly.
- `twitch318_dex_rebalance.py`: **replacement** for the original failed DEX2→DEX7-only script. Reads existing DEX2–DEX7, estimates each pool, plans moves across any DEX with enough headroom, then moves whole related smali class groups **only if the entire plan fits**. It does not create a new DEX and cannot guarantee the 16-bit pools will be under limit after dexlib2 adds hidden references.

## Testing completed here

- All three new patch files passed `git apply --check --index` and `git apply --index` sequentially on the supplied, decoded 31.8.0 reference files, *in real build order*, interleaved with the existing `aaj`, `f86`, `ffo`, `qt1`, `wjf`, and `zz_emote_details` patches. See `ROUND11_TEST_SUMMARY.txt`.
- The rebalance script was syntax-checked and tested in both `--dry-run` and `--rebalance` modes on a synthetic 6-DEX project where DEX7 had very little spare capacity and DEX3–DEX6 were available.
- **No full Apktool compilation or ART/device testing was possible in this environment.** The `git apply` tests say nothing about actual DEX linkage, resource correctness, or app behavior.

## Apply on Windows PowerShell

From the repository root, with existing Round 1–9 changes already installed:

```powershell
# Keep an independent copy of the three patch files and existing rebalance script
New-Item -ItemType Directory -Force .\round11-backup | Out-Null
Copy-Item .\patches\live\cl2.smali.patch .\round11-backup\cl2.smali.patch
Copy-Item .\patches\live\r2k.smali.patch .\round11-backup\r2k.smali.patch
Copy-Item .\patches\live\zy_gif_modes.patch .\round11-backup\zy_gif_modes.patch
Copy-Item .\twitch318_dex_rebalance.py .\round11-backup\twitch318_dex_rebalance.py

Expand-Archive -LiteralPath .\twitch318-round11-final-three-and-dex-v2.zip -DestinationPath . -Force

# The old installed build hook still calls the same Python filename. Confirm it exists.
Select-String .\build -Pattern 'BEGIN BTTV TWITCH 31.8 DEX REBALANCE'

$run = Get-Date -Format 'yyyyMMdd-HHmmss'
$env:BTTV_OUTPUT_DIR = "./dist/docker-patch-audit-round11-$run"
docker compose run --rm --entrypoint python3 build /source/audit_twitch_patches.py
Get-Content (Join-Path $env:BTTV_OUTPUT_DIR 'patch-audit.txt') -TotalCount 85
```

If all patches apply, the audit should report **65/65**. This is not proof the APK works.

### Attempt the real full build — not the 3-patch-disabled probe

```powershell
$run = Get-Date -Format 'yyyyMMdd-HHmmss'
$env:BTTV_OUTPUT_DIR = "./dist/docker-full-build-round11-$run"
docker compose run --rm build
Get-Content (Join-Path $env:BTTV_OUTPUT_DIR 'build/build.log') -Tail 130
```

Do **not** use the old `probe_twitch318_build_v2.ps1` to verify the three new hooks: it intentionally disables them. The full build above retains all 65 patches. It uses a new output folder to avoid the build system's no-overwrite protection.

## Remaining risks to investigate after successful DEX assembly

1. Rebalance estimates do not count all DEX type and string pool references. Extra relocation may be needed.
2. Adding an enum to `Lxoz` modifies R8-generated class state. The new value is appended to `values()` and Kotlin `entries`, and the BTTV click is intercepted before the original ordinal switch; nevertheless the entire settings navigation needs runtime testing.
3. The existing `NativePickerBridge` has other 31.2.0-era obfuscated names, outside the GIF-specific edited path. Further class-mapping/bytecode verification is necessary.
4. GIF behavior depends on `GifPolicy.shouldAnimate`, valid synthetic emote IDs and working Glide handlers; a successful `git apply` is not sufficient.
5. Earlier ports still have unresolved runtime risks (DEX relocation, resource IDs, and unrelated stale helper references).

Use the resulting `build/build.log`, *not* only the Python `CalledProcessError` traceback, to diagnose build failures.
