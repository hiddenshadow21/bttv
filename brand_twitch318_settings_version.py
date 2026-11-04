#!/usr/bin/env python3
"""Experimental *visible settings label* shim for BTTV 31.8.0.

Changes the displayed Twitch version text only when represented by a native
TextView. Does not alter manifest, package identity, or other UI settings.
Requires SettingsNavigation.install(Activity, Menu) to be invoked.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
from pathlib import Path
import sys

TARGET=Path('mod/app/src/main/java/bttv/settings/SettingsNavigation.java')
MARKER='BTTV318Brand: native settings version label shim'
BEFORE='    public static void install(final Activity activity, Menu menu) {'
HOOK='        installBttv318VersionBranding(activity); // '+MARKER
HELPER='''
    // BTTV318Brand: native settings version label shim. If the version is drawn by
    // Compose rather than a TextView, log that fact instead of altering unrelated UI.
    private static void installBttv318VersionBranding(final Activity activity) {
        if (activity == null || activity.getWindow() == null) return;
        try {
            final android.view.View decor = activity.getWindow().getDecorView();
            final android.view.ViewTreeObserver.OnGlobalLayoutListener listener =
                    new android.view.ViewTreeObserver.OnGlobalLayoutListener() {
                private int layouts = 0;
                @Override public void onGlobalLayout() {
                    boolean changed = replaceBttv318VersionLabel(decor, activity);
                    if (changed || ++layouts >= 200) {
                        try {
                            android.view.ViewTreeObserver observer = decor.getViewTreeObserver();
                            if (observer.isAlive()) observer.removeOnGlobalLayoutListener(this);
                        } catch (Throwable ignored) { }
                        if (!changed) android.util.Log.i("BTTV318Brand",
                                "No native TextView with Twitch 31.8 version; possibly Compose");
                    }
                }
            };
            decor.getViewTreeObserver().addOnGlobalLayoutListener(listener);
            replaceBttv318VersionLabel(decor, activity);
            android.util.Log.i("BTTV318Brand", "Settings version label observer installed");
        } catch (Throwable failure) {
            android.util.Log.w("BTTV318Brand", "Could not inspect settings version label", failure);
        }
    }

    private static boolean replaceBttv318VersionLabel(android.view.View root, Activity activity) {
        if (root == null) return false;
        java.util.ArrayDeque<android.view.View> pending = new java.util.ArrayDeque<>();
        pending.add(root);
        int visited = 0;
        while (!pending.isEmpty() && visited++ < 1000) {
            android.view.View item = pending.removeFirst();
            if (item instanceof android.widget.TextView) {
                android.widget.TextView label = (android.widget.TextView) item;
                CharSequence chars = label.getText();
                if (chars != null) {
                    String text = chars.toString();
                    String lower = text.toLowerCase(java.util.Locale.ROOT);
                    if (text.length() <= 90 && lower.contains("twitch")
                            && (lower.contains("31.8.0") || lower.contains("31.8"))) {
                        String version = "0.43.2-beta";
                        try {
                            android.content.pm.PackageInfo info = activity.getPackageManager()
                                    .getPackageInfo(activity.getPackageName(), 0);
                            if (info.versionName != null) version = info.versionName;
                        } catch (Throwable ignored) { }
                        label.setText("BTTV " + version + " (Twitch 31.8.0)");
                        android.util.Log.i("BTTV318Brand", "Replaced native settings version label");
                        return true;
                    }
                }
            }
            if (item instanceof android.view.ViewGroup) {
                android.view.ViewGroup group = (android.view.ViewGroup) item;
                for (int i = 0; i < group.getChildCount(); i++) {
                    android.view.View child = group.getChildAt(i);
                    if (child != null) pending.addLast(child);
                }
            }
        }
        return false;
    }
'''

def digest(b):return sha256(b).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    command=ap.add_mutually_exclusive_group(required=True)
    command.add_argument('--check',action='store_true')
    command.add_argument('--apply',action='store_true')
    command.add_argument('--revert',action='store_true')
    ap.add_argument('--root',type=Path,default=Path('.'))
    a=ap.parse_args()
    root=a.root.resolve(); path=root/TARGET
    state=root/'.bttv318-version-branding-source.bak'
    if a.revert:
        if not state.exists() or not path.exists():ap.error('No backup/target found')
        curr=path.read_text(encoding='utf-8')
        if MARKER not in curr:ap.error('Source no longer includes this shim; refusing to overwrite')
        # Revert only our inserted code; keep unrelated edits made afterward.
        if curr.count(HOOK)!=1 or curr.count(HELPER)!=1:ap.error('Shim changed; refuse ambiguous revert')
        restored=curr.replace(HOOK+'\n','',1).replace(HELPER,'',1)
        path.write_text(restored,encoding='utf-8',newline='\n')
        state.unlink()
        print('Removed version-label shim; other Java diagnostics are preserved.')
        return
    if not path.is_file():ap.error(f'Missing {path}')
    raw=path.read_bytes()
    if b'\r\n' in raw:ap.error('Expected LF source (CRLF present)')
    text=raw.decode('utf-8')
    if MARKER in text:
        if a.check:print('Version-label shim is already installed.');return
        ap.error('Already installed')
    if text.count(BEFORE)!=1 or not text.rstrip().endswith('}'):
        ap.error('SettingsNavigation structure differs; no changes made.')
    result=text.replace(BEFORE,BEFORE+'\n'+HOOK,1)
    idx=result.rfind('\n}')
    if idx<0:ap.error('Cannot find final class brace')
    result=result[:idx]+HELPER+result[idx:]
    if a.check:
        print('CHECK OK: can insert optional TextView version-label shim. Does not promise Compose version change.')
        return
    if state.exists():ap.error('Backup exists; refusing to overwrite')
    state.write_bytes(raw)
    path.write_text(result,encoding='utf-8',newline='\n')
    print('Applied optional shim to '+str(TARGET))
    print('Stage Java source with git add; verify with adb logcat -s BTTV318Brand:I '*1)
if __name__=='__main__':
    try:main()
    except Exception as error:
        print('ERROR:',error,file=sys.stderr);sys.exit(1)
