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
 'android/view/ViewParent.java': 'package android.view;public interface ViewParent {}',
 'android/view/ViewTreeObserver.java': '''package android.view;
 public class ViewTreeObserver {
 public interface OnGlobalLayoutListener { void onGlobalLayout(); }
 java.util.List<OnGlobalLayoutListener> listeners=new java.util.ArrayList<>();
 public void addOnGlobalLayoutListener(OnGlobalLayoutListener l){listeners.add(l);}
 public void removeOnGlobalLayoutListener(OnGlobalLayoutListener l){listeners.remove(l);}
 public boolean isAlive(){return true;}
 public void fire(){for(OnGlobalLayoutListener l:new java.util.ArrayList<>(listeners))l.onGlobalLayout();}
 }''',
 'android/view/View.java': '''package android.view;
 public class View implements ViewParent {
 private Object tag; private Object unkeyedTag;
 private final android.content.Context ctx=new android.content.Context();
 private final ViewTreeObserver observer=new ViewTreeObserver();
 private int height=20,width=20,left=0,top=0;
 private float tx,ty; private ViewParent parent;
 java.util.List<OnLayoutChangeListener> listeners=new java.util.ArrayList<>();
 java.util.List<OnAttachStateChangeListener> attached=new java.util.ArrayList<>();
 public interface OnLayoutChangeListener {void onLayoutChange(View v,int l,int t,int r,int b,int ol,int ot,int orr,int ob);}
 public interface OnAttachStateChangeListener {void onViewAttachedToWindow(View v);void onViewDetachedFromWindow(View v);}
 public void setTag(int id,Object value){tag=value;unkeyedTag=value;}
 public Object getTag(int id){return tag;}public Object getTag(){return unkeyedTag;}
 public void setTag(Object value){unkeyedTag=value;}
 public int getHeight(){return height;} public int getWidth(){return width;}
 public int getLeft(){return left;}public int getTop(){return top;}
 public void place(int l,int t,int w,int h){left=l;top=t;width=w;height=h;
 for(OnLayoutChangeListener listener:listeners)listener.onLayoutChange(this,l,t,l+w,t+h,0,0,0,0);}
 public float getTranslationX(){return tx;} public float getTranslationY(){return ty;}
 public ViewTreeObserver getViewTreeObserver(){return observer;}
 public void getLocationOnScreen(int[] xy){
 float x=left+tx,y=top+ty;ViewParent p=parent;
 for(int n=0;p instanceof View && n<32;n++){
 View v=(View)p;x+=v.left+v.tx;y+=v.top+v.ty;p=v.parent;}
 xy[0]=Math.round(x);xy[1]=Math.round(y); }
 public void setTranslationX(float x){tx=x;}public void setTranslationY(float y){ty=y;}
 public void addOnLayoutChangeListener(OnLayoutChangeListener l){listeners.add(l);}
 public void addOnAttachStateChangeListener(OnAttachStateChangeListener l){attached.add(l);}
 public void resize(int h){place(left,top,width,h);}
 public boolean post(Runnable runnable){runnable.run();return true;}
 public ViewParent getParent(){return parent;}public void setParent(ViewParent p){parent=p;}
 public android.content.Context getContext(){return ctx;}
 public android.content.res.Resources getResources(){return ctx.getResources();} }''',
 'android/view/ViewGroup.java': '''package android.view;
 public class ViewGroup extends View {
 java.util.List<View> children=new java.util.ArrayList<>();
 public void setClipChildren(boolean b){} public void setClipToPadding(boolean b){}
 public void add(View v){v.setParent(this);children.add(v);}
 public int indexOfChild(View v){return children.indexOf(v);}
 public int getChildCount(){return children.size();}
 public View getChildAt(int i){return children.get(i);}
 }''',
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
 public static final String ZERO_WIDTH_PREFIX="BTTV-zw-";
 public static int overlayBaseSteps(String id){if(!id.startsWith(ZERO_WIDTH_PREFIX))return -1;
 return Integer.parseInt(id.substring(ZERO_WIDTH_PREFIX.length(),id.indexOf('-',ZERO_WIDTH_PREFIX.length())));}
 public static String extractBTTVId(String id){return id.startsWith(ZERO_WIDTH_PREFIX)?id.substring(id.indexOf('-',ZERO_WIDTH_PREFIX.length())+1):id.substring(WIDE_PREFIX.length());} }''',
 'bttv/emote/WideTest.java': '''package bttv.emote;
 import android.view.View;import android.view.ViewGroup;
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
  check(WideEmotes.inlineViewWidth("base\u2063 rest",4,20)==1);
  View view=new View();view.setTag(1,"chat-emote-xyz");
  WideEmotes.onImageViewSource(view,new com.facebook.react.bridge.ReadableArray());
  check(WideEmotes.layoutWidth(new Manager(view),7,20,20)==40);
  view.setTag(1,"chat-emote-card-xyz");
  check(WideEmotes.layoutWidth(new Manager(view),7,20,20)==20);
  View wrapper=new View();
  WideEmotes.onWrapperTestId(wrapper,"chat-emote-wrapper-BTTV-zw-4-id");
  check(wrapper.getTranslationX()==0f); // don't guess without mounted base
  check(WideEmotes.layoutWidth(new Manager(wrapper),8,0,20)==40);
  wrapper.resize(32);
  check(wrapper.getTranslationX()==0f);
  WideEmotes.onWrapperTestId(wrapper,"chat-emote-wrapper-BTTV-other");
  check(wrapper.getTranslationX()==0f);
  check(wrapper.getTranslationY()==0f);

  // The previously failing case: a zero-width wrapper appears at the start
  // of a second line, although its base image is on the first line.
  ViewGroup row=new ViewGroup();
  View text=new View();text.setTag(1,"chat-message-line");row.add(text);
  View base=new View();base.setTag(1,"chat-emote-wrapper-555555560");
  base.place(557,25,64,64);row.add(base);
  View overlay=new View();overlay.setTag(1,"chat-emote-wrapper-BTTV-zw-0-id");
  overlay.place(99,101,64,64);row.add(overlay);
  WideEmotes.onWrapperTestId(overlay,"chat-emote-wrapper-BTTV-zw-0-id");
  check(overlay.getTranslationX()==458f);
  check(overlay.getTranslationY()==-76f);

  // Chain overlay positions must stay anchored to the original base.
  View overlay2=new View();overlay2.setTag(1,"chat-emote-wrapper-BTTV-zw-0-id");
  overlay2.place(163,101,64,64);row.add(overlay2);
  WideEmotes.onWrapperTestId(overlay2,"chat-emote-wrapper-BTTV-zw-0-id");
  check(overlay2.getTranslationX()==394f);
  check(overlay2.getTranslationY()==-76f);

  // A wide base needs horizontal centering across the expanded image.
  ViewGroup wideRow=new ViewGroup();
  View wideBase=new View();wideBase.setTag(1,"chat-emote-wrapper-BTTV-wide-base");
  wideBase.place(300,25,64,64);wideRow.add(wideBase);
  View wideOverlay=new View();wideOverlay.setTag(1,"chat-emote-wrapper-BTTV-zw-4-id");
  wideOverlay.place(364,25,64,64);wideRow.add(wideOverlay);
  WideEmotes.onWrapperTestId(wideOverlay,"chat-emote-wrapper-BTTV-zw-4-id");
  check(wideOverlay.getTranslationX()==-32f);
  check(wideOverlay.getTranslationY()==0f);

  // Fabric nested wrappers: base and overlay have *different parents*.
  // The old patch only searched immediate siblings and missed this case.
  ViewGroup nestedRow=new ViewGroup();nestedRow.setTag("chat-message-row");
  nestedRow.place(10,20,500,200);
  ViewGroup left=new ViewGroup();left.place(20,10,200,100);nestedRow.add(left);
  View deepBase=new View();deepBase.setTag("chat-emote-wrapper-25");
  deepBase.place(90,8,64,64);left.add(deepBase);
  ViewGroup right=new ViewGroup();right.place(250,90,200,100);nestedRow.add(right);
  View deepOverlay=new View();deepOverlay.setTag("chat-emote-wrapper-BTTV-zw-0-id");
  deepOverlay.place(5,8,64,64);right.add(deepOverlay);
  WideEmotes.onWrapperTestId(deepOverlay,"chat-emote-wrapper-BTTV-zw-0-id");
  check(deepOverlay.getTranslationX()==-145f);
  check(deepOverlay.getTranslationY()==-80f);
  // Repeating the update should NOT accumulate translations.
  deepOverlay.getViewTreeObserver().fire();
  check(deepOverlay.getTranslationX()==-145f);
  check(deepOverlay.getTranslationY()==-80f);

  // A preceding emote in a different row must never be chosen.
  ViewGroup root=new ViewGroup();
  ViewGroup first=new ViewGroup();first.setTag("chat-message-row");root.add(first);
  View prior=new View();prior.setTag("chat-emote-wrapper-99");first.add(prior);
  ViewGroup second=new ViewGroup();second.setTag("chat-message-row");root.add(second);
  View stranded=new View();stranded.setTag("chat-emote-wrapper-BTTV-zw-0-id");second.add(stranded);
  WideEmotes.onWrapperTestId(stranded,"chat-emote-wrapper-BTTV-zw-0-id");
  check(stranded.getTranslationX()==0f);
  check(stranded.getTranslationY()==0f);

  // Late base mount triggers the retry via the global-layout callback.
  ViewGroup lateRow=new ViewGroup();lateRow.setTag("chat-message-row");
  ViewGroup lateBaseGroup=new ViewGroup();lateRow.add(lateBaseGroup);
  View lateOverlay=new View();lateOverlay.setTag("chat-emote-wrapper-BTTV-zw-0-id");
  lateOverlay.place(64,64,64,64);lateRow.add(lateOverlay);
  WideEmotes.onWrapperTestId(lateOverlay,"chat-emote-wrapper-BTTV-zw-0-id");
  check(lateOverlay.getTranslationX()==0f);
  View lateBase=new View();lateBase.setTag("chat-emote-wrapper-100");
  lateBase.place(0,0,64,64);lateBaseGroup.add(lateBase);
  lateOverlay.getViewTreeObserver().fire();
  check(lateOverlay.getTranslationX()==-64f);
  check(lateOverlay.getTranslationY()==-64f);

  WideEmotes.onWrapperTestId(overlay,"chat-emote-wrapper-BTTV-normal");
  check(overlay.getTranslationX()==0f);
  check(overlay.getTranslationY()==0f);
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
