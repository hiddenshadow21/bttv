"""JVM behavior tests for the 31.8.0 moderation and auto-claim gates.

Compiles the two Android-agnostic feature classes against tiny fake Android
and BTTV settings classes. No APK or Twitch credentials required.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'mod/app/src/main/java/bttv'

STUBS = {
    'android/content/Context.java': 'package android.content; public class Context {}',
    'android/util/Log.java': '''package android.util;
        public class Log {
            public static int w(String tag, String text, Throwable e){ return 0; }
            public static int i(String tag, String text){ return 0; }
            public static int d(String tag, String text){ return 0; }
        }''',
    'android/view/View.java': '''package android.view;
        public class View { public interface OnClickListener { void onClick(View view); } }''',
    'bttv/Data.java': '''package bttv;
        public class Data { public static android.content.Context ctx = new android.content.Context(); }''',
    'bttv/ResUtil.java': '''package bttv;
        public class ResUtil { public static boolean enabled = true;
        public static boolean getBooleanFromSettings(bttv.settings.Settings s) { return enabled; } }''',
    'bttv/settings/UserPreferences.java': '''package bttv.settings;
        public class UserPreferences {
            public static class Entry {
                public static class BoolEntry {
                    public BoolValue get(android.content.Context c) {
                        return new BoolValue(Boolean.TRUE);
                    }
                }
                public static class BoolValue {
                    Boolean value;
                    public BoolValue(Boolean value) {this.value=value;}
                    public Boolean get() {return value;}
                }
            }
        }''',
    'bttv/settings/Settings.java': '''package bttv.settings;
        public enum Settings {
            ShowDeletedMessagesEnabled,AutoRedeemChannelPointsEnabled;
            public final Object entry = new UserPreferences.Entry.BoolEntry();
        }''',
    'bttv/LiveFeatureTest.java': '''package bttv;
        public final class LiveFeatureTest {
            private static void check(boolean ok) { if(!ok) throw new AssertionError(); }
            public static void main(String[] args) {
                check(ChannelPoints.once("bonus-1",true));
                check(!ChannelPoints.once("bonus-1",true));
                check(ChannelPoints.once("bonus-2",true));
                check(!ChannelPoints.once("bonus-3",false));
                check(!ChannelPoints.once(null,true));
                check(!ChannelPoints.once("",true));
                String msg = "@id=abc :a PRIVMSG #room :hello";
                String del = "@target-msg-id=abc :tmi.twitch.tv CLEARMSG #room :hello";
                String ban = ":tmi.twitch.tv CLEARCHAT #room :viewer";
                String globalClear = ":tmi.twitch.tv CLEARCHAT #room";
                check(ChatModeration318.filterFrame(del,false).equals(del));
                check(ChatModeration318.filterFrame(del,true).equals(""));
                check(ChatModeration318.filterFrame(ban,true).equals(ban));
                check(ChatModeration318.filterFrame(globalClear,true).equals(""));
                check(ChatModeration318.filterFrame(msg+"\\r\\n"+del+"\\r\\n",true).equals(msg+"\\r\\n"));
                check(ChatModeration318.filterFrame(del+"\\r\\n"+msg,true).equals(msg));
                check(ChatModeration318.filterFrame(msg,true).equals(msg));
                String fake = ":viewer PRIVMSG #room :I read about CLEARMSG #other";
                check(ChatModeration318.filterFrame(fake,true).equals(fake));
                System.out.println("PASS: auto-claim and deleted-message gates");
            }
        }'''
}

class LiveFeatures(unittest.TestCase):
    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'JDK not installed')
    def test_java_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name, source in STUBS.items():
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
            classes = base / 'classes'
            classes.mkdir()
            files = list(base.rglob('*.java')) + [SRC / 'ChannelPoints.java', SRC / 'ChatModeration318.java']
            subprocess.run(['javac','-d',str(classes)]+list(map(str,files)),check=True)
            subprocess.run(['java','-cp',str(classes),'bttv.LiveFeatureTest'],check=True)

    def test_wiring(self):
        hooks = (SRC/'api/Hooks.java').read_text()
        overlay = (SRC/'settings/SettingsOverlay318.java').read_text()
        self.assertIn('ChatModeration318.filterFrame(text)',hooks)
        self.assertIn('Settings.ShowDeletedMessagesEnabled',overlay)
        self.assertIn('Settings.AutoRedeemChannelPointsEnabled',overlay)

if __name__=='__main__': unittest.main()
