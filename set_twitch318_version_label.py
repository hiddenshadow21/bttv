#!/usr/bin/env python3
"""Change only Stage 1's displayed BTTV version. No APK manifest/versionCode edits."""
import argparse
import pathlib
import re
import sys

ap = argparse.ArgumentParser()
ap.add_argument('--check', action='store_true')
ap.add_argument('--apply', action='store_true')
a = ap.parse_args()
path = pathlib.Path('mod/app/src/main/java/bttv/rn/RNPortHooks.java')
if not path.is_file():
    sys.exit('ERROR: '+str(path)+' not found. Install React Native Stage 1 first.')
s = path.read_text(encoding='utf-8')
pat = re.compile(r'(private\s+static\s+final\s+String\s+LABEL\s*=\s*")BTTV [^"\r\n]*(";)')
ms = list(pat.finditer(s))
if len(ms) != 1:
    sys.exit(f'ERROR: expected one LABEL declaration; found {len(ms)}. No changes made.')
new_label='BTTV 0.44.0-beta (Twitch 31.8.0)'
old_label=ms[0].group(0)
print('Before:', old_label.strip())
print('After:  private static final String LABEL = "'+new_label+'";')
if a.apply:
    updated = pat.sub(lambda m:m.group(1)+new_label+m.group(2),s,count=1)
    if updated != s:
        backup=path.with_suffix('.java.branding-backup')
        if not backup.exists(): backup.write_text(s,encoding='utf-8')
        path.write_text(updated,encoding='utf-8')
        print('Updated',path,'(backup:',backup,')')
    else: print('Already current')
elif not a.check:
    sys.exit('Use --check or --apply')
