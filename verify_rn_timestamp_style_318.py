#!/usr/bin/env python3
"""Verify source staging and optional built APK contains the RN timestamp renderer."""
from __future__ import annotations
import argparse
import subprocess
import zipfile
from pathlib import Path

HELPER = Path('mod/app/src/main/java/bttv/rn/RNTimestampStyle318.java')
PATCH = Path('patches/live/zzzzzzzb_rn_timestamp_style_318.patch')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path)
    args=parser.parse_args()
    problems=[]
    for path,needle in [(HELPER,'class RNTimestampStyle318'),(PATCH,'RNTimestampStyle318;->style')]:
        if not path.is_file() or needle not in path.read_text(encoding='utf-8',errors='replace'):
            problems.append('Missing or malformed '+str(path))
        else:
            print('OK:',path)
        if path.is_file():
            status=subprocess.run(['git','ls-files','--error-unmatch','--',str(path)],capture_output=True,text=True)
            if status.returncode: problems.append('Untracked by git: '+str(path))
            else: print('TRACKED:',path)
    if args.apk:
        if not args.apk.is_file():
            problems.append('APK not found: '+str(args.apk))
        else:
            with zipfile.ZipFile(args.apk) as z:
                dex=[i for i in z.namelist() if i.startswith('classes') and i.endswith('.dex')]
                matches=[i for i in dex if b'RNTimestampStyle318' in z.read(i)]
                if matches: print('OK: renderer class present in',', '.join(matches))
                else: problems.append('RNTimestampStyle318 absent from all APK dex files')
    if problems:
        for error in problems:print('ERROR:',error)
        raise SystemExit(1)
    print('PASS: timestamp renderer source and APK check')

if __name__=='__main__':main()
