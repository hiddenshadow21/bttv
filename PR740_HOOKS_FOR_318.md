# React Native port map — Twitch 31.8.0

Upstream *draft* port: https://github.com/bttv-android/bttv/pull/740  
Source hook script: https://raw.githubusercontent.com/asong91/bttv/31.5.2/v31/apply_hooks.sh

PR #740 targets **31.5.2** and has a known report of crashes with heavy emote spam; it is a research baseline, not a drop-in fix for the current **31.8.0** binary. Do not run `v31/apply_hooks.sh` directly on 31.8.0.

| Priority | Anchor to locate in 31.8 | PR #740 hook / behavior | Validation before patching |
|---|---|---|---|
| 1 | Listener of `com/facebook/react/modules/websocket/WebSocketModule` emitting `websocketMessage` | `Hooks.onWebSocketText` rewrite inbound IRC and ROOMSTATE | Match listener method signature, session ID field, and string argument register; confirm the app uses this path |
| 2 | `com/facebook/react/modules/network/NetworkingModule.sendRequest` | `Hooks.interceptHttpRequest` to enrich the emote picker (`ChatEmoteSets`) and emote detail card (`EmoteCard`) responses | Inspect exact method descriptors, parameter registers, request routing; do not suppress other network requests |
| 3 | React Native image view `setSource`, source-object constructor | `Hooks.imageUri` and `onImageViewSource` to load BTTV URLs/width | Find via `ReactImageManager`, `ReactImageView`, and string URI references; check image library and view signatures |
| 4 | `com/twitchrn/emoteinput/` | `inputEmoteUrl`, loader, dimensions, animation | Validate span and loader types; leave animation hook out until baseline rendering works |
| 5 | `tv/twitch/android/settings/main/MainSettingsFragmentV2` and menu routing | A **separate** 31.8 settings UI hook; PR #740 does not port settings | Trace real screen construction and correct version label source |

The original PR #740 uses obfuscated 31.5.2 classes `xm90` (WS listener), `knl` (ImageSource), `fw30` (text transform), `jt30` (ReplacementSpan) and `hcw` (ReactImageView). **These names are not valid evidence of the equivalents in 31.8.0.**

The already-uploaded global 31.8.0 index contains `smali_classes3/com/facebook/react/modules/websocket/WebSocketModule.smali`, `smali_classes3/com/facebook/react/modules/network/NetworkingModule.smali` and `smali_classes4/com/twitchrn/emoteinput/TwitchEmoteInputView.smali`. It also references `smali_classes3/fy90.smali` and `smali_classes3/spo.smali` alongside `WebSocketModule`; these are *candidate*, not verified, listener types.

The collector ZIP from this kit will include the 31.8.0 smali needed to establish exact mappings and produce compile-testable hooks. The settings version-label script is optional and changes only a native `TextView` (if one exists); it does not change APK metadata or guarantee changes to Compose-rendered labels.
