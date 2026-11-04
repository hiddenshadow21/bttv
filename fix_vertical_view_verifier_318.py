#!/usr/bin/env python3
"""Scoped, reversible repair of the Twitch 31.8.0 EmoteDetailsBridge VerifyError.

PR #741's patch contains THREE diff --git file sections, so hunk counting
must be confined to the EmoteDetailsBridge file section. The previous
installer incorrectly counted every hunk in the whole patch.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

PATCH = Path('patches/live/bttvcompat.EmoteDetailsBridge.smali.patch')
BRIDGE = 'smali_classes7/bttvcompat/EmoteDetailsBridge.smali'
METHODS = {
    'open': {
        'sig': 'open(Landroid/view/View;Ljava/lang/String;Ljava/lang/String;Z)V',
        'body': [
            '    .locals 0',
            '    # 31.8.0 verifier mitigation: disable incompatible legacy details dialog.',
            '    return-void',
        ],
    },
    'clear': {
        'sig': 'clear(Landroid/widget/ImageView;)V',
        'body': [
            '    .locals 1',
            '    if-eqz p0, :bttv318_clear_done',
            '    const/4 v0, 0x0',
            '    invoke-virtual {p0, v0}, Landroid/widget/ImageView;->setImageDrawable(Landroid/graphics/drawable/Drawable;)V',
            '    :bttv318_clear_done',
            '    return-void',
        ],
    },
}
DIFF_HEADER = re.compile(r'^diff --git a/(\S+) b/(\S+)$', re.M)
HUNK_HEADER = re.compile(r'^@@ -0,0 \+1,(\d+) @@[^\n]*$', re.M)


def repair(source: str):
    if '\r' in source:
        raise ValueError('CR line endings in patch: normalize this patch to LF before editing')
    diffs = list(DIFF_HEADER.finditer(source))
    matching = [i for i, m in enumerate(diffs) if m.group(1) == BRIDGE and m.group(2) == BRIDGE]
    if len(matching) != 1:
        raise ValueError(f'Expected exactly one diff section for {BRIDGE}; found {len(matching)}')
    idx = matching[0]
    start = diffs[idx].start()
    stop = diffs[idx + 1].start() if idx + 1 < len(diffs) else len(source)
    block = source[start:stop]
    head = block.split('@@', 1)[0]
    if 'new file mode 100644' not in head or '--- /dev/null\n' not in head:
        raise ValueError('Bridge is not a new-file patch; cannot use this new-file repair')
    hunks = list(HUNK_HEADER.finditer(block))
    if len(hunks) != 1 or len(re.findall(r'^@@ ', block, re.M)) != 1:
        raise ValueError('Expected exactly one new-file hunk inside the BRIDGE file section')
    hunk = hunks[0]
    hunk_body = block[hunk.end():]
    if not hunk_body.startswith('\n'):
        raise ValueError('Unexpected hunk formatting (no newline)')
    hunk_body = hunk_body[1:]
    lines = hunk_body.splitlines(keepends=True)
    if not lines or any(not line.startswith('+') for line in lines):
        raise ValueError('Bridge file section contains non-added lines')
    original_count = int(hunk.group(1))
    if original_count != len(lines):
        raise ValueError(f'Original bridge hunk line count mismatch: header={original_count}, actual={len(lines)}')

    modified = []
    # Locate independently before replacing. Never mix methods or sections.
    edits = []
    for name, cfg in METHODS.items():
        signature = cfg['sig']
        beginnings = [i for i, ln in enumerate(lines)
                      if ln.startswith('+.method ') and signature in ln]
        if len(beginnings) != 1:
            raise ValueError(f'Expected one {signature} declaration in BRIDGE; found {len(beginnings)}')
        first = beginnings[0]
        last = next((j for j in range(first + 1, len(lines))
                     if lines[j].rstrip('\n') == '+.end method'), None)
        if last is None:
            raise ValueError(f'Method {signature} lacks .end method')
        desired = [lines[first]] + ['+' + s + '\n' for s in cfg['body']] + ['+.end method\n']
        current = lines[first:last + 1]
        if current != desired:
            # Never replace an arbitrary incompatible method body that might be
            # independently customized/partially repaired. Known crash patterns
            # or previously issued no-op fixer only.
            current_text = ''.join(current)
            known_unsafe = ((name == 'open' and
                             'Landroidx/fragment/app/n;' in current_text and
                             'Landroid/app/Activity;' in current_text) or
                            (name == 'clear' and
                             'new-instance' in current_text and
                             'Lwte;' in current_text and 'Lkgl;' in current_text))
            previous_noop = (re.fullmatch(
                re.escape(lines[first]) + r'\+\s*\.locals 0\n\+\s*return-void\n\+\.end method\n?',
                current_text) is not None)
            if not known_unsafe and not previous_noop:
                raise ValueError(f'Unrecognized implementation of {signature}; refusing to overwrite it')
            edits.append((first, last + 1, desired, name))

    for first, after, desired, name in sorted(edits, reverse=True):
        lines[first:after] = desired
        modified.append(name)
    modified.reverse()
    body = ''.join(lines)
    new_count = len(lines)
    # Keep the other two PR #741 classes (and all other sections) byte-for-byte.
    block_new = (block[:hunk.start(1)] + str(new_count) +
                 block[hunk.end(1):hunk.end()] + '\n' + body)
    result = source[:start] + block_new + source[stop:]
    if result[0:start] != source[0:start] or result[len(source[:start]) + len(block_new):] != source[stop:]:
        raise AssertionError('Unexpected edit outside bridge block')
    return result, modified


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true', help='read-only compatibility check')
    mode.add_argument('--apply', action='store_true', help='back up and edit existing patch')
    p.add_argument('--root', type=Path, default=Path.cwd())
    args = p.parse_args()
    path = args.root / PATCH
    try:
        original = path.read_bytes()
        decoded = original.decode('utf-8')
        result, changed = repair(decoded)
        if args.check:
            print('PREFLIGHT PASS: target BRIDGE diff section validated')
            print('Methods needing repair:', ', '.join(changed) if changed else '(already repaired)')
            print('EmoteDetailsClick and EmoteDetailsSheet sections: preserved')
            return 0
        if not changed:
            print('ALREADY REPAIRED:', path)
            return 0
        backup_dir = args.root / 'dist' / 'twitch318-vertical-view-backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / ('EmoteDetailsBridge.smali.patch.' +
                               dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
        backup.write_bytes(original)
        path.write_bytes(result.encode('utf-8'))
        print('PATCHED:', path)
        print('REPAIRED:', ', '.join(changed))
        print('BACKUP:', backup)
        print('Note: legacy details popup disabled; RN emotes not modified')
        return 0
    except (ValueError, OSError, UnicodeError) as error:
        print('ERROR:', error, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
