"""31.8.0 vertical-native and async emote-picker regression checks."""
from pathlib import Path
import importlib.util
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PATCHER = ROOT / 'v31' / 'apply_hooks_31_8.py'
SRC = ROOT / 'mod/app/src/main/java/bttv'

spec = importlib.util.spec_from_file_location('patcher_318', PATCHER)
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)


class VerticalAndPickerTests(unittest.TestCase):
    def test_native_vertical_hook_from_supplied_318_smali(self):
        # This is the actual 31.8.0 OneChat view delegate, not a fabricated fixture.
        sample = Path('/mnt/data/twitch-31.8.0-smali.zip')
        if sample.exists():
            with zipfile.ZipFile(sample) as archive:
                original = archive.read('smali_classes6/q5s.smali').decode('utf-8')
        else:
            self.skipTest('Original decoded Twitch 31.8.0 sample not provided')
        updated = patcher.vertical_native_chat(original)
        self.assertEqual(updated.count('Lbttv/VerticalChat318;->onTextBound'), 1)
        self.assertEqual(updated.count('.method public final x(Lo5s;)V'), 1)
        with self.assertRaises(patcher.PatchError):
            patcher.vertical_native_chat(updated)

    def test_vertical_fragment_channel_hook_from_real_smali(self):
        sample = Path('/mnt/data/twitch-31.8.0-smali.zip')
        if not sample.exists():
            self.skipTest('Original decoded Twitch 31.8.0 sample not provided')
        with zipfile.ZipFile(sample) as archive:
            original = archive.read('smali_classes6/tv/twitch/android/shared/one/chat/VerticalTheatreOneChatFragment.smali').decode('utf-8')
        updated = patcher.vertical_native_channel(original)
        self.assertEqual(updated.count('VerticalChat318;->onChannel(Ljava/lang/Object;)V'), 1)
        self.assertIn('invoke-static {v0}', updated)
        with self.assertRaises(patcher.PatchError):
            patcher.vertical_native_channel(updated)

    def test_no_global_chat_text_or_hermes_hooks_modified(self):
        src = (SRC / 'VerticalChat318.java').read_text(encoding='utf-8')
        self.assertIn('onTextBound(TextView view)', src)
        self.assertIn('getSpans(start, end, ReplacementSpan.class)', src)
        self.assertIn('InputEmotes.bitmapForEmote(emote)', src)
        self.assertIn('emotes.put(emote.url, emote)', (SRC / 'emote/InputEmotes.java').read_text(encoding='utf-8'))
        self.assertIn('SplitChat318.SEPARATOR_PREF', src)
        self.assertIn("('q5s.smali', vertical_native_chat)", PATCHER.read_text(encoding='utf-8'))

    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'JDK not available')
    def test_picker_prefers_latest_foreground_context(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / 'PickerTest.java'
            source.write_text('''import bttv.emote.PickerChannelContext318;
public class PickerTest {
  static void eq(int expect, int actual) { if(expect!=actual) throw new AssertionError(expect+" != "+actual); }
  public static void main(String[] args) {
    eq(29468517, PickerChannelContext318.select(23220337, false, 23220337, 29468517));
    eq(22484632, PickerChannelContext318.select(29468517, false, 29468517, 22484632));
    eq(111, PickerChannelContext318.select(111, true, 99, 99));
    eq(99, PickerChannelContext318.select(111, false, 99, 99));
    eq(111, PickerChannelContext318.select(111, true, -1, -1));
    eq(-1, PickerChannelContext318.select(-1, false, -1, -1));
    if(!PickerChannelContext318.stale(1, 2)) throw new AssertionError();
    if(PickerChannelContext318.stale(1, 1)) throw new AssertionError();
  }
}''', encoding='utf-8')
            subprocess.run(['javac','-d',d,str(SRC/'emote/PickerChannelContext318.java'),str(source)],check=True)
            subprocess.run(['java','-cp',d,'PickerTest'],check=True)

    def test_network_404_is_scoped_and_retryable(self):
        src=(SRC/'Network.java').read_text(encoding='utf-8')
        self.assertNotIn('NOT_FOUND_RETRY_AFTER',src)
        self.assertIn('"No 7TV channel catalog for " + channel',src)
        self.assertIn('FINISHED_REQUESTS.add(key)',src)


if __name__ == '__main__': unittest.main()
