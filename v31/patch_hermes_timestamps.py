#!/usr/bin/env python3
"""Enable Twitch 31.8.0's native timestamp *component* for live chat.

For the 31.8.0 Hermes v98 ChatMessageRowComponent (function 19420), the
showTimestamp prop defaults to false, and the JS renderer therefore suppresses
live timestamps. The component already renders TimestampPart ahead of badges.

Keep the original bytecode layout and registers: change exactly two operations:
    LoadConstFalse r22 -> LoadConstTrue r22
    Mov r22, r18       -> Mov r22, r22

Both new opcodes have identical sizes to the old ones. The unchanged
hideTimestamp prop still hides timestamps in contexts explicitly requesting it.
The Android layer controls presence of tmi-sent-ts on *new live IRC messages*,
which is the native timestamp's data source. Historical chat is untouched.
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile

FUNCTION_ID = 19420
EXPECTED = (
    '00d6  LoadConstFalse r7\n'
    '00d8  LoadConstFalse r22\n'
    '00da  JStrictEqual L225, r18, r2\n'
    '00de  Mov r22, r18\n'
    'L225:\n'
    '00e1  LoadConstFalse r50'
)
REPLACEMENT = (
    '00d6  LoadConstFalse r7\n'
    '00d8  LoadConstTrue r22\n'
    '00da  JStrictEqual L225, r18, r2\n'
    '00de  Mov r22, r22\n'
    'L225:\n'
    '00e1  LoadConstFalse r50'
)


def patch_hasm(source: str) -> str:
    normalized = source.replace('\r\n', '\n')
    if normalized.count(EXPECTED) != 1:
        raise ValueError('Unexpected ChatMessageRowComponent timestamp prologue; refusing patch')
    for required in ('"showTimestamp"', '"isHistorical"', '"tmiSentTs"', '"TimestampPart"'):
        if required not in normalized:
            raise ValueError('Missing expected renderer identifier: ' + required)
    result = normalized.replace(EXPECTED, REPLACEMENT, 1)
    # Only the two intended bytecode instructions can change.
    before = normalized.splitlines()
    after = result.splitlines()
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    if len(before) != len(after) or changed != [
        ('00d8  LoadConstFalse r22', '00d8  LoadConstTrue r22'),
        ('00de  Mov r22, r18', '00de  Mov r22, r22'),
    ]:
        raise ValueError('Timestamp patch changed more than the two approved instructions')
    return result


def run(*args):
    subprocess.run([str(s) for s in args], check=True)


def run_tool(tool: Path, bundle: Path):
    if not bundle.is_file() or bundle.stat().st_size < 1024:
        raise ValueError(f'Hermes bundle missing or empty: {bundle}')
    with tempfile.TemporaryDirectory(prefix='bttv-hbc-') as temp:
        temp = Path(temp)
        original = temp / 'original.hasm'
        patched = temp / 'patched.hasm'
        result = temp / 'patched.bundle'
        verification = temp / 'recovered.hasm'
        run(tool, 'emit-hasm', bundle, '--function', FUNCTION_ID, '-o', original)
        patched.write_text(patch_hasm(original.read_text(encoding='utf-8')), encoding='utf-8', newline='\n')
        run(tool, 'patch-function', bundle, '--function', FUNCTION_ID,
            '--hasm', patched, '-o', result)
        if not result.is_file() or result.stat().st_size != bundle.stat().st_size:
            raise ValueError('Patched modern Hermes function changed bundle size; refusing')
        run(tool, 'asm-check', result, '--function', FUNCTION_ID)
        run(tool, 'emit-hasm', result, '--function', FUNCTION_ID, '-o', verification)
        validated = verification.read_text(encoding='utf-8').replace('\r\n', '\n')
        # Assembler may canonicalize offsets but must preserve the intended
        # opcode pair and must remove the original live timestamp suppressor.
        if not re.search(r'LoadConstTrue r22\s*\n\w+\s+JStrictEqual .*?\n\w+\s+Mov r22, r22', validated):
            raise ValueError('Patched bytecode did not retain the native timestamp override')
        if '"TimestampPart"' not in validated:
            raise ValueError('TimestampPart disappeared during assembly')
        result.replace(bundle)
        print('Hermes v98: enabled native ChatMessageRowComponent timestamps (function 19420)')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--tool', type=Path, default=Path('hermes-decomp'))
    args = parser.parse_args()
    try:
        run_tool(args.tool, args.bundle)
    except (ValueError, subprocess.CalledProcessError, OSError) as exc:
        sys.exit(f'BTTV Hermes timestamp patch FAILED: {exc}')


if __name__ == '__main__':
    main()
