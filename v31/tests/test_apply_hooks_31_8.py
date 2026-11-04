"""Test that 31.8.0 anchors patch atomically, and incorrect targets fail closed.

Synthetic fragments are based on the supplied slop patch contexts. They are
NOT a substitute for a build against the real Twitch 31.8.0 base APK.
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'apply_hooks_31_8.py'
spec = importlib.util.spec_from_file_location('bttv_port_318', SCRIPT)
port = importlib.util.module_from_spec(spec)
spec.loader.exec_module(port)

FIXTURES = {
    'smali/tv/twitch/android/app/consumer/TwitchApplication.smali': (
        '.class public Ltv/twitch/android/app/consumer/TwitchApplication;\n'
        '.method public onCreate()V\n    .locals 28\n'
        '    invoke-virtual {v1}, Ltv/twitch/android/app/consumer/TwitchApplication;->b()V\n'
        '    return-void\n.end method\n'),
    'smali_classes3/fy90.smali': (
        '.class public Lfy90;\n'
        '.method public final n(Lnpw;Ljava/lang/String;)V\n    .locals 3\n'
        '    .line 1\n    invoke-virtual {p1}, Ljava/lang/Object;->getClass()Ljava/lang/Class;\n'
        '.end method\n'),
    'smali_classes3/com/facebook/react/modules/network/NetworkingModule.smali': (
        '.method public sendRequest(Ljava/lang/String;Ljava/lang/String;D'
        'Lcom/facebook/react/bridge/ReadableArray;Lcom/facebook/react/bridge/ReadableMap;'
        'Ljava/lang/String;ZDZ)V\n    .locals 1\n'
        '    invoke-static {p1, p2, p7}, Lkgp;->z(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V\n'
        '.end method\n'),
    'smali_classes3/com/facebook/react/views/image/ReactImageManager.smali': (
        '.method public setSource(Landroid/view/View;Lcom/facebook/react/bridge/ReadableArray;)V\n'
        '    .annotation runtime Lcom/facebook/react/uimanager/annotations/ReactProp;\n'
        '        name = "source"\n    .end annotation\n\n'
        '    .line 1\n    invoke-virtual {p1}, Ljava/lang/Object;->getClass()Ljava/lang/Class;\n'
        '.end method\n'),
    'smali_classes4/com/twitchrn/emoteinput/TwitchEmoteInputView$EmoteSpanTarget.smali': (
        '.method public constructor <init>(IIILjava/lang/String;Ljava/lang/Integer;)V\n'
        '    .locals 0\n    invoke-virtual {p4}, Ljava/lang/Object;->getClass()Ljava/lang/Class;\n'
        '.end method\n'),
    'smali_classes4/com/twitchrn/emoteinput/EmoteImageLoader.smali': (
        '.method private final fetch(Ljava/lang/String;)Landroid/graphics/Bitmap;\n'
        '    .locals 2\n    new-instance p0, Ljava/net/URL;\n.end method\n'),
    'smali_classes4/com/twitchrn/emoteinput/EmoteImageSpan.smali': (
        '.method public draw(Landroid/graphics/Canvas;)V\n    .locals 1\n'
        '    invoke-virtual {p1, p5, p2, p3, p0}, Landroid/graphics/Canvas;'
        '->drawBitmap(Landroid/graphics/Bitmap;Landroid/graphics/Rect;'
        'Landroid/graphics/RectF;Landroid/graphics/Paint;)V\n.end method\n'),
    'smali_classes4/com/twitchrn/emoteinput/TwitchEmoteInputView.smali': (
        '.method protected onAttachedToWindow()V\n    .locals 1\n'
        '    invoke-super {p0}, Landroid/view/View;->onAttachedToWindow()V\n'
        '    return-void\n.end method\n'),
}


class HookTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        for path, code in FIXTURES.items():
            full = self.root / path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(code)

    def tearDown(self):
        self.dir.cleanup()

    def test_check_mode_does_not_write(self):
        self.assertEqual(len(port.apply(self.root, check=True)), 8)
        for path, code in FIXTURES.items():
            self.assertEqual((self.root / path).read_text(), code)

    def test_all_eight_targets_are_injected(self):
        self.assertEqual(len(port.apply(self.root)), 8)
        for path in FIXTURES:
            patched = (self.root / path).read_text()
            self.assertIn('Lbttv/api/Hooks;->', patched)
        self.assertIn('onWebSocketText', (self.root / 'smali_classes3/fy90.smali').read_text())
        self.assertIn('interceptHttpRequest', (self.root / 'smali_classes3/com/facebook/react/modules/network/NetworkingModule.smali').read_text())

    def test_no_partial_changes_on_bad_anchor(self):
        path = self.root / 'smali_classes3/fy90.smali'
        path.write_text(path.read_text().replace('Lnpw;', 'Lwrong;'))
        with self.assertRaises(port.PatchError):
            port.apply(self.root)
        for filename, code in FIXTURES.items():
            if filename != 'smali_classes3/fy90.smali':
                self.assertEqual((self.root / filename).read_text(), code)

    def test_reapplication_fails_instead_of_duplicating(self):
        port.apply(self.root)
        with self.assertRaises(port.PatchError):
            port.apply(self.root)


if __name__ == '__main__':
    unittest.main()
