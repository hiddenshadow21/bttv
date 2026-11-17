"""Regression test: minimized-stream IRC messages must not steal foreground channel."""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
IRC_SOURCE = ROOT / "mod/app/src/main/java/bttv/IrcEmotes.java"

STUBS = {
    "android/content/Context.java": "package android.content; public class Context {}",
    "android/util/Log.java": """package android.util; public class Log {
        public static int i(String a,String b) {return 0;}
        public static int d(String a,String b) {return 0;}
        public static int e(String a,String b,Throwable c) {return 0;}
    }""",
    "bttv/Data.java": """package bttv;
        import android.content.Context;
        public class Data {
            public static int currentBroadcasterId = -1;
            public static Context ctx = new Context();
            public static void setCurrentBroadcasterId(int id) {currentBroadcasterId=id;}
        }""",
    "bttv/emote/Emote.java": "package bttv.emote; public class Emote {public String id,code;public boolean zeroWidth;public float aspectRatio=1f;public Emotes.Source source;}",
    "bttv/emote/EmoteUrlUtil.java": "package bttv.emote; public class EmoteUrlUtil {public static final String WIDE_PREFIX=\"wide-\";public static String overlayId(String id,int steps){return \"BTTV-zw-\"+steps+\"-\"+id;}}",
    "bttv/emote/WideEmotes.java": "package bttv.emote; public class WideEmotes {public static final String OVERLAY_MARKER=\"\\u2063\";public static int steps(float r){return 0;}public static String marker(Emote e){return \"\";}}",
    "bttv/emote/Emotes.java": """package bttv.emote;
        import android.content.Context;
        public class Emotes {
            public enum Source { BTTV, FFZ, STV }
            public static Emote getZeroWidth7TVEmote(String code,int channel){return null;}
            public static int lastPreloaded = -1;
            public static int preloads = 0;
            public static void ensureChannelEmotes(Context c,int id) {lastPreloaded=id;preloads++;}
            public static Emote getEmote(Context c,String code,int id){return null;}
        }""",
    "bttv/MinimizedChatTest.java": """package bttv;
        import bttv.emote.Emotes;
        public class MinimizedChatTest {
            private static void yes(boolean b) {if(!b)throw new AssertionError();}
            public static void main(String[] args) {
                Data.setCurrentBroadcasterId(101);
                IrcEmotes.onRoomState("@room-id=202 ROOMSTATE #new\\r\\n");
                yes(Data.currentBroadcasterId==202);
                int count=Emotes.preloads;
                String old="@room-id=101;emotes= :u!u@u PRIVMSG #old :hello\\r\\n";
                IrcEmotes.rewriteFrame(old);
                yes(Data.currentBroadcasterId==202);
                yes(Emotes.preloads==count+1 && Emotes.lastPreloaded==101);
                IrcEmotes.rewriteFrame(old);
                yes(Emotes.preloads==count+1);
                String next="@room-id=303;emotes= :u!u@u PRIVMSG #next :hi\\r\\n";
                IrcEmotes.rewriteFrame(next);
                yes(Data.currentBroadcasterId==202);
                yes(Emotes.lastPreloaded==303);
            }
        }""",
}

class MinimizedChatChannelTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "JDK unavailable")
    def test_background_privmsg_does_not_replace_active_broadcaster(self):
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            files = []
            for name, contents in STUBS.items():
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents, encoding="utf-8")
                files.append(str(path))
            subprocess.run(["javac", "-d", temp, *files, str(IRC_SOURCE)],
                           check=True, capture_output=True, text=True)
            subprocess.run(["java", "-cp", temp, "bttv.MinimizedChatTest"],
                           check=True, capture_output=True, text=True)

if __name__ == "__main__":
    unittest.main()
