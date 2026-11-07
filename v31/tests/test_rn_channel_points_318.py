"""JVM checks for React Native claim-available parsing and fail-closed preference.

The event payloads are constructed as JSON objects so that tests do not depend
on a network connection or on any Twitch account credentials.
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
 public class Log { public static int d(String a,String b){return 0;}
 public static int i(String a,String b){return 0;}
 public static int w(String a,String b){return 0;}
 public static int w(String a,String b,Throwable t){return 0;} }''',
 'bttv/Data.java': '''package bttv; public class Data {
 public static android.content.Context ctx=new android.content.Context();
 public static int currentBroadcasterId=0; }''',
 'bttv/ResUtil.java': '''package bttv; public class ResUtil {
 public static boolean enabled=true;
 public static boolean getBooleanFromSettings(bttv.settings.Settings s){return enabled;} }''',
 'bttv/settings/Settings.java': '''package bttv.settings;
 public enum Settings { AutoRedeemChannelPointsEnabled }''',
 'bttv/RNNetwork.java': '''package bttv;
 import java.util.*;
 public class RNNetwork {
 public static java.util.List<String[]> readHeaders(Object o){return Collections.emptyList();}
 }''',
 'org/json/JSONArray.java': '''package org.json; public class JSONArray {
 public int length(){return 0;} public Object opt(int i){return null;} }''',
 'org/json/JSONObject.java': '''package org.json; import java.util.*;
 public class JSONObject {
 private final Map<String,Object> values=new HashMap<>();
 public JSONObject(){} public JSONObject(String ignored){}
 public JSONObject put(String k, Object v){values.put(k,v);return this;}
 public Object opt(String k){return values.get(k);}
 public String optString(String k,String fallback){Object v=values.get(k);return v==null?fallback:v.toString();}
 public JSONObject optJSONObject(String k){Object v=values.get(k);return v instanceof JSONObject?(JSONObject)v:null;}
 public JSONArray optJSONArray(String k){Object v=values.get(k);return v instanceof JSONArray?(JSONArray)v:null;}
 public boolean isNull(String k){return values.get(k)==null;}
 }''',
 'bttv/RNPoints318Test.java': '''package bttv;
 import org.json.JSONObject;
 import java.lang.reflect.*;
 import java.util.*;
 public class RNPoints318Test {
 static void check(boolean b){if(!b)throw new AssertionError();}
 static void parse(JSONObject o)throws Exception {
  Method m=RNChannelPoints318.class.getDeclaredMethod("parseNode", Object.class,String.class,int.class);
  m.setAccessible(true);m.invoke(null,o,null,0);
 }
 static int pending()throws Exception {
  Field f=RNChannelPoints318.class.getDeclaredField("pending");f.setAccessible(true);
  return ((Map<?,?>)f.get(null)).size();
 }
 public static void main(String[] args)throws Exception {
  Method v=RNChannelPoints318.class.getDeclaredMethod("validId",String.class);v.setAccessible(true);
  check((Boolean)v.invoke(null,"a1_b-5")); check(!(Boolean)v.invoke(null,"a b"));
  Method t=RNChannelPoints318.class.getDeclaredMethod("channelFromTopic",String.class);t.setAccessible(true);
  check("12345".equals(t.invoke(null,"community-points-channel-v1.12345")));
  check(t.invoke(null,"community-points-user-v1.12345")==null);
  check(t.invoke(null,"other-topic.12345")==null);
  parse(new JSONObject().put("type","claim-available").put("channelID","123").put("claimID","bonus-A"));
  check(pending()==1);
  parse(new JSONObject().put("type","claim-available").put("channelID","123").put("claimID","bonus-A"));
  check(pending()==1);
  parse(new JSONObject().put("type","claim-available").put("channelID","123")
    .put("data",new JSONObject().put("availableClaim",new JSONObject().put("id","bonus-B"))));
  check(pending()==2);
  // Twitch Hermes's actual notification wrapper: notification.pubsub.message.
  // The topic ends in the USER ID, while the claim carries the CHANNEL ID.
  parse(new JSONObject().put("type","notification").put("notification",
    new JSONObject().put("type","pubsub").put("pubsub",
      new JSONObject().put("topic","community-points-user-v1.888")
        .put("message", new JSONObject().put("type","claim-available")
          .put("data", new JSONObject().put("claim", new JSONObject()
            .put("id","bonus-C").put("point_gain", new JSONObject().put("channel_id","456"))))))));
  check(pending()==3);
  // The user ID is NOT a valid substitute for channel ID.
  parse(new JSONObject().put("topic","community-points-user-v1.888")
      .put("message",new JSONObject().put("type","claim-available")
          .put("claimID","bonus-no-channel")));
  check(pending()==3);
  parse(new JSONObject().put("type","chat").put("channelID","123").put("claimID","bonus-C"));
  check(pending()==3);
  ResUtil.enabled=false;
  parse(new JSONObject().put("type","claim-available").put("channelID","123").put("claimID","bonus-D"));
  check(pending()==3);
  System.out.println("PASS: RN claim-available handling and BTTV toggle");
 }
 }'''
}

class ReactNativePointsTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'JDK not available')
    def test_java_parser_and_preference(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for name, text in STUBS.items():
                target = base / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            out = base / 'classes'
            out.mkdir()
            files = [str(x) for x in base.rglob('*.java')]
            subprocess.run(['javac','-d',str(out)] + files + [str(SRC/'RNChannelPoints318.java')],
                           check=True, capture_output=True, text=True)
            subprocess.run(['java','-cp',str(out),'bttv.RNPoints318Test'],check=True)

    def test_hooks_are_connected(self):
        hooks = (SRC / 'api/Hooks.java').read_text()
        self.assertIn('RNChannelPoints318.onReactNativeSocketFrame(text)', hooks)
        self.assertIn('RNChannelPoints318.onReactNativeRequest(method, url, headers)', hooks)
        self.assertIn('return bttv.ChatTimestamps.rewriteFrame', hooks)
        script = (ROOT / 'v31/apply_hooks_31_8.py').read_text()
        self.assertIn("('fy90.smali', websocket)", script)
        self.assertNotIn("('ic9.smali', auto_claim_points)", script)
        self.assertNotIn("def auto_claim_points", script)

if __name__ == '__main__':
    unittest.main()
