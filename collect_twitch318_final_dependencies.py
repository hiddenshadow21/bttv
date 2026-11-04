#!/usr/bin/env python3
"""Export the class definitions and current patches needed to finish the final
three BTTV/Twitch 31.8.0 patch failures *and* validate existing helper links.

Requires collect_twitch_port_reference.py in /source (already used previously).

  docker compose run --rm --entrypoint python3 build \
    /source/collect_twitch318_final_dependencies.py \
    --old /source/twitch-31.2.0.apkm --new /source/twitch.zip \
    --output /output/twitch318-final-dependencies.zip

Does not modify input APKs or repository patches.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import tempfile
import zipfile
from pathlib import Path
from collect_twitch_port_reference import decode, OLD_EXPECTED

# Explicit names needed to reason about the original/current bridge call sites.
# A shared obfuscated name does NOT indicate the class is semantically equal.
NAMES = set('''a120 b6z en20 xoz qnc e9d fn2 emj ppz r2k r4b0 tij
 dl2 ffo xpo cl2 qz0 o01 en6 vi50 i0x l1x zk2 lix ojx bn2 pjx
 r360 dv60 l5p cgp fmp fv1 qt1 wjf pqf xjj aaj va6 f86 qw9 fsi
 vp0 d6f wqj p9j jqs xjj njj pgr p90 e90 xjx nko aji
 NativeSettingsBridge NativeSettingsClick NativePickerBridge GifBridge
 TwitchApplication SettingsActivity'''.split())
# Repo patch files may have slightly different source locations in this PR.
PATCHES = [
 'live/cl2.smali.patch','live/r2k.smali.patch','live/zy_gif_modes.patch',
 'live/ffo.smali.patch','live/f86.smali.patch','live/qt1.smali.patch',
 'live/wjf.smali.patch','live/aaj.smali.patch','live/zz_emote_details.patch',
 'live/bttvcompat.NativeSettingsBridge.smali.patch',
 'live/bttvcompat.NativePickerBridge.smali.patch',
 'settings/tv.twitch.android.settings.SettingsActivity.smali.patch',
 'tv.twitch.android.app.consumer.TwitchApplication.smali.patch',
]
# Additional renamed Compose and settings candidates, based on the prior
# reference index, are selected by stem (not merely by DEX folder).
NAMES.update('''lor qmj dos lbj fn2 rqf xgv jqo rqx f9c k7d k76
 r7b0 l5j xag dw0 aw0'''.split())

# Collect only a modest number of synthetic settings callbacks. On 31.8,
# FFO's x2() creates Lqnc and w2() constructs Le9d. Their classes are
# collected by NAMES, so this scan is a fallback for other click handlers.
SYMBOLS = ('Len20;', 'La120;', 'Lxoz;', 'Lb6z;')
HELPER = re.compile(r'\b(?:invoke-[\w/-]+|(?:[is]get|[is]put)(?:-[\w]+)?)[^\n]*\b(L[\w/$]+;)->([^\( :]+)', re.M)


def choose(decoded: Path):
    out = {}
    for p in decoded.rglob('*.smali'):
        if p.stem in NAMES:
            rel = p.relative_to(decoded).as_posix()
            out[rel] = p
    return out


def signature_summary(text: str) -> dict:
    """Human-reviewable information only; no guess at obfuscation mappings."""
    return {
        'class': next((line for line in text.splitlines() if line.startswith('.class ')), ''),
        'super': next((line for line in text.splitlines() if line.startswith('.super ')), ''),
        'fields': [line for line in text.splitlines() if line.startswith('.field ')],
        'methods': [line for line in text.splitlines() if line.startswith('.method ')],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old', type=Path, default=Path('/source/twitch-31.2.0.apkm'))
    parser.add_argument('--new', type=Path, default=Path('/source/twitch.zip'))
    parser.add_argument('--patches', type=Path, default=Path('/source/patches'))
    parser.add_argument('--output', type=Path, default=Path('/output/twitch318-final-dependencies.zip'))
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; choose a fresh path: '+str(args.output))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bttv-final-deps-') as t:
        temp = Path(t)
        oldroot, oldhashes = decode(args.old, temp/'old', '31.2.0')
        newroot, newhashes = decode(args.new, temp/'new', '31.8.0')
        if oldhashes.get('base.apk') != OLD_EXPECTED['base.apk']:
            parser.error('Original 31.2.0 base.apk does not match PR #741 pin')
        old, new = choose(oldroot), choose(newroot)
        listed = {}
        for version, files in [('old', old), ('new', new)]:
            for rel, p in sorted(files.items()):
                s = p.read_text(encoding='utf8',errors='replace')
                listed[f'{version}/{rel}'] = signature_summary(s)
        patches = {}
        for rel in PATCHES:
            p = args.patches/rel
            if p.is_file():
                patches[rel] = p
        # Check for stale owner names in current bridge patches. This does
        # NOT imply all references are missing; types can coincidentally exist.
        stale_names = ['La120;', 'Lb6z;', 'Lcl2;', 'Ldl2;', 'Lr2k;',
                       'Lqw9;', 'Lfsi;', 'Lqz0;', 'Lr360;', 'Li0x;', 'Lzk2;']
        counts = {}
        for rel,p in patches.items():
            s = p.read_text(encoding='utf8',errors='replace')
            matches = {c:s.count(c) for c in stale_names if s.count(c)}
            if matches:counts[rel]=matches
        manifest = {
            'purpose':'Extract final dependency smali for 3 remaining patch failures and existing bridge type verification',
            'old_base_sha256':oldhashes.get('base.apk'),
            'new_base_sha256':newhashes.get('base.apk'),
            'old_class_count':len(old), 'new_class_count':len(new),
            'patches_included':list(sorted(patches)),
            'stale_name_appearances_in_patches':counts,
            'note':'Matching obfuscated names across APK versions are NOT semantic matches. Stale-name counts require manual type verification.',
        }
        with zipfile.ZipFile(args.output,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            z.writestr('manifest.json',json.dumps(manifest,indent=2))
            z.writestr('signatures.json',json.dumps(listed,indent=2))
            for version,files in [('old',old),('new',new)]:
                for rel,p in sorted(files.items()):z.write(p, f'{version}/{rel}')
            for rel,p in sorted(patches.items()):z.write(p, f'current-patches/{rel}')
        print('CREATED',args.output, f'old {len(old)}, new {len(new)} classes,',f'{args.output.stat().st_size/1048576:.2f} MiB',flush=True)

if __name__ == '__main__':
    main()
