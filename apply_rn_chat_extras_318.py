#!/usr/bin/env python3
"""Conservative installer: RN ROOMSTATE detection and [HH:mm] timestamps.

The companion ChannelPoints verification is read-only. This script does not
change native bonus-claim logic or any settings/version code.
"""
import argparse
import re
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT_FILE = Path('mod/app/src/main/java/bttv/rn/RNFeatureHooks318.java')
NEW_FILE = Path('mod/app/src/main/java/bttv/rn/RNChatExtras318.java')
POINTS_HOOK = Path('patches/live/z89.smali.patch')
POINTS_JAVA = Path('mod/app/src/main/java/bttv/ChannelPoints.java')
SAMPLE = Path(__file__).with_name('RNChatExtras318.java')
OLD_GUARD = '        if (frame == null || frame.indexOf(" PRIVMSG #") == -1) return frame;'
NEW_GUARD = ('        if (frame == null) return null;\n'
             '        RNChatExtras318.onRoomState(frame);\n'
             '        if (frame.indexOf(" PRIVMSG #") == -1) return frame;')
OLD_LINE = '                String replacement = rewriteLine(lines[i]);'
NEW_LINE = '                String replacement = RNChatExtras318.addTimestamp(rewriteLine(lines[i]));'

def check(root):
    target = root / ROOT_FILE
    if not target.exists(): raise ValueError(f'Missing: {target}; install RN functional hooks first')
    content = target.read_text(encoding='utf-8-sig')
    if NEW_GUARD in content and NEW_LINE in content:
        state = 'ALREADY INSTALLED'
    elif content.count(OLD_GUARD) == 1 and content.count(OLD_LINE) == 1:
        state = 'READY'
    else:
        raise ValueError('RNFeatureHooks318.java differs from the verified functional version; no source changed')
    for rel in (POINTS_HOOK, POINTS_JAVA):
        if not (root / rel).is_file():
            raise ValueError('Missing channel-points source: ' + str(rel))
    hook = (root / POINTS_HOOK).read_text(encoding='utf-8-sig')
    points = (root / POINTS_JAVA).read_text(encoding='utf-8-sig')
    if not re.search(r'Lbttv/ChannelPoints;->shouldAutoRedeem\(Ljava/lang/String;\)Z', hook):
        raise ValueError('Channel-points patch lacks the shouldAutoRedeem call')
    if not re.search(r'Lqf9;->E\(Ljava/lang/String;Ltv/twitch/android/shared/one/chat/pub/ChatModeMetadata;\)V', hook):
        raise ValueError('Channel-points patch lacks 31.8.0 qf9 claim method')
    if 'shouldAutoRedeem(String claimId)' not in points:
        raise ValueError('ChannelPoints.java is not the expected port')
    print('RN chat extras:', state)
    print('Channel-points: existing native 31.8.0 ic9/qf9 claim hook present (runtime NOT verified)')
    if 'BTTV318Points' not in points:
        print('WARNING: channel-point decision logging missing. Network migration v3 adds BTTV318Points logs.')
    net = root / 'mod/app/src/main/java/bttv/Network.java'
    if net.exists() and 'import okhttp3.Callback;' in net.read_text(encoding='utf-8-sig'):
        print('WARNING: original unshaded OkHttp references remain; emote catalogs will fail until network v3 migration is applied.')
    return state

def main():
    p=argparse.ArgumentParser()
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--check', action='store_true')
    g.add_argument('--apply', action='store_true')
    g.add_argument('--revert', action='store_true')
    g.add_argument('--apk', type=Path)
    a=p.parse_args()
    root=Path.cwd()
    if a.apk:
        with zipfile.ZipFile(a.apk) as z:
            dex=[n for n in z.namelist() if re.fullmatch(r'classes\d*\.dex',n)]
            data={n:z.read(n) for n in dex}
            found=[n for n, chunk in data.items() if b'RNChatExtras318' in chunk]
            points=[n for n, chunk in data.items() if b'ChannelPoints' in chunk]
            points_logs=any(b'BTTV318Points' in chunk for chunk in data.values())
        print(f'DEX files: {len(dex)}; RNChatExtras318:', ', '.join(found) if found else 'MISSING')
        print('ChannelPoints class present:', bool(points))
        print('Channel-points decision logging:', 'PRESENT' if points_logs else 'NOT FOUND (v3 networking/points migration may be missing)')
        sys.exit(0 if found and points else 1)
    if a.revert:
        t=root/ROOT_FILE
        s=t.read_text(encoding='utf-8-sig')
        if s.count(NEW_GUARD)!=1 or s.count(NEW_LINE)!=1:
            raise ValueError('RN integration does not match this kit; no revert performed')
        t.write_text(s.replace(NEW_GUARD, OLD_GUARD).replace(NEW_LINE,OLD_LINE), encoding='utf-8')
        # Leave the newly created Java file for user-managed Git cleanup.
        print('Restored the two RNFeatureHooks318.java locations. To remove helper use git rm --',NEW_FILE)
        return
    state=check(root)
    if a.check:
        return
    src=root/ROOT_FILE
    dst=root/NEW_FILE
    source=SAMPLE.read_text(encoding='utf-8')
    if state=='ALREADY INSTALLED':
        if not dst.exists() or dst.read_text(encoding='utf-8-sig')!=source:
            raise ValueError('Installed helper differs; refusing to overwrite custom changes')
        print('Already installed; no changes')
        return
    if dst.exists():
        raise ValueError('The helper already exists but hooks are not installed; refusing to overwrite')
    backup=root/'dist'/('rnchat-extras-backup-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(src, backup / src.name)
    body=src.read_text(encoding='utf-8-sig')
    updated=body.replace(OLD_GUARD,NEW_GUARD,1).replace(OLD_LINE, NEW_LINE,1)
    if updated.count('RNChatExtras318.onRoomState(frame)')!=1 or updated.count('RNChatExtras318.addTimestamp(')!=1:
        raise ValueError('Unexpected hook count; aborting')
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(source,encoding='utf-8',newline='\n')
    src.write_text(updated,encoding='utf-8',newline='\n')
    print('Installed RN ROOMSTATE/channel catalog trigger + IRC text timestamps.')
    print('Backup:',backup)
    print('Stage BOTH changed Java files with git add before Docker build.')

if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, zipfile.BadZipFile) as e:
        print('ERROR:',e,file=sys.stderr)
        sys.exit(1)
