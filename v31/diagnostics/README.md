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
3. Follow the prompts: capture a normal stream with chat visible, then minimize
   and restore the stream until the video plays but chat is black. Keep the
   keyboard in the same state for both snapshots (preferably closed).
4. The script creates dist/chat-restore-TIMESTAMP.zip. **Review the ZIP for
   sensitive data** before uploading it to this conversation.

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
