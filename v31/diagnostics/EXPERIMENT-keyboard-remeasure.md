# Experimental patch: RN theatre remeasure on IME height transitions (Twitch 31.8.0)

**Do not merge as a confirmed fix.** This is an isolated on-device
diagnostic/mitigation candidate, based on unmodified Twitch 31.8.0 smali
and the uploaded Android view hierarchy snapshots.

## Evidence from the actual Twitch 31.8.0 decompilation

The uploaded twitch318-decompiled.zip contains the readable Java and exact
smali for these classes:

- tv/twitch/android/feature/discovery/feed/rn/theatre/TwitchRNTheatreFragment
- tv/twitch/android/feature/discovery/feed/rn/theatre/MiniPlayerController
- tv/twitch/android/feature/discovery/feed/rn/runtime/RNSurfaceController
- tv/twitch/android/feature/viewer/landing/ViewerLandingActivity

The decoded original AndroidManifest.xml declares
ViewerLandingActivity with android:windowSoftInputMode="adjustResize".
The React Native theatre root is inflated via
res/layout/twitch_rn_theatre_fragment.xml and attached to
RNSurfaceController in TwitchRNTheatreFragment.onCreateView().

TwitchRNTheatreFragment.expandPlayer() calls kickSurfaceRemeasure() after
restoring the player. onConfigurationChanged() also does so when appropriate,
but IME/window resize is not normally an orientation/configuration callback.
The private kickSurfaceRemeasure() calls public RNSurfaceController methods
kickRemeasure() or kickRemeasureAfterNextLayout(). They re-request a layout
on the existing RN root view, not restart the stream.

Both the user report and diagnostic capture point at the software keyboard:
the original broken view tree had a 922 px theatre shrink and no theatre-chat,
chat-message-list, or chat-input-bar nodes, but the RN theatre host and video
remained. In the second capture, keyboard was hidden for every snapshot and
chat nodes were present. Missing RN subtrees could reflect JS conditional
rendering, not only a stale native measurement, so a remeasure is only a
hypothesis and might not be sufficient.

JADX logged errors for other app classes; these specific classes are present
in readable output. Exact smali anchor and 4-bit register validations were
performed against the uploaded file.

## Experimental change

- Add bttv/ChatKeyboardRemeasure318.java, a lifecycle-scoped
  View.OnLayoutChangeListener attached only to the RN theatre root.
- It watches for large height changes (120dp threshold); when keyboard
  was reported visible at either endpoint and player is expanded, it calls
  the existing public RNSurfaceController.kickRemeasure() once via reflection.
  The reflection is specific to the verified original class and fails closed.
- A second hook uninstalls the listener in onDestroyView().
- No global AndroidManifest soft-input changes, chat text rewrites, emote
  replacements, forced full React Native remount, or stream restarts.
- Fail-closed, atomic smali patching: verified the target's original
  onViewCreated .locals 5, onDestroyView .locals 2, field signatures and
  super-call anchor, plus tests for missing anchor and idempotence.

## Build (separate worktree)

From the original BTTV repo root, Windows PowerShell:

    $repo = (Get-Location).Path
    git fetch origin experiment/chat-keyboard-surface-remeasure-31.8.0
    git worktree add --detach ..\bttv-ime-experiment FETCH_HEAD
    Copy-Item -LiteralPath "$repo\twitch.zip" -Destination ..\bttv-ime-experiment\twitch.zip
    Push-Location ..\bttv-ime-experiment
    docker build --progress=plain --output "type=local,dest=./dist" .
    Pop-Location

This compiles an experimental APK in the separate worktree. Before
installing, check signing certificate compatibility with the installed BTTV:
a new signing key may prevent updating in place and uninstalling the old app
would erase its local app data. Do not uninstall just to test a hypothesis.

## Device acceptance test

1. Open a stream; verify video, messages and composer appear.
2. Minimize; restore; tap composer to open the keyboard.
3. Verify whether theatre-chat persists and messages/composer remain usable.
4. Repeat with keyboard dismissed, then reopened; verify neither split-chat
   rows nor emote input regressed.
5. Optional filtered diagnostics after reproduction:

       adb logcat -d -s BTTVChatResize318:I AndroidRuntime:E

A successful marker "IME-height transition: requested RN theatre remeasure"
only establishes that the hook ran, **not** that chat recovered. If the
marker appears while chat still disappears, the next step is mapping the
Hermes TheatreScreen conditional that removes theatre-chat when the app window
shrinks (instead of adding more native requestLayout calls).
