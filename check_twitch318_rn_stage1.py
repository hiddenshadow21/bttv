#!/usr/bin/env python3
"""Source and APK-marker preflight for BTTV RN stage-1 integration.

This is not an APK runtime test. Source must be Git-indexed for Docker staging.
"""
import argparse
import pathlib
import subprocess
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
PATCH = pathlib.Path('patches/live/zzzzx_rn_stage1.patch')
JAVA = pathlib.Path('mod/app/src/main/java/bttv/rn/RNPortHooks.java')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--apk', type=pathlib.Path)
    args = parser.parse_args()
    if args.apk:
        if not args.apk.is_file():
            sys.exit(f'APK missing: {args.apk}')
        with zipfile.ZipFile(args.apk) as z:
            dex_files = [p for p in z.namelist() if (p == 'classes.dex' or p.startswith('classes')) and p.endswith('.dex')]
            found = [p for p in dex_files if b'BTTV318RN' in z.read(p)]
        print('DEX files:', len(dex_files))
        print(('PASS' if found else 'FAIL') + ': RN hook tag ' + ('found in ' + ', '.join(found) if found else 'missing from all DEX files'))
        return 0 if found else 1

    ok = True
    for file, needles in ((PATCH, ['Lfy90;->f:I', 'NetworkingModule.smali', 'RNPortHooks;->brandSettings']),
                          (JAVA, ['BTTV318RN', 'onWebSocketText', 'onHttpRequest', 'brandSettings'])):
        path = ROOT / file
        if not path.exists():
            print('MISSING:', file)
            ok = False
            continue
        content = path.read_text('utf-8')
        missing = [needle for needle in needles if needle not in content]
        if missing:
            print('FAIL:', file, 'missing', missing)
            ok = False
        else:
            print('OK:', file)
        res = subprocess.run(['git', 'ls-files', '--error-unmatch', '--', file.as_posix()],
                             cwd=ROOT, capture_output=True, text=True)
        if res.returncode != 0:
            print('UNTRACKED:', file, '(run git add to include it in Docker staging)')
            ok = False
        else:
            print('TRACKED:', file)
    print('SOURCE PREFLIGHT', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
