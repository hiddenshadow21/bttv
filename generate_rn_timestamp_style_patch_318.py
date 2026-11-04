#!/usr/bin/env python3
"""Generate a guarded 31.8.0 smali patch to call RNTimestampStyle318.

Run in the existing BTTV Docker builder where collect_twitch_port_reference.decode
is available and the original Twitch 31.8.0 twitch.zip is mounted at /source/twitch.zip.
The generated patch targets the actual decoded DEX path, not an assumed index.
"""
from __future__ import annotations
import argparse
import difflib
import re
import subprocess
import tempfile
from pathlib import Path
from collect_twitch_port_reference import decode

HOOK = "    invoke-static {p0}, Lbttv/rn/RNTimestampStyle318;->style(Landroid/widget/TextView;)V\n"
METHOD = re.compile(r'(?m)^\.method\s+[^\n]*\bonDraw\(Landroid/graphics/Canvas;\)V\s*$')
CLASS = re.compile(r'(?m)^\.class\s+[^\n]*Lcom/facebook/react/views/text/ReactTextView;\s*$')
SUPER = re.compile(r'(?m)^\.super\s+(L[^\s]+;)\s*$')

def transform(src: str) -> str:
    if not CLASS.search(src):
        raise RuntimeError("Decoded class does not declare ReactTextView")
    if HOOK.strip() in src:
        raise RuntimeError("Already contains the timestamp hook; refusing duplicate")
    m = list(METHOD.finditer(src))
    if len(m) > 1:
        raise RuntimeError("Multiple onDraw methods; refusing ambiguous edit")
    if len(m) == 1:
        tail = src.find('\n.end method', m[0].end())
        if tail < 0:
            raise RuntimeError("Missing .end method for onDraw")
        body = src[m[0].end():tail]
        directive = re.search(r'(?m)^\s+\.(?:locals|registers)\s+\d+\s*$', body)
        if not directive:
            raise RuntimeError("onDraw has no register declaration")
        insertion = m[0].end() + directive.end()
        return src[:insertion] + '\n' + HOOK.rstrip('\n') + src[insertion:]
    superclass = SUPER.search(src)
    if not superclass:
        raise RuntimeError("Cannot determine direct superclass")
    base = superclass.group(1)
    if not (base.startswith('Landroidx/appcompat/widget/') or base.startswith('Landroid/widget/')):
        raise RuntimeError("Unexpected superclass: " + base)
    method = ("\n.method protected onDraw(Landroid/graphics/Canvas;)V\n"
              "    .locals 0\n" + HOOK +
              "    invoke-super {p0, p1}, " + base + "->onDraw(Landroid/graphics/Canvas;)V\n"
              "    return-void\n.end method\n")
    return src.rstrip('\n') + '\n' + method

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--new', default='/source/twitch.zip', type=Path)
    ap.add_argument('--output', default='/output/timestamp-style.patch', type=Path)
    args = ap.parse_args()
    if args.output.exists():
        ap.error('Output already exists; use a fresh output directory to prevent overwriting patches')
    with tempfile.TemporaryDirectory(prefix='bttv318-textstyle-') as d:
        root, _ = decode(args.new, Path(d) / 'decoded', '31.8.0')
        matches = [p for p in root.rglob('ReactTextView.smali')
                   if p.as_posix().endswith('/com/facebook/react/views/text/ReactTextView.smali')]
        if len(matches) != 1:
            raise SystemExit(f'Expected exactly one ReactTextView.smali, found {len(matches)}')
        target = matches[0]
        rel = target.relative_to(root).as_posix()
        before = target.read_text(encoding='utf-8')
        after = transform(before)
        changes = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                               fromfile='a/'+rel, tofile='b/'+rel, n=4))
        patch = 'diff --git a/'+rel+' b/'+rel+'\n'+changes
        # Verify generated patch against a clean Git index, independent of Dex layout.
        scratch = Path(d) / 'verify'
        f = scratch / rel
        f.parent.mkdir(parents=True)
        f.write_text(before, encoding='utf-8')
        subprocess.run(['git','init','-q'], cwd=scratch,check=True,stdout=subprocess.DEVNULL)
        subprocess.run(['git','add','--',rel],cwd=scratch,check=True,stdout=subprocess.DEVNULL)
        patch_tmp=Path(d)/'check.patch'
        patch_tmp.write_text(patch,encoding='utf-8')
        subprocess.run(['git','apply','--check',str(patch_tmp)],cwd=scratch,check=True)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(patch,encoding='utf-8',newline='\n')
        print(f'PASS: generated patch for {rel} ({len(patch)} bytes)')
        print('Hook: ReactTextView.onDraw -> bttv.rn.RNTimestampStyle318.style')
        print('NOTE: native render styling cannot move the timestamp ahead of separate badge views')

if __name__=='__main__': main()
