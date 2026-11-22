#!/usr/bin/env python3
"""Fail-closed 31.8.0 hook relocation for PR #740's bttv.api.Hooks.

Each anchor is selected from the 31.8.0 `slop` port's smali patch contexts.
No 31.2.0 mod code or PR #741 patch infrastructure is imported.

This script expects apktool-decoded base.apk under /usr/build/work (or --work).
It makes no changes unless *every* anchor matches uniquely.
"""
import argparse
from pathlib import Path
import re
import sys


class PatchError(RuntimeError):
    pass


def select(work: Path, name: str) -> Path:
    matches = sorted(work.glob('smali*/' + name))
    if len(matches) != 1:
        raise PatchError(f'{name}: expected exactly one decoded smali file, got {len(matches)}')
    return matches[0]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise PatchError(f'{label}: expected one original instruction sequence, got {count}')
    return text.replace(old, new, 1)


def change_method(text: str, signature: str, transform, label: str) -> str:
    # Keep changes inside the intended method, even if another method has the same opcodes.
    start = text.find(signature)
    if start < 0 or text.find(signature, start + len(signature)) >= 0:
        raise PatchError(f'{label}: missing or non-unique method signature')
    end = text.find('.end method', start)
    if end < 0:
        raise PatchError(f'{label}: missing .end method')
    body = text[start:end]
    changed = transform(body)
    if changed == body:
        raise PatchError(f'{label}: unchanged')
    return text[:start] + changed + text[end:]


def locate_method(text: str, name: str) -> str:
    matches = re.findall(r'(?m)^\.method[^\n]*\b' + re.escape(name) + r'\([^\n]*\)[^\n]*\n', text)
    if len(matches) != 1:
        raise PatchError(f'{name}: expected one method declaration, got {len(matches)}')
    return matches[0]


def app(text: str) -> str:
    anchor = '    invoke-virtual {v1}, Ltv/twitch/android/app/consumer/TwitchApplication;->b()V\n'
    return change_method(text, locate_method(text, 'onCreate'),
        lambda body: replace_once(body, anchor,
            anchor + '\n    # BTTV 31.8: initialize PR740 React Native hooks\n'
            '    invoke-static {v1}, Lbttv/api/Hooks;->onAppCreate(Landroid/content/Context;)V\n', 'app onCreate'),
        'app onCreate')


def websocket(text: str) -> str:
    anchor = '.method public final n(Lnpw;Ljava/lang/String;)V\n    .locals 3\n'
    snippet = ('\n    # BTTV 31.8: 31.8.0 WebSocketModule listener\n'
               '    iget v0, p0, Lfy90;->f:I\n'
               '    invoke-static {v0, p2}, Lbttv/api/Hooks;->onWebSocketText(ILjava/lang/String;)Ljava/lang/String;\n'
               '    move-result-object p2\n')
    return replace_once(text, anchor, anchor + snippet, 'WebSocket text')


def network(text: str) -> str:
    anchor = ('.method public sendRequest(Ljava/lang/String;Ljava/lang/String;D'
              'Lcom/facebook/react/bridge/ReadableArray;Lcom/facebook/react/bridge/ReadableMap;'
              'Ljava/lang/String;ZDZ)V\n    .locals 1\n')
    snippet = ('\n    # BTTV 31.8: PR740 GraphQL EmoteCard / ChatEmoteSets interceptor\n'
               '    invoke-static/range {p0 .. p11}, Lbttv/api/Hooks;->interceptHttpRequest('
               'Ljava/lang/Object;Ljava/lang/String;Ljava/lang/String;DLjava/lang/Object;'
               'Ljava/lang/Object;Ljava/lang/String;ZDZ)Z\n'
               '    move-result v0\n'
               '    if-eqz v0, :bttv318_network_continue\n'
               '    return-void\n'
               '    :bttv318_network_continue\n')
    return replace_once(text, anchor, anchor + snippet, 'NetworkingModule.sendRequest')


def image_manager(text: str) -> str:
    anchor = ('    .annotation runtime Lcom/facebook/react/uimanager/annotations/ReactProp;\n'
              '        name = "source"\n'
              '    .end annotation\n\n')
    snippet = ('    # BTTV 31.8: capture original wide-emote IDs before URL translation\n'
               '    invoke-static {p1, p2}, Lbttv/api/Hooks;->onImageViewSource(Ljava/lang/Object;Ljava/lang/Object;)V\n'
               '    # BTTV 31.8: rewrite emote image sources copy-on-write\n'
               '    invoke-static {p2}, Lbttv/api/Hooks;->rewriteReactSources(Ljava/lang/Object;)Ljava/lang/Object;\n'
               '    move-result-object p2\n'
               '    check-cast p2, Lcom/facebook/react/bridge/ReadableArray;\n\n')
    return replace_once(text, anchor, anchor + snippet, 'ReactImageManager source prop')


def input_target(text: str) -> str:
    anchor = ('.method public constructor <init>(IIILjava/lang/String;Ljava/lang/Integer;)V\n'
              '    .locals 0\n')
    snippet = ('\n    # BTTV 31.8: RN emote input URL\n'
               '    invoke-static {p4}, Lbttv/api/Hooks;->inputEmoteUrl(Ljava/lang/String;)Ljava/lang/String;\n'
               '    move-result-object p4\n')
    return replace_once(text, anchor, anchor + snippet, 'EmoteSpanTarget constructor')


def input_loader(text: str) -> str:
    anchor = ('.method private final fetch(Ljava/lang/String;)Landroid/graphics/Bitmap;\n'
              '    .locals 2\n')
    snippet = ('\n    # BTTV 31.8: PR740 cached emote bitmap\n'
               '    invoke-static {p1}, Lbttv/api/Hooks;->inputEmoteBitmap(Ljava/lang/String;)Landroid/graphics/Bitmap;\n'
               '    move-result-object v0\n'
               '    if-eqz v0, :bttv318_input_stock_fetch\n'
               '    return-object v0\n'
               '    :bttv318_input_stock_fetch\n')
    return replace_once(text, anchor, anchor + snippet, 'EmoteImageLoader.fetch')


def input_span(text: str) -> str:
    # The 31.8.0 port identifies this exact drawBitmap site, but does not verify
    # 31.5.2's getSize / add-float register assumptions. Do not copy those hooks.
    anchor = ('    invoke-virtual {p1, p5, p2, p3, p0}, Landroid/graphics/Canvas;'
              '->drawBitmap(Landroid/graphics/Bitmap;Landroid/graphics/Rect;'
              'Landroid/graphics/RectF;Landroid/graphics/Paint;)V\n')
    snippet = ('    # BTTV 31.8: preserve PR740 animated emote drawing\n'
               '    invoke-static {p5, p1, p3, p0}, Lbttv/api/Hooks;->drawInputEmote('
               'Landroid/graphics/Bitmap;Landroid/graphics/Canvas;'
               'Landroid/graphics/RectF;Landroid/graphics/Paint;)Z\n'
               '    move-result v0\n'
               '    if-eqz v0, :bttv318_draw_stock\n'
               '    return-void\n'
               '    :bttv318_draw_stock\n')
    return replace_once(text, anchor, snippet + anchor, 'EmoteImageSpan.draw')


def input_view(text: str) -> str:
    return change_method(text, locate_method(text, 'onAttachedToWindow'),
        lambda body: replace_once(body, '    return-void\n',
            '    # BTTV 31.8: refresh animated emote input\n'
            '    invoke-static {p0}, Lbttv/api/Hooks;->onInputViewAttached(Ljava/lang/Object;)V\n'
            '    return-void\n', 'TwitchEmoteInputView return'),
        'TwitchEmoteInputView.onAttachedToWindow')



def settings_fragment_context(text: str) -> str:
    """Capture the real Activity-backed Context from MainSettingsFragmentV2.

    This uses the Fragment's requireContext(), not the possibly overridden
    Compose LocalContext. Preserve Apktool's optional `.line` metadata.
    """
    signature = '.method public final onCreateView(Landroid/view/LayoutInflater;Landroid/view/ViewGroup;Landroid/os/Bundle;)Landroid/view/View;\n'
    pattern = re.compile(
        r'(    invoke-virtual \{p0\}, Landroidx/fragment/app/m;->requireContext\(\)Landroid/content/Context;\n'
        r'(?:\s*\.line [0-9]+\n)*'
        r'    move-result-object p3\n)')
    def patch(body):
        matches = list(pattern.finditer(body))
        if len(matches) != 1:
            raise PatchError(f'MainSettingsFragmentV2 host context: expected one requireContext site, got {len(matches)}')
        position = matches[0].end()
        return (body[:position] +
                '    # BTTV 31.8: capture actual settings Fragment host context\n'
                '    invoke-static {p3}, Lbttv/settings/SettingsOverlay318;->rememberContext(Landroid/content/Context;)V\n'
                + body[position:])
    return change_method(text, signature, patch, 'MainSettingsFragmentV2 host context')


def settings_compose(text: str) -> str:
    """Insert a real scrollable Compose settings row into Twitch 31.8.0.

    The visible screen is MainSettingsFragmentV2 via l7m -> vo2 -> ilj.h,
    *not* the old MainSettingsFragment backed by xpo/xoz/qnc.

    ilj.m is the existing click-enabled settings row component. The current
    Compose LocalContext and an explicit cpi callback are supplied to it.
    """
    signature = locate_method(text, 'h')
    # ilj has a unique h() method with a long Compose signature; explicitly
    # check the type to avoid hitting an unrelated obfuscated overload.
    if not signature.startswith('.method public static final h(Lcpi;ZZZZZZ'):
        raise PatchError('Compose settings: ilj.h has an unexpected signature')
    anchor = ('    invoke-static {v7, v8, v0, v2}, Lilj;->d(ZLcpi;Lb0a;I)V\n\n'
              '    shr-int/lit8 v2, v37, 0x15\n')
    snippet = ("""    invoke-static {v7, v8, v0, v2}, Lilj;->d(ZLcpi;Lb0a;I)V

    # BTTV 31.8: native scrolling Compose row, alongside other settings items
    # v0 is the active s0j composer at this site (not an Activity).
    # Compose has finished using v2 for the preceding row. The next instruction
    # reinitializes it, so v2 is safe as a 4-bit invoke argument register.
    sget-object v2, Lrq0;->b:Licf;
    invoke-virtual {v0, v2}, Ls0j;->m(Landroidx/compose/runtime/g;)Ljava/lang/Object;
    move-result-object v2
    check-cast v2, Landroid/content/Context;
    new-instance v15, Lbttv/compat/SettingsClick318;
    invoke-direct {v15, v2}, Lbttv/compat/SettingsClick318;-><init>(Landroid/content/Context;)V
    const-string v13, "BTTV settings"
    const/4 v14, 0x0
    const v16, 0x7f080673
    const/16 v17, 0x0
    move-object/from16 v18, v0
    const/16 v19, 0x0
    const/16 v20, 0x12
    invoke-static/range {v13 .. v20}, Lilj;->m(Ljava/lang/String;Ljava/lang/String;Lcpi;ILdhj;Lb0a;II)V

    shr-int/lit8 v2, v37, 0x15
""")
    return change_method(text, signature,
                         lambda body: replace_once(body, anchor, snippet,
                                'MainSettingsFragmentV2 Compose row'),
                         'MainSettingsFragmentV2 Compose row')


SETTINGS_CLICK_SMALI = """.class public final Lbttv/compat/SettingsClick318;
.super Ljava/lang/Object;
.implements Lcpi;

.field private final context:Landroid/content/Context;

.method public constructor <init>(Landroid/content/Context;)V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Lbttv/compat/SettingsClick318;->context:Landroid/content/Context;
    return-void
.end method

.method public invoke()Ljava/lang/Object;
    .locals 2
    const-string v0, "LBTTVSettings318"
    const-string v1, "Compose BTTV settings click invoked"
    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    iget-object v0, p0, Lbttv/compat/SettingsClick318;->context:Landroid/content/Context;
    invoke-static {v0}, Lbttv/settings/SettingsOverlay318;->open(Landroid/content/Context;)V
    sget-object v0, Lg760;->a:Lg760;
    return-object v0
.end method
"""


def react_text_manager(text: str, name: str) -> str:
    """Hook the actual 31.8.0 text payload field, not a nonexistent getText().

    The decoded RN managers use concrete payload classes:
      qjw.a: Spannable, PreparedLayout.a: android.text.Layout.
    Both are verified from the provided 31.8.0 smali archive.
    """
    if name.endswith('/ReactTextViewManager.smali'):
        signature = '.method public updateExtraData(Lrjw;Ljava/lang/Object;)V\n'
        anchor = '    iget-object v0, p2, Lqjw;->a:Landroid/text/Spannable;\n'
        replacement = (anchor +
            '    # BTTV 31.8: style real RN Spannable after text update is decoded\n'
            '    invoke-static {v0}, Lbttv/ChatTimestamps;->styleText(Ljava/lang/CharSequence;)V\n')
        # Text is assigned later in the same method, after the timestamp hook.
        # Only named EmoteCard views are touched by this new callback.
        text_set = '    invoke-virtual {p1, p2}, Lrjw;->setText(Lqjw;)V\n'
        card_set = (text_set +
            '    # BTTV 31.8: correct native EmoteCard provider/type labels\n'
            '    invoke-static {p1}, Lbttv/api/Hooks;->onReactNativeText(Landroid/view/View;)V\n')

    elif name.endswith('/PreparedLayoutTextViewManager.smali'):
        signature = ('.method public updateExtraData('
                     'Lcom/facebook/react/views/text/PreparedLayoutTextView;Ljava/lang/Object;)V\n')
        anchor = ('    iget-object v0, p2, Lcom/facebook/react/views/text/PreparedLayout;'
                  '->a:Landroid/text/Layout;\n')
        replacement = (anchor +
            '    # BTTV 31.8: prepare gray timestamp span in prepared layout\n'
            '    invoke-virtual {v0}, Landroid/text/Layout;->getText()Ljava/lang/CharSequence;\n'
            '    move-result-object v1\n'
            '    invoke-static {v1}, Lbttv/ChatTimestamps;->styleText(Ljava/lang/CharSequence;)V\n')
    else:
        raise PatchError(f'Unexpected React text manager: {name}')
    def patch(body):
        body = replace_once(body, anchor, replacement, name + ' text payload')
        if name.endswith('/ReactTextViewManager.smali'):
            body = replace_once(body, text_set, card_set, name + ' native emote-card text')
        return body
    return change_method(text, signature, patch, name + ' text payload')


def locate_react_text_updates(work: Path) -> list:
    names = (
        'com/facebook/react/views/text/ReactTextViewManager.smali',
        'com/facebook/react/views/text/PreparedLayoutTextViewManager.smali',
    )
    results = []
    for name in names:
        path = select(work, name)
        original = path.read_text(encoding='utf-8')
        if '# BTTV 31.8:' in original:
            raise PatchError(f'{name}: already patched; start from a clean APK')
        results.append((path, react_text_manager(original, name)))
    return results


def settings_version(text: str) -> str:
    # Derived from the 31.8.0 l7m Compose footer patch in the slop bundle.
    # Fetch versionName at runtime from the BTTV Android manifest rather
    # than embedding an unrelated Twitch version or a hard-coded BTTV tag.
    anchor = ('    move-result-object v4\n\n    .line 2434\n'
              '    invoke-virtual {v0}, Ls0j;->m0()Ljava/lang/Object;\n')
    snippet = ('    move-result-object v4\n\n'
               '    # BTTV 31.8: versionName from bttv.manifest.json at build time\n'
               '    invoke-static {}, Lbttv/settings/SettingsOverlay318;->versionLabel()Ljava/lang/String;\n'
               '    move-result-object v4\n\n    .line 2434\n'
               '    invoke-virtual {v0}, Ls0j;->m0()Ljava/lang/Object;\n')
    return replace_once(text, anchor, snippet, 'Compose settings version footer')


def timestamp_native(text: str) -> str:
    """Expose BTTV's preference to Twitch's 31.8.0 native chat renderer.

    This is the original 31.8 `k76` flag identified by the slop port.
    Unlike IRC display-name prefixes, it uses Twitch's own timestamp span,
    which is already used for messages loaded from history.
    """
    anchor = '    iget-boolean v6, p0, Lk76;->g:Z\n'
    if text.count(anchor) != 1:
        raise PatchError('native timestamp: missing or non-unique 31.8.0 flag')
    pos = text.index(anchor)
    # Verify the adjacent fields from the existing 31.8.0 patch to guard
    # against accidentally modifying an unrelated boolean in another build.
    before = text[max(0, pos - 260):pos]
    after = text[pos + len(anchor):pos + len(anchor) + 260]
    if 'Lk76;->f:Lnb6;' not in before or 'Lk76;->h:Ltv/twitch/android/core/mvp/viewdelegate/EventDispatcher;' not in after:
        raise PatchError('native timestamp: surrounding 31.8.0 model changed')
    return replace_once(text, anchor,
        anchor + '    # BTTV 31.8: use Twitch native timestamp span, not IRC username prefix\n'
        '    invoke-static {v6}, Lbttv/ChatTimestamps;->shouldShow(Z)Z\n'
        '    move-result v6\n', 'Twitch live chat timestamp')



def wide_span_width(text: str) -> str:
    """React Native ReplacementSpan.getSize is the real inline width measure."""
    signature = '.method public final getSize(Landroid/graphics/Paint;Ljava/lang/CharSequence;IILandroid/graphics/Paint$FontMetricsInt;)I\n'
    anchor = ('    iget p0, p0, Lp040;->a:I\n\n'
              '    .line 19\n    .line 20\n    return p0\n')
    replacement = ('    iget p0, p0, Lp040;->a:I\n\n'
                   '    # BTTV: reserve the full width of wide emotes (marker follows span)\n'
                   '    invoke-static {p2, p4, p0}, Lbttv/api/Hooks;->inlineViewWidth(Ljava/lang/CharSequence;II)I\n'
                   '    move-result p0\n    return p0\n')
    return change_method(text, signature,
        lambda body: replace_once(body, anchor, replacement, 'RN inline replacement span'),
        'RN inline replacement span')


def wide_text_layout(text: str) -> str:
    """Ensure RN inline placements use the same expanded span size as measurement."""
    signature = '.method public static m(Landroid/text/Layout;Landroid/text/Spanned;IIFLa240;)I\n'
    anchor = ('    aget-object p3, p3, v2\n\n'
              '    .line 35\n    .line 36\n'
              '    invoke-interface {p1, p3}, Landroid/text/Spanned;->getSpanStart(Ljava/lang/Object;)I\n')
    replacement = ('    aget-object p3, p3, v2\n\n'
                   '    # BTTV: derive expanded inline emote width from original span and markers\n'
                   '    invoke-interface {p1, p3}, Landroid/text/Spanned;->getSpanEnd(Ljava/lang/Object;)I\n'
                   '    move-result v7\n'
                   '    iget v6, p3, Lp040;->a:I\n'
                   '    invoke-static {p1, v7, v6}, Lbttv/api/Hooks;->inlineViewWidth(Ljava/lang/CharSequence;II)I\n'
                   '    move-result v7\n'
                   '    invoke-interface {p1, p3}, Landroid/text/Spanned;->getSpanStart(Ljava/lang/Object;)I\n')
    def patch(body):
        if '    .locals 8\n' not in body: raise PatchError('RN layout m(): register layout changed')
        body = replace_once(body, anchor, replacement, 'RN placement width preparation')
        return replace_once(body, '    iget p2, p3, Lp040;->a:I\n',
                            '    # BTTV: match original measurement expansion\n    move p2, v7\n',
                            'RN placement width')
    return change_method(text, signature, patch, 'RN inline placement')


def wide_fabric_layout(text: str) -> str:
    signature = '.method public final updateLayout(IIIIIIII)V\n    .locals 6\n'
    replacement = (signature +
        '\n    # BTTV 31.8: expand chat emote image view to match the inline slot\n'
        '    invoke-static {p0, p1, p5, p6}, Lbttv/api/Hooks;->layoutWidth(Ljava/lang/Object;III)I\n'
        '    move-result p5\n')
    return replace_once(text, signature, replacement, 'Fabric image layout')



def react_chat_row_test_id(text: str) -> str:
    """Mark RN chat row views at the verified 31.8 BaseViewManager testID hook.

    Hermes ChatMessageRowComponent assigns testID='chat-message-row'.
    Invoke the Java helper only after RN has assigned the View tag.
    """
    signature = '.method public setTestId(Landroid/view/View;Ljava/lang/String;)V\n'
    anchor = '    invoke-virtual {p1, p2}, Landroid/view/View;->setTag(Ljava/lang/Object;)V\n'
    replacement = (anchor +
        '    # BTTV 31.8: apply split chat only to RN chat-message-row views\n'
        '    invoke-static {p1, p2}, Lbttv/SplitChat318;->onTestId(Landroid/view/View;Ljava/lang/String;)V\n')
    return change_method(text, signature,
        lambda body: replace_once(body, anchor, replacement, 'RN chat row testID'),
        'RN chat row testID')

def classic_native_chat(text: str) -> str:
    """31.8.0 native RecyclerView message viewholder, confirmed by UI dump.

    chat_message_item=0x7f0b0478 belongs to sb6.A / k7d.C, where
    k7d.C renders the final Spanned in v3. Never hook global TextView.setText.
    """
    if 'Lbttv/VerticalChat318;->onClassicTextBound' in text:
        raise PatchError('native Classic chat message bind: already patched')
    signature = '.method public final C(Ljwp;Z)V\n'
    anchor = ('    invoke-virtual {v3, v5, v2}, Landroid/widget/TextView;'
              '->setText(Ljava/lang/CharSequence;Landroid/widget/TextView$BufferType;)V\n')
    new = (anchor +
           '    # BTTV 31.8: native Classic theatre RecyclerView emotes\n'
           '    invoke-static {v3}, Lbttv/VerticalChat318;->onClassicTextBound(Landroid/widget/TextView;)V\n')
    return change_method(text, signature,
        lambda body: replace_once(body, anchor, new, 'native Classic chat message bind'),
        'native Classic chat message bind')


def classic_native_theatre(text: str) -> str:
    """Native Classic theatre's visible fragment supplies the live channel."""
    if 'Lbttv/VerticalChat318;->onClassicTheatre' in text:
        raise PatchError('native Classic theatre channel: already patched')
    signature = '.method public onViewCreated(Landroid/view/View;Landroid/os/Bundle;)V\n'
    anchor = ('    invoke-super {p0, p1, p2}, Landroidx/fragment/app/m;'
              '->onViewCreated(Landroid/view/View;Landroid/os/Bundle;)V\n')
    new = (anchor +
           '    # BTTV 31.8: native Classic theatre channel on foreground entry\n'
           '    invoke-static {p0}, Lbttv/VerticalChat318;->onClassicTheatre(Ljava/lang/Object;)V\n')
    return change_method(text, signature,
        lambda body: replace_once(body, anchor, new, 'native Classic theatre channel'),
        'native Classic theatre channel')


def vertical_native_channel(text: str) -> str:
    """Initialize the native VerticalTheatreOneChatFragment's broadcaster ID."""
    signature = '.method public final onCreate(Landroid/os/Bundle;)V\n'
    pattern = re.compile(
        r'(    invoke-virtual \{v0\}, Ltv/twitch/android/shared/one/chat/'
        r'VerticalTheatreOneChatFragment\$Arguments;->getChannel\(\)'
        r'Ltv/twitch/android/models/channel/ChannelInfo;\n'
        r'(?:\s*\.line [0-9]+\n)*'
        r'    move-result-object v0\n)')
    def patch(body):
        if 'Lbttv/VerticalChat318;->onChannel' in body:
            raise PatchError('vertical OneChat channel: already patched')
        matches = list(pattern.finditer(body))
        if len(matches) != 1:
            raise PatchError(f'vertical OneChat channel: expected one channel argument, got {len(matches)}')
        position = matches[0].end()
        return body[:position] + (
            '    # BTTV 31.8: set native vertical OneChat channel context\n'
            '    invoke-static {v0}, Lbttv/VerticalChat318;->onChannel(Ljava/lang/Object;)V\n'
        ) + body[position:]
    return change_method(text, signature, patch, 'vertical OneChat channel')


def vertical_native_chat(text: str) -> str:
    """VerticalTheatreOneChatFragment binds through native q5s, not RN/Fabric.

    Only the exact 31.8.0 OneChat TextView binding is patched. Do not hook
    Android's global TextView.setText or modify unrelated settings screens.
    """
    if 'Lbttv/VerticalChat318;->onTextBound' in text:
        raise PatchError('native vertical OneChat text: already patched')
    signature = '.method public final x(Lo5s;)V\n'
    anchor = ('    invoke-virtual {v3, v7}, Landroid/widget/TextView;'
              '->setText(Ljava/lang/CharSequence;)V\n')
    replacement = (anchor +
        '    # BTTV 31.8: native vertical theatre OneChat emotes and split styling\n'
        '    invoke-static {v3}, Lbttv/VerticalChat318;->onTextBound(Landroid/widget/TextView;)V\n')
    return change_method(text, signature,
        lambda body: replace_once(body, anchor, replacement, 'native vertical OneChat text'),
        'native vertical OneChat text')


TARGETS = (
    ('tv/twitch/android/app/consumer/TwitchApplication.smali', app),
    ('tv/twitch/android/settings/main/MainSettingsFragmentV2.smali', settings_fragment_context),
    ('ilj.smali', settings_compose),
    ('l7m.smali', settings_version),
    ('k76.smali', timestamp_native),
    ('fy90.smali', websocket),
    ('com/facebook/react/modules/network/NetworkingModule.smali', network),
    ('com/facebook/react/views/image/ReactImageManager.smali', image_manager),
    ('com/facebook/react/uimanager/BaseViewManager.smali', react_chat_row_test_id),
    ('k7d.smali', classic_native_chat),
    ('tv/twitch/android/feature/theatre/TheatreModeFragment.smali', classic_native_theatre),
    ('q5s.smali', vertical_native_chat),
    ('tv/twitch/android/shared/one/chat/VerticalTheatreOneChatFragment.smali', vertical_native_channel),
    ('p040.smali', wide_span_width),
    ('d240.smali', wide_text_layout),
    ('com/facebook/react/fabric/mounting/SurfaceMountingManager.smali', wide_fabric_layout),
    ('com/twitchrn/emoteinput/TwitchEmoteInputView$EmoteSpanTarget.smali', input_target),
    ('com/twitchrn/emoteinput/EmoteImageLoader.smali', input_loader),
    ('com/twitchrn/emoteinput/EmoteImageSpan.smali', input_span),
    ('com/twitchrn/emoteinput/TwitchEmoteInputView.smali', input_view),
)


def apply(work: Path, check: bool = False) -> list:
    if not work.is_dir():
        raise PatchError(f'Not a directory: {work}')
    changes = []
    for name, transformer in TARGETS:
        path = select(work, name)
        old = path.read_text(encoding='utf-8')
        if '# BTTV 31.8:' in old:
            raise PatchError(f'{name}: already contains BTTV 31.8.0 injected hooks; start from clean base')
        updated = transformer(old)
        changes.append((path, updated))
    changes.extend(locate_react_text_updates(work))
    callback_path = work / 'smali_classes6/bttv/compat/SettingsClick318.smali'
    if callback_path.exists():
        raise PatchError('Settings click callback already exists; start from clean base')
    changes.append((callback_path, SETTINGS_CLICK_SMALI))
    # The entire matching pass must complete before writing ANY file.
    if not check:
        for path, updated in changes:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(updated, encoding='utf-8')
    return [path for path, _ in changes]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=Path('/usr/build/work'))
    parser.add_argument('--check', action='store_true', help='validate exact anchors without touching files')
    args = parser.parse_args()
    try:
        files = apply(args.work, check=args.check)
        for path in files:
            print(('CHECK' if args.check else 'PATCH') + ' ' + str(path.relative_to(args.work)))
        print(f'{len(files)} PR #740 hook targets verified for Twitch 31.8.0')
    except (PatchError, OSError, UnicodeError) as error:
        print('BTTV 31.8.0 hook relocation FAILED: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
