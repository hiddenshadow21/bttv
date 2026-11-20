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

## 2026-11-20: first on-device test failed silently; correction

The first experimental build did not restore chat. The user saw no
BTTVChatResize318 logs. Source review against the exact original
MiniPlayerController.smali found a concrete implementation error:

    .method public final isMinimized()Z

The earlier Java helper mistakenly reflected getMinimized(), a spelling
that JADX synthesized when rendering the Kotlin property in Java. The
actual Android DEX name is **isMinimized**. The helper treated failed
reflection as minimized, so even a legitimate keyboard resize would be
suppressed without a success log.

Corrected in the experimental branch:

- Look up isMinimized(), not getMinimized().
- Log immediately on install() invocation, after installation, every
  nonzero theatre height change, and when remeasurement is requested.
- Do not gate a genuine large height change on WindowInsets.Type.ime()
  already reflecting keyboard state: Android may dispatch insets after
  onLayoutChange, so previously both snapshots could read false.
- Added a source-level regression assertion for the real DEX method
  name, plus an APK-level DEX marker check.

No claim of runtime success is made until the rebuilt APK is tested.

### Update your *existing* experimental worktree and rebuild

From your primary repository root, in Windows PowerShell:

    git -C ..\bttv-ime-experiment fetch origin experiment/chat-keyboard-surface-remeasure-31.8.0
    git -C ..\bttv-ime-experiment switch --detach origin/experiment/chat-keyboard-surface-remeasure-31.8.0
    Push-Location ..\bttv-ime-experiment
    docker build --progress=plain --output "type=local,dest=./dist" .
    powershell -ExecutionPolicy Bypass -File .\v31\diagnostics\verify_ime_apk.ps1 -ApkPath .\dist\bttv-31.8.0.apk
    Pop-Location

The verifier must print "Current experimental hook found in DEX". If not,
stop: the wrong/old APK was built. This does **not** verify that the new
APK is installed on the phone.

After installing the compatible newly built APK, clear logcat, reopen a
stream so the theatre fragment starts, reproduce the keyboard issue,
then collect:

    adb logcat -c
    # Open stream, minimize/restore, open keyboard.
    adb logcat -d -v time -s BTTVChatResize318:V AndroidRuntime:E

Expected diagnostic progression:

1. "install invoked; root=true surface=true mini=true":
   the smali patch ran and dependencies were available.
2. "installed theatre layout watcher; ... mini=false": listener ready.
3. "theatre layout changed: height=...->...": resize observed.
4. "requesting RN remeasure..." / "IME-height transition: requested ...":
   native remeasurement requested.

If no **install invoked** line appears after opening a new stream, suspect
wrong installed APK, wrong theatre route, or a hook that did not run. If
install logs but no resize logs appear when keyboard opens, monitor the
actual activity window/parent container instead of adding more remeasure
calls. If remeasure is requested but chat remains absent, the culprit is
likely the Hermes layout/conditional rendering, not missing native
remeasure.
