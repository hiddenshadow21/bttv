#!/usr/bin/env python3
"""Twitch 31.8.0 combined RN emotes + sender timestamp upgrade.

Rebased against the previously installed RN Stage 1, functional emotes and
RN chat timestamp kits. All source edits are preflighted before modification.
No prior working smali or settings patch is replaced.
"""
import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
KIT = Path(__file__).resolve().parent
PATCH_JAVA = KIT / 'data/rn_java_318_upgrade.patch'
PATCH_SMALI = KIT / 'patches/live/zzzzzzza_rn_animated_input_318.patch'
ANIMATED_HELPER = KIT / 'mod/app/src/main/java/bttv/rn/RNAnimatedInput318.java'
JAVA1 = Path('mod/app/src/main/java/bttv/rn/RNFeatureHooks318.java')
JAVA2 = Path('mod/app/src/main/java/bttv/rn/RNChatExtras318.java')
EMOTE = Path('mod/app/src/main/java/bttv/emote/Emote.java')
DST_HELPER = Path('mod/app/src/main/java/bttv/rn/RNAnimatedInput318.java')
DST_SMALI = Path('patches/live/zzzzzzza_rn_animated_input_318.patch')
PREREQ = [
    Path('patches/live/zzzzx_rn_stage1.patch'),
    Path('patches/live/zzzzzz_rn_features_318.patch'),
    Path('mod/app/src/main/java/bttv/rn/RNPortHooks.java'),
]


def read(file):
    return file.read_text(encoding='utf-8-sig').replace('\r\n', '\n')


def apply_gif_selection(source):
    if 'String format = "WEBP";' in source and '.equals(format)' in source:
        return source, 'ALREADY INSTALLED'
    old_file_check = 'if (!emote.getString("format").equals("WEBP")) {'
    marker = 'JSONArray files = hostObj.getJSONArray("files");'
    if source.count(old_file_check) != 1 or source.count(marker) != 1:
        raise ValueError('Emote.java 7TV format selector has changed; refusing an unverified rewrite')
    insert = '''JSONArray files = hostObj.getJSONArray("files");
                // Animated 7TV WebP may be decoded only as a still in RN's Fresco pipeline.
                // Prefer the GIF variant when one is available (PR #740 behavior).
                String format = "WEBP";
                if (data.optBoolean("animated")) {
                    for (int gifIndex = 0; gifIndex < files.length(); gifIndex++) {
                        if ("GIF".equals(files.getJSONObject(gifIndex).getString("format"))) {
                            format = "GIF";
                            break;
                        }
                    }
                }'''
    return (source.replace(marker, insert, 1)
                  .replace(old_file_check, 'if (!emote.getString("format").equals(format)) {', 1), 'READY')


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def check():
    required = [JAVA1, JAVA2, EMOTE] + PREREQ
    for rel in required:
        if not (ROOT / rel).is_file():
            raise ValueError(f'Missing prerequisite source/patch: {rel}')
    for p in (PATCH_JAVA, PATCH_SMALI, ANIMATED_HELPER):
        if not p.is_file():
            raise ValueError(f'Incomplete kit: {p}')
    if 'RNAnimatedInput318' not in read(PATCH_SMALI):
        raise ValueError('Smali animation patch missing marker')
    if 'Animated input emote decoded' not in read(ANIMATED_HELPER):
        raise ValueError('GIF helper missing marker')
    if 'RNChatExtras318.addTimestamp' not in read(ROOT/JAVA1):
        raise ValueError('First install the RN chat timestamps kit; current hook is missing')

    feature = read(ROOT/JAVA1)
    chat = read(ROOT/JAVA2)
    installed = ('External emote metadata card answered' in feature
                 and 'Picker channel catalogs:' in feature
                 and 'Timestamp moved to sender display label' in chat)
    if installed:
        if not ('RNAnimatedInput318.register' in feature):
            raise ValueError('Partial Java upgrade detected: animation registration missing')
        java_state = 'ALREADY INSTALLED'
    else:
        if any(k in feature for k in ('External emote metadata card answered', 'Picker channel catalogs:', 'RNAnimatedInput318.register')) or 'Timestamp moved to sender display label' in chat:
            raise ValueError('Partial RN upgrade detected; restore source from backup before trying again')
        candidate=git('apply','--check',str(PATCH_JAVA))
        if candidate.returncode:
            raise ValueError('RN Java patch does not apply cleanly; no changes made.\n' + candidate.stderr.strip())
        java_state = 'READY'
    modified_emote, gif_state = apply_gif_selection(read(ROOT/EMOTE))
    for kit_path, rel in ((ANIMATED_HELPER,DST_HELPER),(PATCH_SMALI,DST_SMALI)):
        existing=ROOT/rel
        if existing.exists() and read(existing) != read(kit_path):
            raise ValueError(f'{rel} exists with different contents; refusing overwrite')
    print('RN hooks, picker and metadata:',java_state)
    print('7TV animated GIF URL selector:',gif_state)
    print('RN input animation smali and Java:', 'READY' if not (ROOT/DST_HELPER).exists() else 'PRESENT')
    print('Preserves: working settings, version 0.44.0-beta, Vertical View verifier fix, points hook')
    return java_state, gif_state, modified_emote


def apply():
    java_state, gif_state, new_emote=check()
    if java_state=='ALREADY INSTALLED' and gif_state=='ALREADY INSTALLED' and (ROOT/DST_HELPER).exists() and (ROOT/DST_SMALI).exists():
        print('Already installed, nothing to change.'); return
    destination=ROOT/'dist'/('rn-unified-backup-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    destination.mkdir(parents=True,exist_ok=False)
    originals={}
    targets=(JAVA1,JAVA2,EMOTE,DST_HELPER,DST_SMALI)
    for rel in targets:
        target=ROOT/rel
        if target.exists():
            originals[rel]=target.read_bytes()
            out=destination/rel
            out.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(target,out)
    try:
        if java_state=='READY':
            result=git('apply',str(PATCH_JAVA))
            if result.returncode: raise ValueError('Java patch application failed: '+result.stderr)
        if gif_state=='READY':
            (ROOT/EMOTE).write_text(new_emote,encoding='utf-8',newline='\n')
        for kit_path, rel in ((ANIMATED_HELPER,DST_HELPER),(PATCH_SMALI,DST_SMALI)):
            dest=ROOT/rel
            dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists(): shutil.copy2(kit_path,dest)
        # Ensure source update complete
        _, _, _ = check()
    except BaseException:
        for rel in targets:
            p=ROOT/rel
            if rel in originals:
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(originals[rel])
            elif p.exists(): p.unlink()
        raise
    print('APPLIED. Backup:',destination)
    print('Stage all five files using git add before the Docker build.')


def apk(path):
    with zipfile.ZipFile(path) as z:
        dex={p:z.read(p) for p in z.namelist() if re.fullmatch(r'classes\d*\.dex',p)}
    needles=[b'RNAnimatedInput318', b'External emote metadata card answered',
             b'Picker channel catalogs:', b'Timestamp moved to sender display label']
    print('DEX files:',len(dex))
    all_bytes=b''.join(dex.values())
    missing=[name.decode() for name in needles if name not in all_bytes]
    if missing: raise ValueError('Missing DEX markers: '+', '.join(missing))
    print('APK PASS: animated-input helper, external metadata card, channel picker and sender timestamps present')


def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check',action='store_true')
    group.add_argument('--apply',action='store_true')
    group.add_argument('--apk',type=Path)
    args=parser.parse_args()
    if args.apk: apk(args.apk)
    elif args.apply: apply()
    else: check()

if __name__=='__main__':
    try: main()
    except (ValueError,OSError,zipfile.BadZipFile) as exc:
        print('ERROR:',exc,file=sys.stderr)
        sys.exit(1)
