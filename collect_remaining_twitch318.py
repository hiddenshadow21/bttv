#!/usr/bin/env python3
"""Collect missing old/new dependency smali for the final BTTV 31.8.0 port.

Run from the repo root, inside the existing Linux Docker builder:

  docker compose run --rm --entrypoint python3 build \
    /source/collect_remaining_twitch318.py \
    --old /source/twitch-31.2.0.apkm \
    --new /source/twitch.zip \
    --output /output/twitch-318-remaining-context.zip

Requires collect_twitch_port_reference.py (from the previous step) in /source.
Never edits patches or builds a modified APK. Exports decoded smali, not APKs.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import tempfile
import zipfile
from collect_twitch_port_reference import decode, OLD_EXPECTED

REMAINING = (
    'cl2', 'f86', 'fbj', 'ffo', 'ilg', 'jc2', 'r2k', 'v46',
    'vw90', 'z89', 'zy_gif_modes', 'zz_emote_details',
)
# All these class names are *candidates*. Presence does not prove equivalence.
NAMES = {
    # Original targets and known new candidates.
    'cl2', 'f86', 'fbj', 'ffo', 'ilg', 'jc2', 'r2k', 'v46', 'vw90', 'z89',
    'va6', 'ic9', 'tij', 'lor', 'k7d', 'szs', 'cqo', 'je2', 'clj', 'h5g',
    'qw6', 'rvp', 'fv1', 'njj', 'xjj', 'pb6', 'pqf', 'r360',
    'cbl', 'i0z', 'xpo', 'tb1', 'jbp', 'xgv', 'rap', 'tfz', 'gam',
    'v0q', 'dos', 'lbj', 'qmj', 'd7c', 'fvv', 'ltz', 'd7m',
    # Concrete old/new type dependencies from patches and nearby code.
    'qf9', 'vb9', 'jd', 'hc9', 'm89', 'gd', 'g86', 'wa6', 'rsf', 'vqf',
    'qz0', 'pz0', 'fmp', 'y86', 'enj', 'sro', 't1a0', 'lka', 'qw9',
    'NativeSettingsBridge', 'NativePickerBridge', 'DeletedSpecialRows',
    'TwitchApplication', 'SettingsActivity',
    # Other strong/ambiguous candidate classes.
    'r4b0', 'fs0', 'zjb', 'x9r', 'mc00', 'nec', 'n79', 'pb9',
    'we0', 's340', 'oo4', 'lw00', 'jud', 'a7d', 'kr4',
}


def select_files(decoded: Path):
    selected = {}
    reasons = {}
    synthetic = []
    for path in decoded.rglob('*.smali'):
        rel = path.relative_to(decoded).as_posix()
        if not rel.startswith('smali'):
            continue
        if path.stem in NAMES:
            selected[rel] = path
            reasons[rel] = 'named target, mapping candidate, or type dependency'
            continue
        # The old v46 timestamp hook is an R8 synthetic Function1 with
        # EventDispatcher captured in a field. Its renamed equivalent may not
        # share a stable class name, so collect matching synthetics as leads.
        if path.stat().st_size > 50000:
            continue
        with path.open(encoding='utf-8', errors='replace') as f:
            head = ''.join(f.readline() for _ in range(75))
        if ('Ltv/twitch/android/core/mvp/viewdelegate/EventDispatcher;' in head
                and '.implements Lkotlin/jvm/functions/Function1;' in head):
            synthetic.append((rel, path))
    for rel, path in synthetic[:60]:
        selected[rel] = path
        reasons[rel] = 'timestamp Function1 synthetic candidate (needs verification)'
    return selected, reasons, len(synthetic)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--old', type=Path, default=Path('/source/twitch-31.2.0.apkm'))
    p.add_argument('--new', type=Path, default=Path('/source/twitch.zip'))
    p.add_argument('--output', type=Path, default=Path('/output/twitch-318-remaining-context.zip'))
    p.add_argument('--patches', type=Path, default=Path('/source/patches'))
    args = p.parse_args()
    if args.output.exists():
        p.error(f'Refusing to overwrite existing file: {args.output}')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bttv-remaining-') as temp:
        temp = Path(temp)
        oldroot, oldhashes = decode(args.old, temp/'old', '31.2.0')
        newroot, newhashes = decode(args.new, temp/'new', '31.8.0')
        if oldhashes.get('base.apk') != OLD_EXPECTED['base.apk']:
            p.error('Old base.apk hash does not match original PR #741 pin; do not use for class mappings')
        o, oreasons, osyn = select_files(oldroot)
        n, nreasons, nsyn = select_files(newroot)
        report = {
            'old_base_sha256': oldhashes.get('base.apk'),
            'new_apk_hashes': newhashes,
            'old_classes': dict(sorted(oreasons.items())),
            'new_classes': dict(sorted(nreasons.items())),
            'timestamp_synthetic_candidates': {'old': osyn, 'new': nsyn},
            'note': ('Old and new files are unmodified decoded APK smali. '
                     'No automatic class mapping is implied by the filenames. '
                     'Patches are from the current checkout and may include your manual edits.'),
        }
        with zipfile.ZipFile(args.output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            z.writestr('manifest.json', json.dumps(report, indent=2))
            for version, files in [('old', o), ('new', n)]:
                for rel, path in sorted(files.items()):
                    z.write(path, version+'/'+rel)
            for name in REMAINING:
                for suffix in ('.smali.patch', '.patch'):
                    patch = args.patches/'live'/(name+suffix)
                    if patch.is_file():
                        z.write(patch, 'current-patches/live/'+patch.name)
            app = args.patches/'tv.twitch.android.app.consumer.TwitchApplication.smali.patch'
            if app.is_file():
                z.write(app, 'current-patches/'+app.name)
        print(f'Created {args.output} ({len(o)} old and {len(n)} new classes; '
              f'{args.output.stat().st_size/1048576:.2f} MiB)', flush=True)


if __name__ == '__main__':
    main()
