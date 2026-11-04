# BTTV PR #740 rebased to Twitch 31.8.0 (source-only candidate)

**Base:** `bttv-android/bttv` PR #740, commit `46accb0`. This branch deliberately
**does not contain PR #741** and does not migrate the 31.2.0-era `patches/live`
infrastructure. Its React Native chat, picker, and input implementations remain
PR #740's (`bttv.api.Hooks`, `IrcEmotes`, `RNEmoteMenu`, etc.).

## Rebase changes

The `apply_hooks.sh` script now calls a small fail-closed 31.8.0 relocator. Each
hook is based on a location present in the supplied `slop` branch's 31.8.0
patches. It patches 8 files in the decoded base APK:

- `TwitchApplication`: set context / start loading emote catalogs.
- `fy90.n`: React Native WebSocket chat listener.
- `NetworkingModule.sendRequest`: use PR #740's EmoteCard and ChatEmoteSets handler.
- `ReactImageManager`: copy-on-write image source URI rewriting; replaced
  the old `knl` constructor hook whose 31.8.0 identity is unverified.
- `TwitchEmoteInputView$EmoteSpanTarget`: input emote URLs.
- `EmoteImageLoader`: emote cache bitmap fallback.
- `EmoteImageSpan`: animated input rendering site.
- `TwitchEmoteInputView`: attached input animation callback.

The builder allocates a fresh DEX after the highest existing `smali_classesN`,
so it does not overwrite native 31.8.0 DEX code. The build uses the original
Twitch base and untouched splits (from `twitch.zip`), preserving PR #740's
build method. Network callers no longer require unshaded `okhttp3.*` at runtime.
The existing legacy badge/updater classes were adjusted only to remove their
OkHttp linkage; these features were not independently ported or enabled in RN.

## Build (requires a legally obtained, unmodified Twitch 31.8.0 split bundle)

1. Place the **31.8.0** Twitch `.apkm` ZIP at repo root as `twitch.zip`.
2. Follow the Docker builder setup from the original PR #740 instructions:

   ```sh
   docker run -d --name bttv --entrypoint sleep -v "$(pwd)":/repo ghcr.io/bttv-android/builder infinity
   docker exec bttv bash -c 'cp /repo/v31/*.sh /usr/build/'
   docker exec bttv bash /usr/build/setup.sh
   docker exec bttv bash -c 'cd /usr/build && bash apply_hooks.sh && bash build_mod.sh'
   ```

3. Check the generated `dist/splits` package. Install via `adb install-multiple -r`
   with the base and the matching device splits, **not** an arbitrary mixture of
   ABI/density splits. Do not uninstall the existing app to overcome a signing
   mismatch: that can erase app data.

To inspect hook compatibility without modifying the decoded Twitch files:

```sh
python3 v31/apply_hooks_31_8.py --work /path/to/decoded/base --check
```

## Scope / unverified

This is a **clean, source-only port candidate**, not a verified working APK.
The supplied Git bundle includes **no Twitch 31.8.0 APK or decoded smali**, so
we cannot run a genuine `apktool`/DEX build or runtime verification here. The
script fails rather than patching unrecognized method signatures. Twitch UI
behavior is not guaranteed, even if all 8 sites patch successfully.

The following PR #740 hooks were **not** copied to 31.8.0 because their method
and register mappings were not established in the supplied source:

- old `fw30` text-transform hook (EmoteCard presentation);
- `jt30`, `hcw`, and `SurfaceMountingManager` wide-emote layout and slot hooks;
- input span width/right-edge modifications (the 31.5.2 instruction layouts
  must not be assumed unchanged).

PR #740 did not implement BTTV settings, badges, native channel points,
updaters or other #741 additions. Legacy sources remain in the upstream
repository, but this port does not claim to activate them. The **31.8.0
React Native chat and emote paths** are the focus here. The older PR #740's
known stress/emote-spam stability issue is not fixed by this rebase.

The original `slop` branch's debugging snapshots, backup patches, forensic
PowerShell scripts, 31.2.0-specific code and duplicate smali assets are excluded.
