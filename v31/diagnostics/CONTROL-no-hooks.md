# Twitch 31.8.0 no-hooks control build

**Purpose:** Determine whether the keyboard-open disappearance of the React
Native theatre/chat subtree persists when no BTTV smali/Hermes modifications
run. This is an A/B isolation experiment, NOT a replacement for a working BTTV.

The earlier visual-isolation test (isolation/remove-new-rn-visual-hooks-31.8.0)
still reproduced the bug. It had disabled RN mounting/row/wide-emote hooks,
but **left the original Hermes timestamp bytecode patch and all other BTTV
hooks enabled**. Therefore it did not prove a stock Twitch regression.

## Differences from regular BTTV

- v31/apply_hooks.sh resets the APK to its freshly decoded base and applies
  **zero** smali patch functions and **zero** Hermes bytecode modifications.
  It asserts a clean git diff before returning.
- bttv.manifest.json versionName is 0.44.0-control, with the SAME
  versionCode (01208000339) and package (tv.twitch.bttvandroid.app).
- The existing standalone build pipeline still repacks/merges the same original
  Twitch 31.8.0 APK+splits, renames its package and signs it.
- The builder **still includes compiled bttv classes in a DEX** but no native
  hooks reference them, so those classes should not run. The manifest and
  repackaged resources also differ from the official app. Therefore this is a
  *no-hooks packaging control*, not a byte-for-byte stock Twitch release.
- Expected: all BTTV enhancements (emotes, split chat, timestamps, etc.) are
  disabled for this diagnostic build.

## Build (Windows PowerShell)

From your main bttv-clean repository root:

    git fetch origin isolation/twitch-only-control-31.8.0
    git worktree add --detach ..\bttv-control FETCH_HEAD
    Copy-Item .\twitch.zip ..\bttv-control\twitch.zip
    Push-Location ..\bttv-control
    docker build --progress=plain --output "type=local,dest=./dist" .
    Pop-Location

Build output: ..\bttv-control\dist\bttv-31.8.0.apk.
The Docker build log MUST include:

    BTTV_CONTROL_NO_HOOKS: clean Twitch 31.8.0 smali + original Hermes bundle

If it instead says "Hermes v98: enabled native timestamps", you built
the WRONG branch or a stale image: do not test it as a control.

After installing the control APK, confirm that the package version is
0.44.0-control (e.g. via Android app details or dumpsys package).

The APK **may not update** your currently installed app if signed by a
different signing key. DO NOT uninstall or wipe user data just to install a
diagnostic build. If signature compatibility is unknown, verify first.

## Test

1. Open a stream in the 0.44.0-control build.
2. Minimize, restore, open the chat keyboard.
3. Observe whether chat/metadata still disappear.
4. Dismiss and reopen the keyboard without leaving the stream.

Please report one of:

- **Chat works**: the regression requires some BTTV code or Hermes patch.
  Then bisect input/text, network, and Hermes hooks separately to identify
  the offending patch without changing underlying Twitch 31.8.
- **Chat still disappears**: the problem persists even with *all* BTTV hooks
  disabled. Investigate original Twitch 31.8 Hermes keyboard response,
  Android soft-input/insets, and packaging differences. A clean original
  Twitch 31.8 app comparison would then establish the role of repackaging.
- **Control build won't open**: a control packaging/runtime issue; capture
  AndroidRuntime errors and do not interpret as the chat bug.

## Relevant evidence

- First capture: 2138 px theatre height with keyboard closed / 1216 px with
  keyboard open; chat subtree absent only in broken view hierarchy.
- User's remeasure test: successful RN surface remeasure calls on IME changes
  still did not restore chat.
- User's visual-hook isolation test: keyboard-open failure persists even when
  global RN row/Fabric/wide-emote hooks are disabled.
- The selected ReactNativeJS log includes theatre/chat initialization but no
  conclusive stack trace explaining the subtree disappearance.

This branch is diagnostic only and must not be merged as a BTTV release.
