"""Source-level RN emote regression checks; run with python3 -m unittest discover -s v31/tests.

The catalog test compiles the real Emotes.java with minimal Android/JVM stubs,
so it exercises provider collisions rather than checking source strings alone.
"""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
JAVA = ROOT / 'mod/app/src/main/java/bttv'

STUBS = {
    'android/content/Context.java': 'package android.content; public class Context {}',
    'android/util/Log.java': '''package android.util; public class Log {
        public static int i(String a,String b){return 0;}
        public static int w(String a,String b){return 0;}
        public static int e(String a,String b,Throwable t){return 0;}
    }''',
    'bttv/Network.java': '''package bttv; public class Network {
        public static void getBTTVGlobalEmotes(){}
        public static void getFFZGlobalEmotes(){}
        public static void get7TVGlobalEmotes(){}
        public static void getBTTVChannelEmotes(int c){}
        public static void getFFZChannelEmotes(int c){}
        public static void get7TVChannelEmotes(int c){}
    }''',
    'bttv/emote/EmoteSettings.java': '''package bttv.emote; public class EmoteSettings {
        public static boolean bttv=true,ffz=true,stv=true,gif=true;
        public static boolean bttvEnabled(){return bttv;}
        public static boolean ffzEnabled(){return ffz;}
        public static boolean stvEnabled(){return stv;}
        public static boolean gifEnabled(){return gif;}
    }''',
    'bttv/emote/Emote.java': '''package bttv.emote; public class Emote {
        public final String id,code,imageType;
        public boolean zeroWidth;
        public final Emotes.Source source;
        public Emote(String i,Emotes.Source s,String c,String t){id=i;source=s;code=c;imageType=t;}
        public boolean isAnimated(){return "gif".equals(imageType);}
    }''',
    'bttv/emote/ChannelEmoteData.java': '''package bttv.emote; import java.util.List;
        public class ChannelEmoteData {
            public final List<Emote> channelEmotes,sharedEmotes;
            public ChannelEmoteData(List<Emote> c,List<Emote> s){channelEmotes=c;sharedEmotes=s;}
        }''',
    'bttv/emote/EmoteCatalogTest.java': '''package bttv.emote;
        import java.util.*;
        public class EmoteCatalogTest {
            static void yes(boolean ok) { if (!ok) throw new AssertionError(); }
            public static void main(String[] args) {
                Emote ffz=new Emote("ffz",Emotes.Source.FFZ,"Same","png");
                Emote bttv=new Emote("bttv",Emotes.Source.BTTV,"Same","png");
                Emote stv=new Emote("stv",Emotes.Source.STV,"Same","png");
                Emotes.addChannelFFZ(11,Arrays.asList(ffz));
                Emotes.addChannelBTTV(11,new ChannelEmoteData(Arrays.asList(bttv),Collections.<Emote>emptyList()));
                Emotes.addChannel7TV(11,Arrays.asList(stv));
                yes(Emotes.getChannelEmote(Emotes.Source.FFZ,11,"Same")==ffz);
                yes(Emotes.getChannelEmote(Emotes.Source.BTTV,11,"Same")==bttv);
                yes(Emotes.getChannelEmote(Emotes.Source.STV,11,"Same")==stv);
                yes(Emotes.getEmote(null,"Same",11)==ffz);
                stv.zeroWidth=true;
                // Ordinary chat keeps FFZ priority; an adjacent overlay
                // must resolve to the metadata-correct 7TV emote.
                yes(Emotes.getZeroWidth7TVEmote("Same",11)==stv);
                stv.zeroWidth=false;
                yes(Emotes.getZeroWidth7TVEmote("Same",11)==null);
                stv.zeroWidth=true;
                EmoteSettings.ffz=false;
                yes(Emotes.getEmote(null,"Same",11)==bttv);
                EmoteSettings.bttv=false;
                yes(Emotes.getEmote(null,"Same",11)==stv);
                EmoteSettings.stv=false;
                yes(Emotes.getEmote(null,"Same",11)==null);
                yes(Emotes.getZeroWidth7TVEmote("Same",11)==null);
                yes(Emotes.getAllEmotes(11).isEmpty());
                EmoteSettings.ffz=true;
                yes(Emotes.getAllEmotes(11).size()==1);
                yes(Emotes.getEmote(null,"Same",22)==null);
                Emotes.addChannelFFZ(22,Arrays.asList(new Emote("gif",Emotes.Source.FFZ,"GIF","gif")));
                EmoteSettings.gif=false;
                yes(Emotes.getEmote(null,"GIF",22)==null);
            }
        }''',
}


class ReactNativeEmoteTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'JDK unavailable')
    def test_channel_catalog_provider_isolation(self):
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            paths = []
            for name, src in STUBS.items():
                dest = base / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(src, encoding='utf-8')
                paths.append(str(dest))
            subprocess.run(['javac', '-d', temp, *paths, str(JAVA / 'emote/Emotes.java')],
                           check=True, capture_output=True, text=True)
            subprocess.run(['java', '-cp', temp, 'bttv.emote.EmoteCatalogTest'],
                           check=True, capture_output=True, text=True)

    def test_real_query_context_and_empty_twitch_emote_set(self):
        menu = (JAVA / 'emote/RNEmoteMenu.java').read_text(encoding='utf-8')
        hooks = (JAVA / 'api/Hooks.java').read_text(encoding='utf-8')
        self.assertIn('observeChannelQuery(String body)', menu)
        self.assertIn('RNEmoteMenu.observeChannelQuery(body)', hooks)
        self.assertIn('Emotes.getChannelEmote(source, channel, code)', menu)
        self.assertIn('if (emoteTemplate == null)', menu)
        self.assertIn('if (setTemplate == null)', menu)

    def test_7tv_gif_detection_and_input_modes(self):
        emote = (JAVA / 'emote/Emote.java').read_text(encoding='utf-8')
        settings = (JAVA / 'emote/EmoteSettings.java').read_text(encoding='utf-8')
        input_emotes = (JAVA / 'emote/InputEmotes.java').read_text(encoding='utf-8')
        self.assertIn('return animated;', emote)
        self.assertIn('emote.animated = jsonObject.getJSONObject("data").optBoolean("animated")', emote)
        for mode in ('FOREVER', 'ONCE', 'STATIC', 'DISABLED'):
            self.assertIn(mode, settings)
        self.assertIn('setRepeatCount(', input_emotes)
        self.assertIn('playedOnce.add(animation)', input_emotes)


if __name__ == '__main__':
    unittest.main()
