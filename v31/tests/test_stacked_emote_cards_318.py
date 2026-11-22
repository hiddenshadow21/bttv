"""JVM regression checks for 7TV stack hit detection and combined emote cards."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_wide_emotes_318 import FILES as BASE_FILES

JAVA = Path(__file__).resolve().parents[2] / 'mod/app/src/main/java/bttv'
FILES = dict(BASE_FILES)
FILES.pop('bttv/emote/WideTest.java')
FILES['android/view/ViewParent.java'] = '''package android.view; public interface ViewParent {ViewParent getParent();}'''
FILES['android/view/View.java'] = FILES['android/view/View.java'].replace(
    ' public interface OnLayoutChangeListener',
    ''' public interface OnTouchListener {boolean onTouch(View v, android.view.MotionEvent e);}
 private OnTouchListener onTouch;
 public void setOnTouchListener(OnTouchListener l){onTouch=l;}
 public boolean dispatch(android.view.MotionEvent e){return onTouch!=null && onTouch.onTouch(this,e);}
 public void setBackgroundColor(int color){}
 public void setPadding(int left,int top,int right,int bottom){}
 public interface OnLayoutChangeListener''')
FILES['android/view/ViewGroup.java'] = FILES['android/view/ViewGroup.java'].replace(
    ' public void add(View v)',
    ' public void addView(View v){add(v);} public void addView(View v, Object p){add(v);} public void add(View v)')
FILES['android/view/View.java'] = FILES['android/view/View.java'].replace('new android.content.Context()', 'new android.app.Activity()')
FILES['android/view/MotionEvent.java'] = '''package android.view;
 public class MotionEvent {
 public static final int ACTION_DOWN=0,ACTION_UP=1,ACTION_MOVE=2,ACTION_CANCEL=3;
 private final int action;public MotionEvent(int a){action=a;}
 public int getActionMasked(){return action;}public float getX(){return 2;}public float getY(){return 2;}}
'''
FILES['android/content/ContextWrapper.java'] = '''package android.content;
 public class ContextWrapper extends Context {public Context getBaseContext(){return this;}}'''
FILES['android/app/Activity.java'] = '''package android.app;
 public class Activity extends android.content.Context {
 public boolean isFinishing(){return false;}public boolean isDestroyed(){return false;}}
'''
FILES['android/app/AlertDialog.java'] = '''package android.app;
 public class AlertDialog {
 public static int shown=0;
 public static class Builder {public Builder(Activity host){}
 public Builder setTitle(String s){return this;} public Builder setView(Object v){return this;}
 public Builder setPositiveButton(String s,Object l){return this;}
 public AlertDialog show(){shown++;return new AlertDialog();}}
 }'''
FILES['android/graphics/Color.java'] = 'package android.graphics;public class Color{public static final int WHITE=-1;}'
FILES['android/util/Log.java'] = '''package android.util;public class Log {
 public static int d(String a,String b){return 0;}public static int i(String a,String b){return 0;}
 public static int w(String a,String b){return 0;}public static int w(String a,String b,Throwable e){return 0;}
 public static int e(String a,String b,Throwable e){return 0;} }'''
FILES['android/content/res/Resources.java'] = '''package android.content.res;
 public class Resources {public int getIdentifier(String a,String b,String c){return 1;}
 public android.util.DisplayMetrics getDisplayMetrics(){return new android.util.DisplayMetrics();}}'''
FILES['android/util/DisplayMetrics.java'] = 'package android.util;public class DisplayMetrics {public float density=1f;}'
FILES['android/view/Gravity.java'] = 'package android.view;public class Gravity {public static final int CENTER_VERTICAL=16;}'
FILES['android/widget/ImageView.java'] = '''package android.widget;
 public class ImageView extends android.view.View {
 public ImageView(android.content.Context c){} public enum ScaleType{FIT_CENTER}
 public void setScaleType(ScaleType t){} }'''
FILES['android/widget/TextView.java'] = '''package android.widget;
 public class TextView extends android.view.View {
 public TextView(android.content.Context c){}public void setText(String s){}
 public void setTextColor(int c){}public void setTextSize(int size){} }'''
FILES['android/widget/LinearLayout.java'] = '''package android.widget;
 public class LinearLayout extends android.view.ViewGroup {
 public static final int VERTICAL=1,HORIZONTAL=0;
 public LinearLayout(android.content.Context c){} public void setOrientation(int v){}
 public void setGravity(int v){}
 public static class LayoutParams {public LayoutParams(int w,int h){}
 public LayoutParams(int w,int h,float weight){}}}'''
FILES['android/widget/ScrollView.java'] = '''package android.widget;
 public class ScrollView extends android.view.ViewGroup {
 public ScrollView(android.content.Context c){}public void setFillViewport(boolean v){} }'''
FILES['com/bumptech/glide/Glide.java'] = '''package com.bumptech.glide;
 public class Glide {public static final java.util.List<String> loaded=new java.util.ArrayList<>();
 public static Loader with(android.content.Context c){return new Loader();}
 public static class Loader {public Loader load(String url){loaded.add(url);return this;}
 public void into(android.widget.ImageView v){}}}'''
FILES['bttv/emote/EmoteUrlUtil.java'] = '''package bttv.emote;
 public class EmoteUrlUtil {
 public static final String PREFIX="BTTV-zw-";
 public static int overlayBaseSteps(String id){if(id==null||!id.startsWith(PREFIX))return -1;
 int end=id.indexOf('-',PREFIX.length());if(end<0)return -1;
 try{return Integer.parseInt(id.substring(PREFIX.length(),end));}catch(Exception e){return -1;}}
 public static String extractBTTVId(String id){if(id==null||!id.startsWith("BTTV-"))return null;
 if(overlayBaseSteps(id)>=0)return id.substring(id.indexOf('-',PREFIX.length())+1);
 if(id.startsWith("BTTV-wide-"))return id.substring(10);
 return id.substring(5);}}
'''
FILES['bttv/emote/Emote.java'] = '''package bttv.emote;
 public class Emote {public Emotes.Source source=Emotes.Source.STV;
 public String code,url,owner;public Emote(String c){code=c;url="https://example.com/"+c;owner="owner";}}'''
FILES['bttv/emote/Emotes.java'] = '''package bttv.emote;
 public class Emotes {public enum Source{BTTV,FFZ,STV}
 public static Emote getEmoteById(String id){return new Emote(id);} }'''
FILES['bttv/emote/RNEmoteCard.java'] = '''package bttv.emote;
 public class RNEmoteCard {static String providerAndScope(Emote e){return "7TV Channel Emote";}}'''
FILES['bttv/emote/StackTest.java'] = '''package bttv.emote;
 import android.view.*;
 import android.app.AlertDialog;
 import java.util.Arrays;
 public class StackTest {
 static void ok(boolean test){if(!test)throw new AssertionError();}
 static ViewGroup tag(String name){ViewGroup g=new ViewGroup();g.setTag(name);return g;}
 public static void main(String[] args){
 java.util.List<String> ids=Arrays.asList("BTTV-base","BTTV-zw-0-overlay","BTTV-zw-0-overlay2","BTTV-unrelated");
 ok(StackedEmoteDetails.findStack(ids,0).ids.size()==3);
 ok(StackedEmoteDetails.findStack(ids,2).ids.size()==3);
 ok(StackedEmoteDetails.findStack(Arrays.asList("BTTV-zw-0-orphan"),0)==null);
 // Different nested parent views in one chat row must still form one stack.
 ViewGroup row=tag("chat-message-row");
 ViewGroup left=tag("container-left");row.add(left);
 ViewGroup base=tag("chat-emote-press-BTTV-base");left.add(base);
 View baseWrapper=new View();baseWrapper.setTag("chat-emote-wrapper-BTTV-base");base.add(baseWrapper);
 ViewGroup right=tag("container-right");row.add(right);
 ViewGroup overlay=tag("chat-emote-press-BTTV-zw-0-overlay");right.add(overlay);
 View image=new View();image.setTag("chat-emote-wrapper-BTTV-zw-0-overlay");overlay.add(image);
 StackedEmoteDetails.onTestId(base,"chat-emote-press-BTTV-base");
 StackedEmoteDetails.onTestId(overlay,"chat-emote-press-BTTV-zw-0-overlay");
 // Touch listener must NOT eat the native React Native onPress.
 ok(!overlay.dispatch(new MotionEvent(MotionEvent.ACTION_DOWN)));
 ok(StackedEmoteDetails.onCardRequest("BTTV-zw-0-overlay")!=null);
 ok(StackedEmoteDetails.cardTitle("BTTV-zw-0-overlay","").contains(" + "));
 ok(StackedEmoteDetails.cardDescription().contains("Base:"));
 ok(StackedEmoteDetails.cardDescription().contains("Overlay:"));
 ok(StackedEmoteDetails.cardOrigins().contains("7TV Channel Emote"));
 ok(!base.dispatch(new MotionEvent(MotionEvent.ACTION_DOWN)));
 ok(StackedEmoteDetails.onCardRequest("BTTV-base")!=null);
 ok(AlertDialog.shown==0); // never open a duplicate Android popup
 // Ordinary emotes and unrelated chat rows must remain untouched.
 ViewGroup single=tag("chat-message-row");
 ViewGroup normal=tag("chat-emote-press-25");single.add(normal);
 View thumb=new View();thumb.setTag("chat-emote-wrapper-25");normal.add(thumb);
 StackedEmoteDetails.onTestId(normal,"chat-emote-press-25");
 ok(!normal.dispatch(new MotionEvent(MotionEvent.ACTION_DOWN)));
 ok(StackedEmoteDetails.onCardRequest("25")==null);
 System.out.println("PASS stacked native EmoteCard without duplicate dialog");
 }
 }'''

class StackCardTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('java') and shutil.which('javac'), 'JDK not installed')
    def test_stack_passes_through_to_native_card(self):
        with tempfile.TemporaryDirectory() as root:
            paths = []
            for name, contents in FILES.items():
                target = Path(root, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(contents)
                paths.append(str(target))
            completed = subprocess.run(['javac', '-d', root, *paths,
                     str(JAVA / 'emote/StackedEmoteDetails.java')],
                    capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            completed = subprocess.run(['java', '-cp', root, 'bttv.emote.StackTest'],
                    capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('PASS stacked native EmoteCard', completed.stdout)

    def test_existing_hook_wires_new_cards(self):
        source = (JAVA / 'SplitChat318.java').read_text()
        self.assertIn('WideEmotes.onWrapperTestId(view, testId)', source)
        self.assertIn('StackedEmoteDetails.onTestId(view, testId)', source)
        self.assertIn('RNEmoteCard.onNativeCardTestId(view, testId)', source)
        card = (JAVA / 'emote/RNEmoteCard.java').read_text()
        self.assertIn('subscriptionSummaries', card)
        self.assertIn('onNativeCardText(View view)', card)
        self.assertIn('StackedEmoteDetails.onCardRequest(emoteId)', card)
        self.assertNotIn('new AlertDialog.Builder(', (JAVA / 'emote/StackedEmoteDetails.java').read_text())
        script = (JAVA.parents[5] / 'v31/apply_hooks_31_8.py').read_text()
        self.assertIn('onReactNativeText(Landroid/view/View;)V', script)

if __name__ == '__main__':
    unittest.main()
