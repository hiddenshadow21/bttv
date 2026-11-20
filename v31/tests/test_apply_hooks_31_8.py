"""Tests for the Twitch 31.8.0 source-verified settings and RN text hooks.

Synthetic fixtures validate atomic changes and preconditions. The smali
signatures were inspected in the user's actual Twitch 31.8.0 decode.
"""
import importlib.util
import re
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'apply_hooks_31_8.py'
spec = importlib.util.spec_from_file_location('bttv318', SCRIPT)
port = importlib.util.module_from_spec(spec)
spec.loader.exec_module(port)

FIXTURES = {
    'smali/tv/twitch/android/app/consumer/TwitchApplication.smali': (
        '.method public onCreate()V\n    .locals 28\n'
        '    invoke-virtual {v1}, Ltv/twitch/android/app/consumer/TwitchApplication;->b()V\n'
        '    return-void\n.end method\n'),
    'smali_classes2/tv/twitch/android/settings/main/MainSettingsFragmentV2.smali': (
        '.method public final onCreateView(Landroid/view/LayoutInflater;Landroid/view/ViewGroup;Landroid/os/Bundle;)Landroid/view/View;\n'
        '    .locals 1\n'
        '    invoke-virtual {p0}, Landroidx/fragment/app/m;->requireContext()Landroid/content/Context;\n'
        '    move-result-object p3\n'
        '    new-instance p1, Landroidx/compose/ui/platform/ComposeView;\n'
        '    return-object p1\n.end method\n'),
    'smali_classes4/ilj.smali': (
        '.method public static final h(Lcpi;ZZZZZZLjava/lang/String;)V\n'
        '    .locals 39\n'
        '    invoke-static {v7, v8, v0, v2}, Lilj;->d(ZLcpi;Lb0a;I)V\n\n'
        '    shr-int/lit8 v2, v37, 0x15\n'
        '    return-void\n.end method\n'),
    'smali_classes6/l7m.smali': (
        '.method public final invoke()Ljava/lang/Object;\n    .locals 5\n'
        '    move-result-object v4\n\n    .line 2434\n'
        '    invoke-virtual {v0}, Ls0j;->m0()Ljava/lang/Object;\n'
        '.end method\n'),
    'smali_classes2/k76.smali': (
        '.method public final a()V\n    .locals 10\n'
        '    iget-object v5, p0, Lk76;->f:Lnb6;\n'
        '    .line 26\n    .line 27\n'
        '    iget-boolean v6, p0, Lk76;->g:Z\n'
        '    .line 28\n    .line 29\n'
        '    iget-object v7, p0, Lk76;->h:Ltv/twitch/android/core/mvp/viewdelegate/EventDispatcher;\n'
        '    return-void\n.end method\n'),
    'smali_classes2/ic9.smali': (
        '.method public final D2(Lvb9;)Ltb9;\n    .locals 13\n'
        '    :cond_1\n    iget-boolean p0, p0, Lic9;->p:Z\n'
        '    :cond_3\n    new-instance v0, Lrb9;\n'
        '    return-object v0\n.end method\n'),
    'smali_classes3/p040.smali': (
        '.method public final getSize(Landroid/graphics/Paint;Ljava/lang/CharSequence;IILandroid/graphics/Paint$FontMetricsInt;)I\n'
        '    .locals 0\n'
        '    iget p0, p0, Lp040;->a:I\n\n'
        '    .line 19\n    .line 20\n    return p0\n.end method\n'),
    'smali_classes3/d240.smali': (
        '.method public static m(Landroid/text/Layout;Landroid/text/Spanned;IIFLa240;)I\n'
        '    .locals 8\n'
        '    aget-object p3, p3, v2\n\n'
        '    .line 35\n    .line 36\n'
        '    invoke-interface {p1, p3}, Landroid/text/Spanned;->getSpanStart(Ljava/lang/Object;)I\n'
        '    move-result p1\n'
        '    iget p2, p3, Lp040;->a:I\n'
        '    return p2\n.end method\n'),
    'smali_classes3/com/facebook/react/fabric/mounting/SurfaceMountingManager.smali': (
        '.method public final updateLayout(IIIIIIII)V\n    .locals 6\n'
        '    return-void\n.end method\n'),
    'smali_classes3/fy90.smali': (
        '.method public final n(Lnpw;Ljava/lang/String;)V\n    .locals 3\n'
        '    return-void\n.end method\n'),
    'smali_classes3/com/facebook/react/modules/network/NetworkingModule.smali': (
        '.method public sendRequest(Ljava/lang/String;Ljava/lang/String;D'
        'Lcom/facebook/react/bridge/ReadableArray;Lcom/facebook/react/bridge/ReadableMap;'
        'Ljava/lang/String;ZDZ)V\n    .locals 1\n'
        '    return-void\n.end method\n'),
    'smali_classes3/com/facebook/react/uimanager/BaseViewManager.smali': (
        '.method public setTestId(Landroid/view/View;Ljava/lang/String;)V\n'
        '    .locals 0\n'
        '    const p0, 0x7f0b10ab\n'
        '    invoke-virtual {p1, p0, p2}, Landroid/view/View;->setTag(ILjava/lang/Object;)V\n'
        '    invoke-virtual {p1, p2}, Landroid/view/View;->setTag(Ljava/lang/Object;)V\n'
        '    return-void\n.end method\n'),
    'smali_classes3/com/facebook/react/views/image/ReactImageManager.smali': (
        '.method public setSource(Landroid/view/View;Lcom/facebook/react/bridge/ReadableArray;)V\n'
        '    .annotation runtime Lcom/facebook/react/uimanager/annotations/ReactProp;\n'
        '        name = "source"\n    .end annotation\n\n'
        '    return-void\n.end method\n'),
    'smali_classes4/com/twitchrn/emoteinput/TwitchEmoteInputView$EmoteSpanTarget.smali': (
        '.method public constructor <init>(IIILjava/lang/String;Ljava/lang/Integer;)V\n'
        '    .locals 0\n    return-void\n.end method\n'),
    'smali_classes4/com/twitchrn/emoteinput/EmoteImageLoader.smali': (
        '.method private final fetch(Ljava/lang/String;)Landroid/graphics/Bitmap;\n'
        '    .locals 2\n    return-object v0\n.end method\n'),
    'smali_classes4/com/twitchrn/emoteinput/EmoteImageSpan.smali': (
        '.method public draw(Landroid/graphics/Canvas;)V\n    .locals 1\n'
        '    invoke-virtual {p1, p5, p2, p3, p0}, Landroid/graphics/Canvas;'
        '->drawBitmap(Landroid/graphics/Bitmap;Landroid/graphics/Rect;'
        'Landroid/graphics/RectF;Landroid/graphics/Paint;)V\n.end method\n'),
    'smali_classes4/com/twitchrn/emoteinput/TwitchEmoteInputView.smali': (
        '.method protected onAttachedToWindow()V\n    .locals 1\n'
        '    return-void\n.end method\n'),
    'smali_classes2/k7d.smali': (
        '.method public final C(Ljwp;Z)V\n    .locals 16\n'
        '    invoke-virtual {v3, v5, v2}, Landroid/widget/TextView;'
        '->setText(Ljava/lang/CharSequence;Landroid/widget/TextView$BufferType;)V\n'
        '    return-void\n.end method\n'),
    'smali_classes5/tv/twitch/android/feature/discovery/feed/rn/theatre/TwitchRNTheatreFragment.smali': (
        '.field public miniPlayer:Ltv/twitch/android/feature/discovery/feed/rn/theatre/MiniPlayerController;\n'
        '.field private final rnSurfaceController:Ltv/twitch/android/feature/discovery/feed/rn/runtime/RNSurfaceController;\n'
        '.method public onViewCreated(Landroid/view/View;Landroid/os/Bundle;)V\n'
        '    .locals 5\n'
        '    invoke-super {p0, p1, p2}, Landroidx/fragment/app/m;'
        '->onViewCreated(Landroid/view/View;Landroid/os/Bundle;)V\n'
        '    return-void\n.end method\n'
        '.method public onDestroyView()V\n'
        '    .locals 2\n'
        '    return-void\n.end method\n'),
    'smali/tv/twitch/android/feature/theatre/TheatreModeFragment.smali': (
        '.method public onViewCreated(Landroid/view/View;Landroid/os/Bundle;)V\n'
        '    .locals 7\n'
        '    invoke-super {p0, p1, p2}, Landroidx/fragment/app/m;'
        '->onViewCreated(Landroid/view/View;Landroid/os/Bundle;)V\n'
        '    return-void\n.end method\n'),
    'smali_classes6/q5s.smali': (
        '.method public final x(Lo5s;)V\n    .locals 11\n'
        '    invoke-virtual {v3, v7}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V\n'
        '    return-void\n.end method\n'),
    'smali_classes6/tv/twitch/android/shared/one/chat/VerticalTheatreOneChatFragment.smali': (
        '.method public final onCreate(Landroid/os/Bundle;)V\n    .locals 4\n'
        '    invoke-virtual {v0}, Ltv/twitch/android/shared/one/chat/'
        'VerticalTheatreOneChatFragment$Arguments;->getChannel()'
        'Ltv/twitch/android/models/channel/ChannelInfo;\n'
        '    move-result-object v0\n'
        '    return-void\n.end method\n'),
    'smali_classes3/com/facebook/react/views/text/ReactTextViewManager.smali': (
        '.method public bridge synthetic updateExtraData(Landroid/view/View;Ljava/lang/Object;)V\n'
        '    .locals 0\n    return-void\n.end method\n'
        '.method public updateExtraData(Lrjw;Ljava/lang/Object;)V\n'
        '    .locals 3\n'
        '    check-cast p2, Lqjw;\n'
        '    iget-object v0, p2, Lqjw;->a:Landroid/text/Spannable;\n'
        '    invoke-virtual {p1, p2}, Lrjw;->setText(Lqjw;)V\n'
        '    return-void\n.end method\n'),
    'smali_classes3/com/facebook/react/views/text/PreparedLayoutTextViewManager.smali': (
        '.method public updateExtraData('
        'Lcom/facebook/react/views/text/PreparedLayoutTextView;Ljava/lang/Object;)V\n'
        '    .locals 3\n'
        '    check-cast p2, Lcom/facebook/react/views/text/PreparedLayout;\n'
        '    iget-object v0, p2, Lcom/facebook/react/views/text/PreparedLayout;->a:Landroid/text/Layout;\n'
        '    invoke-virtual {p1, p2}, Lcom/facebook/react/views/text/PreparedLayoutTextView;->setPreparedLayout(Lcom/facebook/react/views/text/PreparedLayout;)V\n'
        '    return-void\n.end method\n'),
}


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for rel, source in FIXTURES.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source)

    def tearDown(self):
        self.temp.cleanup()

    def test_check_only_is_atomic(self):
        self.assertEqual(len(port.apply(self.root, check=True)), 24)
        for rel, contents in FIXTURES.items():
            self.assertEqual(contents, (self.root / rel).read_text())
        self.assertFalse((self.root / 'smali_classes6/bttv/compat/SettingsClick318.smali').exists())

    def test_all_24_targets(self):
        self.assertEqual(len(port.apply(self.root)), 24)
        self.assertIn('Lilj;->m(Ljava/lang/String;',
                      (self.root / 'smali_classes4/ilj.smali').read_text())
        self.assertIn('Lrq0;->b:Licf;', (self.root / 'smali_classes4/ilj.smali').read_text())
        self.assertIn('Lcpi;',
                      (self.root / 'smali_classes6/bttv/compat/SettingsClick318.smali').read_text())
        self.assertIn('SettingsOverlay318;->open(Landroid/content/Context;)V',
                      (self.root / 'smali_classes6/bttv/compat/SettingsClick318.smali').read_text())
        self.assertIn('ChatTimestamps;->styleText',
                      (self.root / 'smali_classes3/com/facebook/react/views/text/ReactTextViewManager.smali').read_text())
        self.assertIn('Lqjw;->a:Landroid/text/Spannable;',
                      (self.root / 'smali_classes3/com/facebook/react/views/text/ReactTextViewManager.smali').read_text())
        self.assertIn('Landroid/text/Layout;->getText()',
                      (self.root / 'smali_classes3/com/facebook/react/views/text/PreparedLayoutTextViewManager.smali').read_text())
        self.assertIn('rememberContext(Landroid/content/Context;)V',
                      (self.root / 'smali_classes2/tv/twitch/android/settings/main/MainSettingsFragmentV2.smali').read_text())
        self.assertIn('Compose BTTV settings click invoked',
                      (self.root / 'smali_classes6/bttv/compat/SettingsClick318.smali').read_text())
        self.assertIn('versionLabel', (self.root / 'smali_classes6/l7m.smali').read_text())
        self.assertIn('shouldShow', (self.root / 'smali_classes2/k76.smali').read_text())
        # The 31.8 React Native popup does not use the old native ic9 presenter.
        self.assertEqual(FIXTURES['smali_classes2/ic9.smali'],
                         (self.root / 'smali_classes2/ic9.smali').read_text())
        self.assertIn('inlineViewWidth', (self.root / 'smali_classes3/p040.smali').read_text())
        self.assertIn('inlineViewWidth', (self.root / 'smali_classes3/d240.smali').read_text())
        self.assertIn('layoutWidth', (self.root / 'smali_classes3/com/facebook/react/fabric/mounting/SurfaceMountingManager.smali').read_text())
        self.assertIn('onImageViewSource', (self.root / 'smali_classes3/com/facebook/react/views/image/ReactImageManager.smali').read_text())
        self.assertIn('VerticalChat318;->onClassicTextBound',
                      (self.root / 'smali_classes2/k7d.smali').read_text())
        self.assertIn('VerticalChat318;->onClassicTheatre',
                      (self.root / 'smali/tv/twitch/android/feature/theatre/TheatreModeFragment.smali').read_text())
        self.assertIn('VerticalChat318;->onTextBound', (self.root / 'smali_classes6/q5s.smali').read_text())
        self.assertIn('VerticalChat318;->onChannel', (self.root / 'smali_classes6/tv/twitch/android/shared/one/chat/VerticalTheatreOneChatFragment.smali').read_text())


    def test_keyboard_listener_uses_real_smali_method_name_and_observable_logs(self):
        # The actual 31.8.0 MiniPlayerController.smali declares
        # .method public final isMinimized()Z; JADX misleadingly renders
        # this Kotlin getter as getMinimized() in Java output.
        helper = (SCRIPT.parents[1] / 'mod/app/src/main/java/bttv/'
                  'ChatKeyboardRemeasure318.java').read_text(encoding='utf-8')
        self.assertIn('getMethod("isMinimized")', helper)
        self.assertNotIn('getMethod("getMinimized")', helper)
        self.assertIn('install invoked; root=', helper)
        self.assertIn('theatre layout changed: height=', helper)
        self.assertIn('requesting RN remeasure', helper)
        self.assertNotIn('!nowIme.booleanValue() && !previousIme.booleanValue()', helper)

    def test_keyboard_hook_is_on_theatre_only_and_preserves_registers(self):
        port.apply(self.root)
        path = self.root / (
            'smali_classes5/tv/twitch/android/feature/discovery/feed/rn/theatre/'
            'TwitchRNTheatreFragment.smali')
        smali = path.read_text()
        self.assertEqual(smali.count('ChatKeyboardRemeasure318;->install'), 1)
        self.assertEqual(smali.count('ChatKeyboardRemeasure318;->uninstall'), 1)
        self.assertIn('    iget-object v0, p0,', smali)
        self.assertIn('    iget-object v1, p0,', smali)
        self.assertIn('    invoke-static {p1, v0, v1}', smali)
        self.assertIn('.method public onViewCreated(Landroid/view/View;Landroid/os/Bundle;)V\n'
                      '    .locals 5\n', smali)
        self.assertIn('.method public onDestroyView()V\n    .locals 2\n', smali)

    def test_missing_rn_theatre_ime_hook_fails_atomically(self):
        path = self.root / (
            'smali_classes5/tv/twitch/android/feature/discovery/feed/rn/theatre/'
            'TwitchRNTheatreFragment.smali')
        source = path.read_text()
        path.write_text(source.replace('    .locals 5\n', '    .locals 7\n'))
        with self.assertRaises(port.PatchError):
            port.apply(self.root)
        self.assertEqual(FIXTURES['smali_classes3/fy90.smali'],
                         (self.root / 'smali_classes3/fy90.smali').read_text())

    def test_split_chat_hook_is_on_real_RN_test_id_only(self):
        port.apply(self.root)
        p = self.root / 'smali_classes3/com/facebook/react/uimanager/BaseViewManager.smali'
        smali = p.read_text()
        self.assertEqual(smali.count('SplitChat318;->onTestId'), 1)
        self.assertIn('invoke-static {p1, p2}', smali)
        self.assertIn('invoke-virtual {p1, p2}, Landroid/view/View;->setTag', smali)

    def test_missing_split_chat_test_id_anchor_is_atomic(self):
        p = self.root / 'smali_classes3/com/facebook/react/uimanager/BaseViewManager.smali'
        p.write_text(p.read_text().replace('setTag(Ljava/lang/Object;)', 'missingTag(Ljava/lang/Object;)'))
        with self.assertRaises(port.PatchError):
            port.apply(self.root)
        self.assertEqual(FIXTURES['smali_classes3/fy90.smali'],
                         (self.root / 'smali_classes3/fy90.smali').read_text())

    def test_missing_replacement_span_fails_atomically(self):
        p = self.root / 'smali_classes3/p040.smali'
        p.write_text(p.read_text().replace('getSize(', 'notGetSize('))
        with self.assertRaises(port.PatchError): port.apply(self.root)
        self.assertEqual(FIXTURES['smali_classes3/fy90.smali'],
                         (self.root / 'smali_classes3/fy90.smali').read_text())

    def test_missing_real_settings_host_context_fails_atomically(self):
        path = self.root / 'smali_classes2/tv/twitch/android/settings/main/MainSettingsFragmentV2.smali'
        path.write_text(path.read_text().replace('requireContext()', 'getContext()'))
        with self.assertRaises(port.PatchError):
            port.apply(self.root)
        self.assertEqual(FIXTURES['smali_classes4/ilj.smali'],
                         (self.root / 'smali_classes4/ilj.smali').read_text())

    def test_missing_settings_anchor_fails_before_write(self):
        p = self.root / 'smali_classes4/ilj.smali'
        p.write_text(p.read_text().replace('Lilj;->d(', 'Lilj;->NOPE('))
        with self.assertRaises(port.PatchError): port.apply(self.root)
        self.assertEqual(FIXTURES['smali_classes3/fy90.smali'],
                         (self.root / 'smali_classes3/fy90.smali').read_text())

    def test_missing_real_RN_text_field_fails_atomically(self):
        p = self.root / 'smali_classes3/com/facebook/react/views/text/ReactTextViewManager.smali'
        p.write_text(p.read_text().replace('Lqjw;->a:', 'Lqjw;->wrong:'))
        with self.assertRaises(port.PatchError): port.apply(self.root)
        self.assertEqual(FIXTURES['smali_classes4/ilj.smali'],
                         (self.root / 'smali_classes4/ilj.smali').read_text())

    def test_prepared_layout_signature_required(self):
        p = self.root / 'smali_classes3/com/facebook/react/views/text/PreparedLayoutTextViewManager.smali'
        p.write_text(p.read_text().replace('PreparedLayoutTextView;', 'WrongView;'))
        with self.assertRaises(port.PatchError): port.apply(self.root)

    def test_compose_settings_row_uses_encodable_registers(self):
        # The 35c invoke forms and const/4 are 4-bit register encodings.
        # The real 31.8.0 ilj.h uses v0..v38, so v16+ must not appear
        # in those instructions even though the method has .locals 39.
        port.apply(self.root)
        smali = (self.root / 'smali_classes4/ilj.smali').read_text()
        injected = smali.split('    # BTTV 31.8: native scrolling Compose row', 1)[1]
        injected = injected.split('    shr-int/lit8 v2, v37, 0x15', 1)[0]
        for line in injected.splitlines():
            line = line.strip()
            if line.startswith('invoke-') and '/range' not in line:
                regs = re.search(r'\{([^}]*)\}', line)
                self.assertIsNotNone(regs, line)
                for register in re.findall(r'v(\d+)', regs.group(1)):
                    self.assertLess(int(register), 16, line)
            if line.startswith('const/4 '):
                match = re.search(r'const/4 v(\d+),', line)
                self.assertIsNotNone(match, line)
                self.assertLess(int(match.group(1)), 16, line)
        self.assertIn('invoke-virtual {v0, v2}', injected)
        self.assertIn('invoke-direct {v15, v2}', injected)
        self.assertIn('const/16 v17, 0x0', injected)
        self.assertIn('const/16 v19, 0x0', injected)
        self.assertIn('invoke-static/range {v13 .. v20}', injected)

    def test_no_legacy_settings_targets(self):
        self.assertFalse(any(n in (x[0] for x in port.TARGETS) for n in
                             ('xpo.smali','xoz.smali','qnc.smali')))

    def test_correct_timestamp_preference_wiring(self):
        java = SCRIPT.parents[1] / 'mod/app/src/main/java'
        hooks = (java / 'bttv/api/Hooks.java').read_text()
        overlay = (java / 'bttv/settings/SettingsOverlay318.java').read_text()
        timestamp = (java / 'bttv/ChatTimestamps.java').read_text()
        self.assertIn('ChatTimestamps.rewriteFrame(IrcEmotes.rewriteFrame(text))', hooks)
        self.assertIn('Settings.AlwaysShowChatTimestamps', timestamp)
        self.assertIn('Settings.AlwaysShowChatTimestamps', overlay)
        self.assertIn('styleText(CharSequence unused)', timestamp)
        self.assertNotIn('reactTextGetText', timestamp)
        self.assertIn('public static void open(Context context)', overlay)
        self.assertIn('public static void rememberContext(Context context)', overlay)
        self.assertIn('new Entry.BoolValue(true)',
                      (java / 'bttv/settings/Settings.java').read_text().split('AlwaysShowChatTimestamps(', 1)[1])

    def test_reapplication_rejected(self):
        port.apply(self.root)
        with self.assertRaises(port.PatchError): port.apply(self.root)

    def test_duplicate_callback_rejected(self):
        p = self.root / 'smali_classes6/bttv/compat/SettingsClick318.smali'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('duplicate')
        with self.assertRaisesRegex(port.PatchError,'already exists'): port.apply(self.root)

    def test_react_native_manager_concrete_not_bridge(self):
        port.apply(self.root)
        p = self.root / 'smali_classes3/com/facebook/react/views/text/ReactTextViewManager.smali'
        s = p.read_text()
        self.assertEqual(s.count('ChatTimestamps;->styleText'),1)
        bridge=s.split('.method public bridge synthetic')[1].split('.end method')[0]
        self.assertNotIn('ChatTimestamps',bridge)


if __name__=='__main__': unittest.main()
