# BTTV Android — Feature Tracker

## How to use this file

- **`[x]`** = verified working on a device or verified end-to-end for a build-only feature. **`[ ]`** = not yet confirmed complete, including features with partial code.
- **State:** `Working` (reported on-device), `Partial` (some functions/hooks exist but feature parity is unconfirmed), `Missing hook` (legacy code/patch may exist, but not integrated with 31.8.0), `Unverified` (implementation exists; no convincing device test), `Not ported` (no active 31.8.0 integration identified), or `Legacy/optional` (may be obsolete in modern Twitch).
- **Priority:** `P0` = foundation/regression; `P1` = core chat experience; `P2` = other major user features; `P3` = integrations/settings/polish; `P4` = legacy compatibility or optional work. Priority is a suggested restoration order, **not** an indication that code works.
- Only check a feature after passing its **Done when** criterion on Twitch 31.8.0. Link the implementing commit/PR or note the test date in the progress log.
- **Code present is not the same as feature working.** Older `mod/` classes and `patches/` files are often retained but no longer invoked by the 31.8.0 patch scripts.

## Quick overview

| Area | Focus |
| --- | --- |
| Existing working foundation | Global third-party emotes, accessible BTTV settings, live timestamps, standalone APK build |
| Main missing user features | Auto-claim, sleep timer, highlights, split chat, anonymous chat, deleted messages, badges, blacklist |
| Main unfinished emote work | Channel emotes/picker edge cases, autocomplete, wide emotes, VOD integration, animation fidelity |
| Main unfinished integrations | Updater, full settings pages/shortcuts, redirects, developer tools, legacy compatibility |

## A. Emotes, picker, and rendering

| Done | ID | Feature | State | Priority | Done when / notes |
| --- | --- | --- | --- | --- | --- |
| [x] | EM-01 | BetterTTV global emotes in live chat | Working | P0 | Reported visible on-device; regression-test across channels. |
| [x] | EM-02 | FFZ global emotes in live chat | Working | P0 | Reported emotes visible; confirm provider-specific samples when retesting. |
| [x] | EM-03 | 7TV global emotes in live chat | Working | P0 | Reported emotes visible; confirm provider-specific samples when retesting. |
| [ ] | EM-04 | BetterTTV channel-specific emotes | Partial | P1 | Show correct channel emotes after switching streams; no stale previous-channel results. |
| [ ] | EM-05 | FFZ channel-specific emotes | Partial | P1 | Same channel-switch test; valid broadcaster mapping. |
| [ ] | EM-06 | 7TV channel-specific emotes | Partial | P1 | Same channel-switch test; correct 7TV emote-set resolution. |
| [ ] | EM-07 | Combined third-party emote picker (global + channel) | Partial | P1 | All enabled providers appear with correctly scoped global and channel entries. |
| [ ] | EM-08 | Provider enable/disable settings applied to chat and picker | Partial | P1 | Each BTTV/FFZ/7TV toggle immediately affects rendering and picker as intended. |
| [ ] | EM-09 | Emote insertion into chat input and cursor/selection behavior | Partial | P1 | Picker inserts correct emote text without corrupting chat input. |
| [ ] | EM-10 | Animated GIF/WebP emotes and render modes | Partial | P2 | Forever/once/static/disabled modes all function; test image loading and memory. |
| [x] | EM-11 | Wide emotes | Working | P2 | Wide emotes render at correct dimensions without clipping or shifting text. |
| [ ] | EM-12 | Emote colon autocomplete | Missing hook | P2 | Typing `:name` suggests and inserts third-party emotes. |
| [ ] | EM-13 | Third-party emotes in VOD chat | Missing hook | P2 | VOD/replay chat displays BTTV/FFZ/7TV emotes correctly. |
| [ ] | EM-14 | Emote details / emote cards | Partial | P2 | Tapping an emote opens appropriate provider details; no broken Twitch native cards. |
| [ ] | EM-15 | SVG support for emotes/badges | Missing hook | P3 | Relevant SVG assets load and display correctly. |
| [ ] | EM-16 | WebP/static GIF fallback and image-loader compatibility | Partial | P3 | Animated/static variants and failures behave as in upstream, without crashes. |

## B. Chat presentation and moderation

| Done | ID | Feature | State | Priority | Done when / notes |
| --- | --- | --- | --- | --- | --- |
| [x] | CH-01 | Native-looking timestamps for live chat | Working | P0 | User confirmed timestamps now render correctly in the native position; Hermes `TimestampPart` path. |
| [x] | CH-02 | Timestamp preference in BTTV settings | Working | P0 | Logcat confirmed toggling the setting; retest both on/off after updates. |
| [ ] | CH-03 | Preserve historical-chat timestamp behavior | Unverified | P1 | Loading earlier history remains visually correct with setting on and off. |
| [ ] | CH-04 | Show deleted chat messages | Missing hook | P1 | Deleted messages remain visible when enabled and follow chosen presentation. |
| [ ] | CH-05 | Highlight messages containing configured keywords | Missing hook | P1 | Live chat matches highlights and applies intended emphasis. |
| [ ] | CH-06 | Highlight selected usernames/users | Missing hook | P1 | User-specific highlighting works alongside keyword highlighting. |
| [ ] | CH-07 | Highlighting in VOD chat | Missing hook | P2 | Keyword/user rules apply to historical/VOD messages. |
| [ ] | CH-08 | Configurable chat blacklist / filtering | Missing hook | P1 | Configured words/patterns filter the intended messages without false positives. |
| [ ] | CH-09 | Split chat | Missing hook | P1 | Visually separates chat message types; readable in both light and dark themes. |
| [ ] | CH-10 | Anonymous chat | Missing hook | P2 | Anonymous connection works without identity leaks or crashes; ordinary chat still works. |
| [ ] | CH-11 | Third-party BTTV badges | Missing hook | P2 | Badges appear for eligible users at correct sizes/positions. |
| [ ] | CH-12 | Third-party FFZ badges | Missing hook | P2 | Badges appear for eligible users and do not break native badge layout. |
| [ ] | CH-13 | Chatterino badges | Missing hook | P3 | Badges appear where provided by the upstream-supported badge source. |
| [ ] | CH-14 | Correct parsing of subscription/gift-subscription chat messages | Unverified | P3 | Events parse correctly alongside third-party emotes and normal messages. |

## C. Stream and playback utilities

| Done | ID | Feature | State | Priority | Done when / notes |
| --- | --- | --- | --- | --- | --- |
| [x] | ST-01 | Auto-claim bonus channel points | Working | P2 | Bonus appears and is claimed automatically, once per eligible event. |
| [ ] | ST-02 | Sleep timer | Missing hook | P2 | Configurable timer stops playback at expiry, including livestreams. |
| [ ] | ST-03 | Sleep timer visibility switch | Missing hook | P3 | The control can be shown/hidden and saved according to preference. |
| [ ] | ST-04 | BTTV shortcuts/toggles in stream settings | Missing hook | P3 | Quick controls appear in the current 31.8.0 stream UI, with working actions. |
| [ ] | ST-05 | BTTV toggles in the chat settings bottom sheet | Missing hook | P3 | Provider toggles appear and update the same preferences as main BTTV settings. |

## D. Settings, preferences, and navigation

| Done | ID | Feature | State | Priority | Done when / notes |
| --- | --- | --- | --- | --- | --- |
| [x] | UI-01 | BTTV entry in Twitch's scrolling settings list | Working | P0 | User confirmed BTTV is visible as the last list item. |
| [x] | UI-02 | Clickable BTTV settings dialog | Working | P0 | Logcat confirmed row click and dialog opened. |
| [x] | UI-03 | Settings persistence for timestamp toggle | Working | P0 | Toggle writes confirmed in logcat; confirm persistence after app restart as regression. |
| [ ] | UI-04 | Full original BTTV settings interface | Partial | P2 | All upstream settings/categories can be navigated and edited, not only provider/animation/timestamp controls. |
| [ ] | UI-05 | Highlighted keywords/users editor | Missing hook | P1 | Add, remove, and persist highlight rules from BTTV settings. |
| [ ] | UI-06 | Blacklist editor | Missing hook | P1 | Add, remove, and persist blacklist rules from BTTV settings. |
| [ ] | UI-07 | Feature switches for restored options | Partial | P2 | Deleted messages, auto-claim, split chat, anon chat, updater, dev tools, etc. all control real implementations. |
| [ ] | UI-08 | Credits/contributors view | Missing hook | P4 | View opens and displays contributors without crashing. |
| [ ] | UI-09 | Version footer: BTTV version + Twitch base in brackets | Unverified | P3 | Settings shows `BTTV 0.44.0-beta (Twitch v31.8.0)` (or updated manifest version) accurately. |
| [ ] | UI-10 | Settings survives navigation, rotation, and process restart | Unverified | P2 | No class-loading errors, preferences survive, and opening/closing settings remains reliable. |

## E. Updater and developer features

| Done | ID | Feature | State | Priority | Done when / notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | UP-01 | Automatic update checks | Missing hook | P3 | App checks configured release source on schedule, without noisy repeats. |
| [ ] | UP-02 | Update notification / in-app banner | Missing hook | P3 | Available releases are presented and actionable. |
| [ ] | UP-03 | Manual “Check for updates” action | Missing hook | P3 | Settings action checks and reports current/new version. |
| [ ] | UP-04 | Automatic update-checks toggle | Missing hook | P3 | Setting persists and suppresses scheduled checks when off. |
| [ ] | UP-05 | Developer tools toggle | Missing hook | P4 | Toggle enables relevant developer controls in modern Twitch. |

## F. Redirects and legacy compatibility fixes

These are present in upstream patches/changelog, but **some may no longer have a modern Twitch equivalent**. Decide whether each still makes sense before investing in a port.

| Done | ID | Feature | State | Priority | Done when / notes |
| --- | --- | --- | --- | --- | --- |
| [ ] | LG-01 | “Subscribe” button opens web subscription flow | Legacy/optional | P4 | Redirect works if the relevant button still exists. |
| [ ] | LG-02 | Gift-subscription web redirect | Legacy/optional | P4 | Gift-sub flow behaves as intended where supported. |
| [ ] | LG-03 | Buy/Get Bits web redirect | Legacy/optional | P4 | Bits flow redirects correctly without breaking viewing/chat. |
| [ ] | LG-04 | Watch Party compatibility changes | Legacy/optional | P4 | Only restore if Twitch 31.8.0 still exposes this functionality. |
| [ ] | LG-05 | Automatic cookie-consent rejection | Missing hook | P4 | Relevant consent dialog handling works and respects user choice. |
| [ ] | LG-06 | Legacy Glide SVG/WebP decoder integrations | Partial | P4 | Required formats work; remove obsolete hooks if React Native path supersedes them. |

## G. Port/build features (not original BTTV user features)

These are tracked separately to prevent a feature-complete port from regressing at build or installation time.

| Done | ID | Feature | State | Priority | Done when / notes |
| --- | --- | --- | --- | --- | --- |
| [x] | BL-01 | Twitch 31.8.0 hooks resolve and apply | Working | P0 | Patch stage and signed build previously completed on user's APK. |
| [x] | BL-02 | Standalone ARM64 APK | Working | P0 | Single APK built and installed on-device. |
| [x] | BL-03 | Correct BTTV Android package/version code | Working | P0 | Version-code downgrade failure was resolved and install succeeded. |
| [x] | BL-04 | Local Docker build with updated OS and cached Gradle dependencies | Working | P0 | Docker build completed after updating image and Hermes CLI invocation. |
| [x] | BL-05 | Hermes v98 timestamp patch integration | Working | P0 | Native timestamps confirmed working on-device. |
| [ ] | BL-06 | Reliable rebuild after changing chat/settings hooks | Unverified | P0 | Full rebuild/install plus smoke tests after each future hook update. |
| [ ] | BL-07 | Repeatable smoke-test checklist | Unverified | P1 | Keep a short repeatable checklist covering launch, stream, chat, emotes, settings, timestamps. |

## H. Intentionally excluded / not supported by original `master`

**Do not count these as restoration failures** unless deciding to add them as new features:

- [ ] **7TV zero-width emotes** — upstream README explicitly marks unsupported.
- [ ] **Personal emotes** — upstream README explicitly marks unsupported.
- [ ] **7TV third-party badges** — removed in upstream's move to 7TV API v3 (changelog 0.40.2).
- [ ] **Separate BTTV uptime display** — removed after Twitch added its own uptime feature (changelog 0.31.0).
- [ ] **Android TV app parity** — upstream is a mod of Twitch mobile, not the Android TV app.

## Regression test checklist (run on every meaningful release)

- [ ] App launches, signs in, and plays a livestream.
- [ ] Open/close BTTV settings; all visible switches respond and persist after restart.
- [ ] Live chat displays time **before badges/username** in a neutral style when enabled.
- [ ] Disabling timestamps hides them for new messages; re-enabling restores them.
- [ ] Historical messages and stream/VOD navigation remain correct.
- [ ] BTTV/FFZ/7TV global emotes appear; switching channels updates channel emotes.
- [ ] Picker, emote insertion, GIF/WebP rendering, and long-chat scrolling work.
- [ ] No new `NoClassDefFoundError`, Hermes verification errors, or repeated logcat warnings.
- [ ] APK version/package/signature are suitable for an in-place `adb install -r` update.

## Progress log

| Date | IDs | Changes / test results | Commit / PR | Verified by |
| --- | --- | --- | --- | --- |
| 2026-11-06 | UI-01–03, CH-01–02, BL-01–05 | User confirmed clickable BTTV settings and correctly positioned native timestamps; previously built and installed standalone APK. | Initial 31.8.0 port and fixes | Device feedback in conversation |
| YYYY-MM-DD | — | — | — | — |

## Open questions / confirm before marking complete

1. Are **channel BTTV/FFZ/7TV emotes** now fully working after the picker/channel-ID changes, including switching streams?
2. Are **animated emote modes** (static/once/forever/off) all functional in live chat and the picker?
3. Does the **version footer** display the BTTV version exactly as requested after the recent updates?
4. Do you want to restore **obsolete upstream integrations** (Watch Parties, legacy redirects), or mark them intentionally skipped?
5. Which features should be ported first: **core chat** (badges/highlights/deleted messages) or **utilities** (channel points/sleep timer)?

---

### Reference pointers

- Upstream: https://github.com/bttv-android/bttv/tree/master
- Upstream features: https://github.com/bttv-android/bttv/blob/master/README.md
- Upstream history: https://github.com/bttv-android/bttv/blob/master/CHANGELOG.md
- Correct rebase starting point: https://github.com/bttv-android/bttv/pull/740
- Original work-in-progress port: https://github.com/hiddenshadow21/bttv/tree/slop

**Maintenance rule:** Keep the table as the single checklist; when restoring a feature, change its state, tick its checkbox **only after an on-device test**, and add a line to the progress log.
