"""JVM regression checks for 7TV zero-width emotes in RN chat on Twitch 31.8.0.

No APK build, emulator, or third-party dependencies required. The tests compile
real source files with lightweight Android and 7TV-JSON stubs.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
JAVA = ROOT / 'mod/app/src/main/java/bttv'

COMMON = {
 'android/content/Context.java': 'package android.content;public class Context {}',
 'android/util/Log.java': '''package android.util;public class Log {
 public static int i(String a,String b){return 0;} public static int d(String a,String b){return 0;}
 public static int w(String a,String b){return 0;} public static int e(String a,String b,Throwable t){return 0;}}
 ''',
 'tv/twitch/android/shared/emotes/utils/AnimatedEmotesUrlUtil.java': '''
 package tv.twitch.android.shared.emotes.utils;public class AnimatedEmotesUrlUtil {
 public enum EmoteUrlAnimationSetting {STATIC,ANIMATED} }''',
}

JSON_STUBS = {
 'org/json/JSONException.java': 'package org.json;public class JSONException extends Exception {public JSONException(String s){super(s);}}',
 'org/json/JSONObject.java': '''package org.json;import java.util.*;
 public class JSONObject {
  private final Map<String,Object> v=new HashMap<>();
  public JSONObject(){} public JSONObject(String ignored){}
  public JSONObject put(String k,Object x){v.put(k,x);return this;}
  public String getString(String k)throws JSONException{return String.valueOf(req(k));}
  public int getInt(String k)throws JSONException{return ((Number)req(k)).intValue();}
  public int optInt(String k){Object o=v.get(k);return o instanceof Number?((Number)o).intValue():0;}
  public boolean optBoolean(String k){return Boolean.TRUE.equals(v.get(k));}
  public boolean has(String k){return v.containsKey(k);} public boolean isNull(String k){return v.get(k)==null;}
  public JSONObject getJSONObject(String k)throws JSONException{return (JSONObject)req(k);}
  public JSONArray getJSONArray(String k)throws JSONException{return (JSONArray)req(k);}
  private Object req(String k)throws JSONException {if(!v.containsKey(k))throw new JSONException(k);return v.get(k);}
 }''',
 'org/json/JSONArray.java': '''package org.json;import java.util.*;
 public class JSONArray {private final List<Object> v=new ArrayList<>();
 public JSONArray(){}public JSONArray(String ignored){}
 public JSONArray put(Object o){v.add(o);return this;} public int length(){return v.size();}
 public JSONObject getJSONObject(int i){return (JSONObject)v.get(i);}
 }''',
 'tv/twitch/android/models/emotes/EmoteModelAssetType.java': '''
 package tv.twitch.android.models.emotes;public enum EmoteModelAssetType {STATIC,ANIMATED}''',
 'bttv/emote/Emotes.java': '''package bttv.emote;
 public class Emotes {public enum Source{BTTV,FFZ,STV};
 public static Emote last;public static Emote getEmoteById(String id){return last!=null && last.id.equals(id)?last:null;}}
 ''',
 'bttv/emote/ParseZeroWidthTest.java': '''package bttv.emote;
 import org.json.*;
 public class ParseZeroWidthTest {
 static void yes(boolean c){if(!c)throw new AssertionError();}
 static JSONObject entry(int activeFlags,int defaultFlags)throws Exception {
  JSONObject file=new JSONObject().put("format","WEBP").put("name","2x.webp")
                 .put("width",64).put("height",64);
  JSONObject host=new JSONObject().put("url","//cdn.7tv.app/emote/some-id")
                .put("files",new JSONArray().put(file));
  JSONObject data=new JSONObject().put("host",host).put("flags",defaultFlags).put("animated",false);
  return new JSONObject().put("id","some-id").put("name","RainTime")
                         .put("flags",activeFlags).put("data",data);
 }
 public static void main(String[] args)throws Exception {
  Emote byActive=Emote.fromJson(entry(1,0),Emotes.Source.STV);yes(byActive.zeroWidth);
  Emote byDefault=Emote.fromJson(entry(0,256),Emotes.Source.STV);yes(byDefault.zeroWidth);
  yes(Emote.fromJson(entry(1,256),Emotes.Source.STV).zeroWidth);
  yes(!Emote.fromJson(entry(0,0),Emotes.Source.STV).zeroWidth);
  yes(!Emote.fromJson(entry(0,1),Emotes.Source.STV).zeroWidth); // private flag, not zero-width
  // A real legacy zero-width 7TV asset may lack active/default flags in
  // channel snapshots; never apply the fallback based on its display alias.
  yes(Emote.fromJson(entry(0,0).put("id","01FE5VRARG000FV5W0DYEQ6JKP"),
       Emotes.Source.STV).zeroWidth); // SnowTime
  yes(!Emote.fromJson(entry(0,0).put("name","SnowTime"),
       Emotes.Source.STV).zeroWidth); // an unrelated emote with the same name
  Emotes.last=byActive;
  String id=EmoteUrlUtil.overlayId("some-id",4);
  yes(id.equals("BTTV-zw-4-some-id"));
  yes(EmoteUrlUtil.overlayBaseSteps(id)==4);
  yes(EmoteUrlUtil.overlayBaseSteps("BTTV-zw-20-some-id")==-1);
  yes(EmoteUrlUtil.extractBTTVId(id).equals("some-id"));
  yes(EmoteUrlUtil.extractBTTVId("BTTV-wide-some-id").equals("some-id"));
  yes(EmoteUrlUtil.getEmoteUrl(id).equals(byActive.url));
  System.out.println("PASS: 7TV active/default flags and per-occurrence overlay URL");
 }
 }''',
}

IRC_STUBS = {
 'bttv/Data.java': '''package bttv;public class Data {
 public static android.content.Context ctx=new android.content.Context();
 public static int currentBroadcasterId=7;
 public static void setCurrentBroadcasterId(int c){currentBroadcasterId=c;}}
 ''',
 'bttv/emote/Emote.java': '''package bttv.emote;public class Emote {
 public String id,code;public boolean zeroWidth;public float aspectRatio=1f;
 public Emotes.Source source=Emotes.Source.STV;
 public String url="https://cdn.7tv.app/emote/some-id/2x.webp";
 public Emote(String id,boolean zw,float ratio){this.id=id;this.code=id;this.zeroWidth=zw;this.aspectRatio=ratio;}}
 ''',
 'bttv/emote/WideEmotes.java': '''package bttv.emote;public class WideEmotes {
 public static final String OVERLAY_MARKER="\\u2063";
 public static int steps(float ratio){return ratio<1.2f?0:Math.round((Math.min(ratio,4f)-1)*4);}
 public static String marker(Emote e){return "\\u2060".repeat(steps(e.aspectRatio));}}
 ''',
 'bttv/emote/Emotes.java': '''package bttv.emote;public class Emotes {
 public enum Source{BTTV,FFZ,STV}
 public static Emote getZeroWidth7TVEmote(String code,int channel) {
  if("SnowTime".equals(code))return new Emote("01FE5VRARG000FV5W0DYEQ6JKP",true,1f);
  if("RainTime".equals(code))return new Emote("rain",true,1f);
  if("SteerR".equals(code))return new Emote("steer",true,1f);
  return null;
 }
 public static Emote getEmote(android.content.Context c,String code,int channel){
 switch(code){case "peepo":return new Emote("base",false,1f);
 case "peepoEstonia":return new Emote("eston",false,1f);
 case "SnowTime":return new Emote("shadowed",false,1f);
 case "WIDE":return new Emote("wide",false,2f);
 case "RainTime":return new Emote("rain",true,1f);
 case "SteerR":return new Emote("steer",true,1f);
 default:return null;}}
 public static Emote getEmoteById(String id){return null;}
 public static void ensureChannelEmotes(android.content.Context c,int channel){} }
 ''',
 'bttv/ZeroWidthIrcTest.java': '''package bttv;
 public class ZeroWidthIrcTest {
 static void yes(boolean x){if(!x)throw new AssertionError();}
 static String frame(String body,String emotes){return "@room-id=7;emotes="+emotes+" :u!u@u PRIVMSG #stream :"+body;}
 static String rewrite(String body,String tags){return IrcEmotes.rewriteFrame(frame(body,tags));}
 static void match(String body,String tags,String text,String tagPart){
  String s=rewrite(body,tags);
  yes(s.endsWith(" :"+text));yes(s.contains("emotes="+tagPart+" "));}
 public static void main(String[] args){
  // Real reproduction: peepoEstonia + the verified SnowTime 7TV overlay.
  // Even when another provider wins ordinary emote-name lookup,
  // the overlay must use the 7TV asset and have a zero-width span.
  match("peepoEstonia SnowTime","","peepoEstoniaSnowTime\\u2063",
        "BTTV-eston:0-11/BTTV-zw-0-01FE5VRARG000FV5W0DYEQ6JKP:12-19");
  match("peepo RainTime hi","","peepoRainTime\\u2063 hi","BTTV-base:0-4/BTTV-zw-0-rain:5-12");
  match("peepo RainTime SteerR","","peepoRainTime\\u2063SteerR\\u2063",
        "BTTV-base:0-4/BTTV-zw-0-rain:5-12/BTTV-zw-0-steer:14-19");
  match("WIDE RainTime","","WIDE\\u2060\\u2060\\u2060\\u2060RainTime\\u2063",
        "BTTV-wide-wide:0-3/BTTV-zw-4-rain:8-15");
  match("Kappa RainTime PogChamp","25:0-4/88:15-22",
        "KappaRainTime\\u2063 PogChamp","25:0-4/88:15-22/BTTV-zw-0-rain:5-12");
  match("RainTime","","RainTime","BTTV-rain:0-7");
  match("hello RainTime","","hello RainTime","BTTV-rain:6-13");
  match("peepo  RainTime","","peepo  RainTime","BTTV-base:0-4/BTTV-rain:7-14");
  System.out.println("PASS: 7TV overlay positions, Twitch base, wide base, chains and plain-text fallback");
 }
 }''',
}

class ZeroWidthTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'),'JDK unavailable')
    def test_7tv_flags_and_url_identifier(self):
        self.compile_and_run({**COMMON,**JSON_STUBS},[JAVA/'emote/Emote.java',JAVA/'emote/EmoteUrlUtil.java'],
                             'bttv.emote.ParseZeroWidthTest')

    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'),'JDK unavailable')
    def test_irc_overlay_positions(self):
        self.compile_and_run({**COMMON,**IRC_STUBS},[JAVA/'emote/EmoteUrlUtil.java',JAVA/'IrcEmotes.java'],
                             'bttv.ZeroWidthIrcTest')

    def test_existing_31_8_hooks_are_used(self):
        split=(JAVA/'SplitChat318.java').read_text()
        wide=(JAVA/'emote/WideEmotes.java').read_text()
        irc=(JAVA/'IrcEmotes.java').read_text()
        self.assertIn('WideEmotes.onWrapperTestId(view, testId)',split)
        self.assertIn('OVERLAY_CHAR',wide)
        self.assertIn('overlayWrappers.get(view)',wide)
        self.assertIn('EmoteUrlUtil.overlayId(',irc)
        self.assertIn('shiftPositions(emotes, insertions)',irc)

    def compile_and_run(self,stubs, sources, main):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);files=[]
            for name,content in stubs.items():
                f=p/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(content);files.append(str(f))
            subprocess.run(['javac','-d',t,*files,*map(str,sources)],check=True,capture_output=True,text=True)
            subprocess.run(['java','-cp',t,main],check=True,capture_output=True,text=True)

if __name__=='__main__':unittest.main()
