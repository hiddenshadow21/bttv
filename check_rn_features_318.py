#!/usr/bin/env python3
"""Read-only preflight checks for the 31.8.0 RN features bundle."""
from __future__ import annotations
import argparse
import pathlib
import subprocess
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
FILES = {
    'patches/live/zzzzzz_rn_features_318.patch': ['RNFeatureHooks318', 'RNSettingsEntry318', 'ReactImageManager'],
    'mod/app/src/main/java/bttv/rn/RNFeatureHooks318.java': ['rewriteFrame', 'redirectImageUri', 'interceptNetwork', 'rewriteReactSources'],
    'mod/app/src/main/java/bttv/rn/RNSettingsEntry318.java': ['wrap(final View composeView)', 'BTTV Settings', 'SettingsNavigation.open'],
}

def check_source() -> int:
    ok = True
    for name, expected in FILES.items():
        path = ROOT / name
        if not path.is_file():
            print('MISSING', name)
            ok = False
            continue
        data = path.read_text('utf-8')
        if all(x in data for x in expected):
            print('OK', name)
        else:
            print('MISSING required content', name)
            ok = False
        result = subprocess.run(['git','ls-files','--error-unmatch','--',name],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if result.returncode:
            print('UNTRACKED by Git (Docker may omit it):',name)
            ok=False
    stage = ROOT/'patches/live/zzzzx_rn_stage1.patch'
    if not stage.is_file() or 'RNPortHooks' not in stage.read_text('utf-8'):
        print('MISSING prerequisite Stage 1 patch')
        ok=False
    else:
        print('OK Stage 1 prerequisite')
    print('SOURCE PREFLIGHT', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1

def check_apk(path: pathlib.Path)->int:
    if not path.is_file():
        print('APK not found:',path); return 1
    with zipfile.ZipFile(path) as apk:
        dexes=[n for n in apk.namelist() if n.startswith('classes') and n.endswith('.dex')]
        for marker in (b'RNFeatureHooks318',b'RNSettingsEntry318'):
            present=[n for n in dexes if marker in apk.read(n)]
            if not present:
                print('FAIL: APK has no',marker.decode());return 1
            print('PASS:',marker.decode(),'found in',', '.join(present))
    print('APK CHECK PASS (code presence, not runtime behavior)')
    return 0

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apk',type=pathlib.Path)
    args=p.parse_args()
    sys.exit(check_apk(args.apk) if args.apk else check_source())
