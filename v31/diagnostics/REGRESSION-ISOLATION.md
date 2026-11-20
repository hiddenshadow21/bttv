# Regression isolation: Twitch 31.8.0 blank chat with keyboard open

## What is confirmed

Device logs: the experimental ChatKeyboardRemeasure318 hook installed and
called RNSurfaceController.kickRemeasure() repeatedly on **2138 -> 1216 px**
keyboard-open transitions. Chat still disappeared, so another native
requestLayout does not solve the symptom.

Original Android UI snapshots: the React Native theatre host and video
persist, but the theatre-chat, chat-message-list and chat-input-bar subtrees
are missing in the failing keyboard-open layout.

## Why inspect newest BTTV changes

The rebase-31.8.0 tip (commit f72d1d0, November 7, 2026) introduced:

- SurfaceMountingManager.updateLayout() interception to override RN emote
  widths on *every* Fabric view layout operation;
- p040.getSize() and d240.m() inline-width modifications;
- BaseViewManager.setTestId() hook to track RN chat rows;
- ReactImageManager.setSource() wide-emote metadata observation;
- SplitChat318 attach/layout callbacks and RN backgrounds/separators.

The subsequent rebase-31.8.0-dev changes also registered zero-width
wrappers and card callbacks via SplitChat318.onTestId, and a native
EmoteCard text callback in ReactTextViewManager.updateExtraData().

These are **possible regressions, not proven bugs**. Original Twitch
keyboard-height responsive layout may also be involved. We do not yet know
the user's last working BTTV commit/hash.

## What this isolation build changes

Base: rebase-31.8.0-dev (NOT the experimental IME-remeasure branch).

Only for this A/B build, it omits five RN view-decoration groups:

1. BaseViewManager.setTestId() -> SplitChat318 hook.
2. SurfaceMountingManager.updateLayout() global width override.
3. Inline RN span/text width overrides (p040 and d240).
4. ReactImageManager.setSource() wide-emote observation; the original
   third-party emote URL rewriting is retained.
5. Newly added ReactTextViewManager EmoteCard text callback.

The remaining 31.8.0 BTTV hooks, network/chat transport, IRC/timestamps,
and native OneChat remain unchanged. **Expected temporary differences:**
split-chat styling, wide-emote/zero-width overlay placement, and card
labels may not work normally. Do not merge this branch as a final fix.

The original Twitch APK and Hermes bundle stay the same, so if the
keyboard still removes chat, investigate Hermes/insets, remaining BTTV
hooks, or an underlying Twitch regression instead.

## Build and compare

From the normal bttv-clean repository root, Windows PowerShell:

    git fetch origin isolation/remove-new-rn-visual-hooks-31.8.0
    git worktree add --detach ..\bttv-rn-isolation FETCH_HEAD
    Copy-Item .\twitch.zip ..\bttv-rn-isolation\twitch.zip
    Push-Location ..\bttv-rn-isolation
    docker build --progress=plain --output "type=local,dest=./dist" .
    Pop-Location

Before installing, check signing compatibility with the installed BTTV.
Do NOT uninstall your active app simply to test this hypothesis.

### Acceptance test

1. Confirm normal chat and composer with keyboard closed.
2. Minimize the stream, restore it, then open the keyboard.
3. Check whether chat remains mounted and usable.
4. Dismiss/reopen the keyboard 2-3 times without closing stream.
5. Report the result, without changing unrelated settings between builds.

If chat stays visible, the visual-hook additions are implicated; restore
one group at a time, starting with SurfaceMountingManager.updateLayout().
If chat still vanishes, do not assume visual hooks caused it, and proceed
to Hermes/insets plus remaining input hooks.

**This isolation build has not been runtime tested.**
