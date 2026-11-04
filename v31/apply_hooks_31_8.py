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
    snippet = ('    # BTTV 31.8: rewrite emote image sources copy-on-write\n'
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


TARGETS = (
    ('tv/twitch/android/app/consumer/TwitchApplication.smali', app),
    ('fy90.smali', websocket),
    ('com/facebook/react/modules/network/NetworkingModule.smali', network),
    ('com/facebook/react/views/image/ReactImageManager.smali', image_manager),
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
    # The entire matching pass must complete before writing ANY file.
    if not check:
        for path, updated in changes:
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
