"""Native Dual Format Classic chat regression tests using user's real 31.8.0 smali."""
import importlib.util
from pathlib import Path
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'v31/apply_hooks_31_8.py'
spec = importlib.util.spec_from_file_location('patch318', SCRIPT)
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)

class ClassicNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.apk = Path('/mnt/data/twitch-31.8.0-smali.zip')
        if not cls.apk.exists():
            raise unittest.SkipTest('Real Twitch 31.8.0 smali not available')

    def test_message_binding_is_exact_native_classic_view(self):
        with zipfile.ZipFile(self.apk) as z:
            holder = z.read('smali_classes2/k7d.smali').decode()
            base = z.read('smali_classes2/sb6.smali').decode()
        self.assertIn('0x7f0b0478', base)
        self.assertIn('->F:Landroid/widget/TextView;', holder)
        self.assertIn('->setText(Ljava/lang/CharSequence;Landroid/widget/TextView$BufferType;)V', holder)
        after = patcher.classic_native_chat(holder)
        self.assertEqual(after.count('->onClassicTextBound'), 1)
        self.assertIn('invoke-static {v3}', after)
        with self.assertRaises(patcher.PatchError):
            patcher.classic_native_chat(after)

    def test_classic_theatre_channel_hook(self):
        with zipfile.ZipFile(self.apk) as z:
            original = z.read('smali/tv/twitch/android/feature/theatre/TheatreModeFragment.smali').decode()
        after = patcher.classic_native_theatre(original)
        self.assertEqual(after.count('->onClassicTheatre'), 1)
        self.assertIn('invoke-static {p0}', after)
        with self.assertRaises(patcher.PatchError):
            patcher.classic_native_theatre(after)

    def test_classic_does_not_change_rn_or_vertical_split_chat(self):
        java = (ROOT/'mod/app/src/main/java/bttv/VerticalChat318.java').read_text()
        self.assertIn('public static void onClassicTextBound(TextView view)',java)
        self.assertIn('applyEmotes(view);',java)
        self.assertIn('public static void onClassicTheatre(Object fragment)',java)
        self.assertIn('public static void onClassicPlayable(Object playable)',java)
        self.assertIn('getChannelId',java)
        self.assertIn('Set<TextView> interestedViews',java)
        self.assertIn('onTextBound(TextView view)',java)
        self.assertNotIn('SplitChat318;->',
            patcher.classic_native_chat(
                zipfile.ZipFile(self.apk).read('smali_classes2/k7d.smali').decode()))

if __name__ == '__main__': unittest.main()
