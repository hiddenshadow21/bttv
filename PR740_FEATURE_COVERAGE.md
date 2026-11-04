# PR #740 versus the current Twitch 31.8.0 port

Source reviewed: https://github.com/bttv-android/bttv/pull/740 and its `v31/apply_hooks.sh`, `bttv.IrcEmotes`, `bttv.api.Hooks`, `bttv.emote.RNEmoteMenu`, and input classes.

| Feature | PR #740 (Twitch 31.5.2) | Current 31.8.0 port / status |
|---|---|---|
| React Native IRC emote tags | `IrcEmotes.rewriteFrame` from WebSocket listener | `RNFeatureHooks318.rewriteFrame` in `fy90.n`, active in phone logs; catalog-dependent |
| Early channel resolution | `IrcEmotes.onRoomState` | **This kit adds it** to the existing RN hook so `Data.setCurrentBroadcasterId` fetches channel emotes |
| RN image URL rewriting | ImageSource/ReactImageView | Existing ReactImageManager and TwitchEmoteInputView hook; runtime unverified |
| RN chat picker | `ChatEmoteSets` GraphQL request/response augmentation | Existing `RNFeatureHooks318.interceptNetwork`; phone log confirms request interception, but catalogs were empty due to missing OkHttp class |
| Clickable emote card | `RNEmoteCard` synthetic EmoteCard response | **Not ported/verified** in current 31.8.0 integration |
| Wide/zero-width emotes | ReplacementSpan width, layout and render hooks | **Not ported**; draft PR reports crashes under heavy emote spam |
| RN input images | bitmap caching, ratio handling and animation | Only URL rewrite hook ported; remainder not yet validated |
| Chat timestamps | Not implemented in PR #740 | **This kit adds `[HH:mm]` text prefixes** to ordinary IRC `PRIVMSG` (including emoji-correct emote-offset shifts) |
| Automatic channel-point bonus | Not implemented in PR #740 | Existing port of native `ic9 → qf9.E(...)` claim callback; **runtime activation & credited points unverified** |
| BTTV settings | Separate legacy settings code | User confirmed visible and working on 31.8.0; this kit does not alter it |

## Critical prerequisite

The last phone trace showed `NoClassDefFoundError: okhttp3.Callback` before any external-emote catalogs loaded. Complete the separate `twitch318-network-dependency-audit-v3.zip` migration (Network.java, Badges.java, updater/Updater.java, updater/UpdaterActivity.java, ChannelPoints.java). This kit intentionally does not duplicate or overwrite that migration.

## Channel-points test

The 31.8.0 native `z89.smali.patch` targets `Lic9` and injects a call to `ChannelPoints.shouldAutoRedeem(claimId)` followed by `Lqf9;->E(claimId, null)` when enabled. That is a real invocation point in the decoded native method. Yet the app may have a React Native channel-points UI; the native method could never execute. After the v3 migration, `ChannelPoints.java` logs the decision as `BTTV318Points` (no claim IDs). Leave a channel open until a bonus chest is actually available; if the decision never logs, capture a broader log and investigate the active bonus UI. A claim decision is not proof that points were credited.

## Timestamp caveat

These are IRC message-content prefixes, not a separate styled React Native component. They change the displayed chat text but keep existing Twitch/BTTV `emotes=` ranges aligned. The feature is always on in this test build, and skips CTCP `/me` messages. Do not treat it as fully tested until a real chat containing Twitch and external emotes is rendered without position errors.
