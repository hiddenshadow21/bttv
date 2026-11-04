#!/usr/bin/env python3
"""Safely add missing Java diagnostics without touching the already-tracked smali probe.

Usage (from repo root):
    python repair_twitch318_java_diagnostics.py --check
    python repair_twitch318_java_diagnostics.py --apply

Requires install_twitch318_runtime_diagnostics.py (from the earlier kit) alongside
this script. Imports the EXACT original diagnostic transformations instead of
maintaining a competing implementation. Does not modify Git history.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

SOURCES = {
    'mod/app/src/main/java/bttv/settings/SettingsNavigation.java': b'SettingsActivity overflow fallback installed',
    'mod/app/src/main/java/bttv/emote/LiveEmotes.java': b'LiveEmotes.split entered',
    'mod/app/src/main/java/bttv/emote/LiveEmoteGlobals.java': b'Global catalog fetched',
}
PROBE = 'patches/live/zzzz_bttv_runtime_diagnostics.patch'
INSTALLER = 'install_twitch318_runtime_diagnostics.py'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def transformations(root: Path):
    src = root / INSTALLER
    if not src.is_file():
        raise RuntimeError(f'Missing {src}; extract twitch318-runtime-diagnostics-repair.zip into repo root.')
    spec = importlib.util.spec_from_file_location('twitch318_original_installer', src)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Cannot load original diagnostic installer {src}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    editors = getattr(module, 'EDITORS', None)
    if not isinstance(editors, dict) or not all(x in editors for x in SOURCES):
        raise RuntimeError('Original diagnostic installer is missing the three expected Java editors.')
    return editors


def prepare(root: Path):
    probe = root / PROBE
    if not probe.is_file() or b'BTTV318Diag' not in probe.read_bytes():
        raise RuntimeError(f'Missing diagnostic smali patch with BTTV318Diag marker: {PROBE}')
    editors = transformations(root)
    proposed = {}
    for rel, expected in SOURCES.items():
        path = root / rel
        if not path.is_file():
            raise RuntimeError(f'Missing Java source: {rel}')
        raw = path.read_bytes()
        if b'\r\n' in raw:
            raise RuntimeError(f'{rel}: CRLF line endings; refusing to rewrite automatically.')
        if expected in raw:
            print('ALREADY INSTRUMENTED:', rel)
            continue
        try:
            changed = editors[rel](raw.decode('utf-8')).encode('utf-8')
        except (UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError(f'{rel}: original diagnostic edit does not match your source: {exc}') from exc
        if expected not in changed or b'BTTV318Diag' not in changed or changed == raw:
            raise RuntimeError(f'{rel}: diagnostic editor did not produce the expected markers')
        proposed[rel] = (raw, changed)
        print('READY TO REPAIR:', rel)
    return proposed


def apply(root: Path, proposed: dict):
    if not proposed:
        print('No Java edits required.')
        return
    # Persist complete originals BEFORE touching any source file.
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    backup = root / 'dist' / f'twitch318-java-diag-backup-{timestamp}'
    backup.mkdir(parents=True, exist_ok=False)
    manifest = {}
    for rel, (before, after) in proposed.items():
        target = backup / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(before)
        manifest[rel] = {'original_sha256': digest(before), 'repaired_sha256': digest(after)}
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    edited = []
    try:
        for rel, (before, after) in proposed.items():
            path = root / rel
            if path.read_bytes() != before:
                raise RuntimeError(f'{rel}: source changed since dry-run; aborting')
            tmp = path.with_name(path.name + '.bttv318-diag-tmp')
            try:
                tmp.write_bytes(after)
                os.replace(tmp, path)
            finally:
                if tmp.exists():
                    tmp.unlink()
            edited.append(rel)
    except BaseException:
        for rel in edited:
            (root / rel).write_bytes(proposed[rel][0])
        print('A write failed; modified Java files were rolled back.', file=sys.stderr)
        raise
    print(f'REPAIRED {len(edited)} Java files')
    print('Original Java files backed up at:', backup)
    print('Next: python twitch318_diagnostics_preflight.py')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true', help='Validate exact anchors, without changes')
    mode.add_argument('--apply', action='store_true', help='Back up and edit only missing Java diagnostics')
    p.add_argument('--root', type=Path, default=Path('.'))
    a = p.parse_args()
    root = a.root.resolve()
    try:
        proposed = prepare(root)
        if a.apply:
            apply(root, proposed)
        else:
            print(f'DRY RUN: {len(proposed)} Java file(s) need diagnostics. No files modified.')
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
