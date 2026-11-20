# Twitch 31.8.0: chat disappears after restoring minimized player

Symptoms confirmed by screenshots: video keeps playing; after minimize -> restore,
video area becomes too short and the chat messages/composer are absent. Leaving
and reopening the stream restores the layout. This branch adds **diagnostics
only**, not an app patch or a claimed fix.

## Capture the working and broken layouts (Windows / PowerShell)

You need an Android phone connected over ADB with USB debugging authorized.

1. Download [capture_chat_restore.ps1](capture_chat_restore.ps1) to its directory
   in your checkout: v31/diagnostics/capture_chat_restore.ps1. Running it from
   the repository checkout keeps the ZIP under dist/.
2. From the repository root run:

   powershell -ExecutionPolicy Bypass -File .\v31\diagnostics\capture_chat_restore.ps1

   If more than one ADB device is connected, add -Serial DEVICE_SERIAL.
3. Follow the prompts: capture a normal stream with keyboard closed.
   Then **keep the keyboard OPEN** on the broken stream until the second snapshot
   completes. Dismiss the keyboard without closing the stream for the third
   snapshot. Note whether chat returns.
4. The script saves IME state **before** the UI hierarchy dump, warns if the
   keyboard was not reported as open for the broken snapshot, and saves
   screenshots locally as PRIVATE files (not in the ZIP).
5. The script creates dist/chat-restore-TIMESTAMP.zip. **Review the ZIP for
   sensitive data** before uploading it to this conversation.

The initial capture showed a 922-pixel window-height reduction alongside a
missing chat subtree, so the third snapshot is specifically designed to
differentiate IME/window-resize behavior from the mini-player transition.
See [2026-11-20 findings](REPORT-2026-11-20.md).

The ZIP contains limited logcat tags, class names and bounds from Android's
accessibility hierarchy (not message text), and selected window/activity
state. The temporary raw accessibility XML is deleted after sanitization.
These snapshots may be incomplete for React Native/Fabric, and the absence of
a log entry does not prove a lifecycle callback did or did not run.

## Decompiled Twitch source: useful, but only a targeted subset initially

Please use the **unmodified Twitch 31.8.0 APK that was the input to the
installed BTTV build**, not a second unrelated Twitch version. If you already
have apktool-decoded smali, the highest-value classes are:

- the Twitch React Native theatre fragment (often named
  TwitchRNTheatreFragment.smali; search all smali* directories);
- tv/twitch/android/feature/theatre/TheatreModeFragment.smali;
- mini-player controller/fragment classes (filenames containing MiniPlayer,
  Miniplayer or MiniaturePlayer), plus their direct navigation callers;
- com/facebook/react/fabric/mounting/SurfaceMountingManager.smali and
  com/facebook/react/fabric/FabricUIManager.smali;
- relevant player/theatre navigation or chat-host fragment classes, if their
  names are exposed by the lifecycle log.

Include the relative paths in a ZIP so that similarly named smali files remain
distinguishable. If the React Native theatre class isn't obvious, send the
log/UI evidence first; we can narrow the exact class names from that. Avoid
uploading credentials, internal app data, tokens, session files or private
device logs. Full APK files are not required at this stage.

## What the code review identified

- v31/tests/test_minimized_chat_channel.py covers IRC room context and emote
  preloading; it does not test the player restore UI lifecycle.
- mod/app/src/main/java/bttv/SplitChat318.java decorates mounted RN chat rows;
  its attach/detach callbacks cannot themselves prove the chat surface mounted.
- mod/app/src/main/java/bttv/IrcEmotes.java updates foreground broadcaster
  on ROOMSTATE, which may also arrive from background sockets. This is a
  separate possible channel-state issue, not proven to hide the chat container.
- The screenshot's shrunken video height suggests a parent theatre-layout or
  window-insets issue; don't force-recreate chat or reload the stream blindly.

The next code change should be based on the class and layout transition seen
in the two snapshots. Keep the app/runtime patch separate from diagnostic work.

## Follow-up: IME-dependent failure in the user's capture

The second user ZIP (`chat-restore-20261120-184959.zip`) captured the IME
*closed* in all three states; the RN theatre and chat tree were fully mounted
in all three. The original broken snapshot had a 922 px theatre height shrink
and omitted `theatre-chat`, `chat-message-list` and `chat-input-bar`.
The user has now confirmed that this black-chat problem appears only with the
keyboard open. Prefer investigating React Native responsive theatre layout,
Android soft-input/window insets and minimized-player restore state, not
emote replacement or row painting. Do not assume the root cause is proven.

To investigate the actual layout condition, the Twitch 31.8.0 Hermes/React
Native bundle that contains `theatre-screen` / `theatre-chat` may be more
informative than Java chat-message smali. Request targeted files or an
extracted map when available, not a full user-data dump.

## Docker-only source extraction

A standalone [Docker decompiler](decompile/README.md) is now available
on this diagnostics branch. It reads the original 31.8.0 twitch.zip/.apkm
with Apktool + JADX entirely inside Docker; it does not install Java or
decompilation tools on the host, modify the original APK, or build/install
BTTV. It exports full smali/Java plus the raw Hermes bundle and a targeted
chat-restore-review.zip for upload.

Windows PowerShell (repository root):

    powershell -ExecutionPolicy Bypass -File .\v31\diagnostics\decompile\run.ps1
