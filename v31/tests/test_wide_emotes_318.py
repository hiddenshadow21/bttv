"""Host-side checks of PR #740's wide emote implementation on the new hooks."""
import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[2] / 'mod/app/src/main/java/bttv/emote/WideEmotes.java'

FILES = {
 'android/util/Log.java': 'package android.util; public class Log { public static int d(String a,String b){return 0;} }',
 'android/content/Context.java': '''package android.content;
 public class Context { public android.content.res.Resources getResources(){return new android.content.res.Resources();}
 public String getPackageName(){return "test";} }''',
 'android/content/res/Resources.java': '''package android.content.res;
 public class Resources { public int getIdentifier(String a,String b,String c){return 1;} }''',
 'android/view/View.java': '''package android.view;
 public class View { private Object tag; private final android.content.Context ctx=new android.content.Context();
 public void setTag(int id,Object value){tag=value;} public Object getTag(int id){return tag;}
 public android.content.Context getContext(){return ctx;}
 public android.content.res.Resources getResources(){return ctx.getResources();} }''',
 'com/facebook/react/bridge/ReadableArray.java': '''package com.facebook.react.bridge;
 public class ReadableArray { public int size(){return 1;} public ReadableMap getMap(int index){return new ReadableMap();} }''',
 'com/facebook/react/bridge/ReadableMap.java': '''package com.facebook.react.bridge;
 public class ReadableMap { public boolean hasKey(String key){return true;}
 public String getString(String key){return "https://static-cdn.jtvnw.net/emoticons/v2/BTTV-wide-id/default/dark/1.0";} }''',
 'bttv/emote/Emote.java': 'package bttv.emote; public class Emote { public float aspectRatio=2f; }',
 'bttv/emote/Emotes.java': '''package bttv.emote;
 public class Emotes { public static Emote getEmoteById(String id){return "id".equals(id)?new Emote():null;} }''',
 'bttv/emote/EmoteUrlUtil.java': '''package bttv.emote;
 public class EmoteUrlUtil { public static final String WIDE_PREFIX="BTTV-wide-";
 public static String extractBTTVId(String id){return id.substring(WIDE_PREFIX.length());} }''',
 'bttv/emote/WideTest.java': '''package bttv.emote;
 import android.view.View;
 public class WideTest {
 public static class Manager { private View view;
 public Manager(View v){view=v;} public boolean getViewExists(int id){return true;}
 public View getView(int id){return view;} }
 static void check(boolean c){if(!c)throw new AssertionError();}
 public static void main(String[] args)throws Exception {
  Emote emote=new Emote(); String marker=WideEmotes.marker(emote);
  check(marker.length()==4);
  String s="x"+marker+" afterwards";
  check(WideEmotes.inlineViewWidth(s,1,20)==40);
  check(WideEmotes.inlineViewWidth("xyz",1,20)==20);
  View view=new View();view.setTag(1,"chat-emote-xyz");
  WideEmotes.onImageViewSource(view,new com.facebook.react.bridge.ReadableArray());
  check(WideEmotes.layoutWidth(new Manager(view),7,20,20)==40);
  view.setTag(1,"chat-emote-card-xyz");
  check(WideEmotes.layoutWidth(new Manager(view),7,20,20)==20);
  System.out.println("PASS: wide emote markers, span widths, and image layout");
 }
 }''',
}

class WideEmotes(unittest.TestCase):
 @unittest.skipUnless(shutil.which('javac') and shutil.which('java'),'JDK not installed')
 def test_marker_span_and_image_width(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for name,source in FILES.items():
    path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(source)
   classes=root/'classes';classes.mkdir()
   subprocess.run(['javac','-d',str(classes)]+[str(x) for x in root.rglob('*.java')]+[str(SRC)],check=True)
   subprocess.run(['java','-cp',str(classes),'bttv.emote.WideTest'],check=True)

if __name__=='__main__':unittest.main()
