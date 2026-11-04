#!/usr/bin/env python3
"""Read-only mapper for React Native text renderers in Twitch 31.8.0.

Decodes the APKM through the repository's existing pinned decode helper, then
collects React Native text managers, their concrete view classes and ancestors.
It does NOT write patches, alter the source tree, or invoke the APK builder.
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

from collect_twitch_port_reference import decode

CLASS_RE = re.compile(r'(?m)^\.class\s+[^\n]*?\s+(L[^\s;]+;)\s*$')
SUPER_RE = re.compile(r'(?m)^\.super\s+(L[^\s;]+;)\s*$')
METHOD_RE = re.compile(r'(?ms)^\.method[^\n]*\n.*?^\.end method\s*$')
NEW_RE = re.compile(r'\bnew-instance\s+[vp]\d+,\s+(L[^;\s]+;)')
TYPE_RE = re.compile(r'L(?:[A-Za-z0-9_$/]+);')
RET_RE = re.compile(r'\)(L[^;\s]+;)')

MANAGER_NAMES = (
    'ReactTextViewManager.smali',
    'PreparedLayoutTextViewManager.smali',
    'SelectableTextViewManager.smali',
    'ReactTextInputManager.smali',
)


def descriptor_path(desc: str) -> str:
    return desc.removeprefix('L').removesuffix(';') + '.smali'


def code_text(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='replace')


def find_class_paths(root: Path, desc: str) -> list[Path]:
    relative = descriptor_path(desc)
    return sorted(p for p in root.glob('smali*/' + relative) if p.is_file())


def record(root: Path, collected: set[Path], path: Path, depths: int = 4) -> list[dict]:
    chain = []
    seen = set()
    for _ in range(depths + 1):
        if not path.is_file() or path in seen:
            break
        seen.add(path)
        collected.add(path)
        data = code_text(path)
        cl = CLASS_RE.search(data)
        parent = SUPER_RE.search(data)
        chain.append({
            'file': path.relative_to(root).as_posix(),
            'class': cl.group(1) if cl else None,
            'super': parent.group(1) if parent else None,
            'defines_onDraw': bool(re.search(r'^\.method[^\n]*\bonDraw\(Landroid/graphics/Canvas;\)V', data, re.M)),
            'text_view_calls': data.count('Landroid/widget/TextView;'),
            'setText_mentions': len(re.findall(r'->setText\(', data)),
        })
        if not parent or not parent.group(1).startswith('L'):
            break
        descendants = find_class_paths(root, parent.group(1))
        if len(descendants) != 1:
            break
        path = descendants[0]
    return chain


def collect(root: Path):
    files: set[Path] = set()
    info = {'version': '31.8.0', 'managers': [], 'text_view_candidates': [], 'source_inventory': {}, 'notes': []}
    folders = list(root.glob('smali*/com/facebook/react/views/text'))
    for folder in folders:
        for item in folder.glob('*.smali'):
            # Entire text-view package is useful for resolving factory delegates and text spans.
            files.add(item)
    info['source_inventory']['react_text_smali_count'] = sum(len(list(folder.glob('*.smali'))) for folder in folders)
    checked_candidates: set[Path] = set()
    for name in MANAGER_NAMES:
        matches = sorted(root.glob('smali*/com/facebook/react/views/**/' + name))
        for path in matches:
            if not path.is_file():
                continue
            files.add(path)
            src = code_text(path)
            spec = {'name': name, 'file': path.relative_to(root).as_posix(), 'factories': []}
            for block in METHOD_RE.findall(src):
                header = block.split('\n', 1)[0].strip()
                if not any(term in header for term in ('createViewInstance', 'createShadowNodeInstance', 'prepareLayout', 'createView')):
                    continue
                new = list(dict.fromkeys(NEW_RE.findall(block)))
                types = list(dict.fromkeys(TYPE_RE.findall(block)))
                ret = RET_RE.search(header)
                relevant = []
                for d in ([ret.group(1)] if ret else []) + new + types:
                    if d and (d.startswith('Lcom/facebook/react/views/text/') or (d in new and not d.startswith('Ljava/'))):
                        if d not in relevant:
                            relevant.append(d)
                factory = {'signature': header, 'new_instances': new, 'return_type': ret.group(1) if ret else None, 'resolved_types': []}
                for desc in relevant[:25]:
                    paths = find_class_paths(root, desc)
                    candidate = {'descriptor': desc, 'files': [p.relative_to(root).as_posix() for p in paths]}
                    if len(paths) == 1:
                        candidate['ancestry'] = record(root, files, paths[0])
                        if paths[0] not in checked_candidates and (desc in new or desc == factory['return_type']):
                            info['text_view_candidates'].append({'origin': name, **candidate})
                            checked_candidates.add(paths[0])
                    factory['resolved_types'].append(candidate)
                spec['factories'].append(factory)
            info['managers'].append(spec)
    info['source_inventory']['manager_files'] = len(info['managers'])
    info['source_inventory']['total_smali_collected'] = len(files)
    if not info['managers']:
        info['notes'].append('No un-obfuscated RN text manager classes found; inspect the React Native package index and renamed managers.')
    if not info['text_view_candidates']:
        info['notes'].append('No concrete text view factory class was resolved. Collected manager classes may still reveal delegates.')
    info['notes'].append('This mapping cannot establish whether the chat-row timestamp is a separate JS/Fabric text node; no patch is generated.')
    return info, files


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--new', type=Path, default=Path('/source/twitch.zip'))
    ap.add_argument('--output', type=Path, default=Path('/output/twitch318-rn-text-renderer-map.zip'))
    args = ap.parse_args()
    if args.output.exists():
        ap.error('Output already exists; choose a new output directory to avoid stale evidence')
    with tempfile.TemporaryDirectory(prefix='bttv318-text-map-') as temp:
        root, _ = decode(args.new, Path(temp) / 'decoded', '31.8.0')
        info, files = collect(root)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
            bundle.writestr('text-renderer-report.json', json.dumps(info, indent=2) + '\n')
            bundle.writestr('README.txt',
                'Read-only Twitch 31.8.0 React Native text renderer mapping.\n'
                'The original script assumed a file literally named ReactTextView.smali.\n'
                'This archive contains view manager factory methods, view classes and ancestors.\n'
                'No patches were generated or applied.\n'
                'Loaded-history timestamp placement is likely controlled by a React Native chat-row layout.\n')
            for path in sorted(files):
                bundle.write(path, 'decoded/' + path.relative_to(root).as_posix())
        print(f'Created {args.output} with {len(files)} smali files')
        print('React Native text manager files:', info['source_inventory']['manager_files'])
        print('Factory view candidates:', len(info['text_view_candidates']))
        for x in info['text_view_candidates'][:12]:
            ancestry = x.get('ancestry', [])
            chain = ' -> '.join([t.get('class') or '?' for t in ancestry])
            print(' ', x['origin'], chain)
        print('READ-ONLY: no repository patches or APK files modified')

if __name__ == '__main__':
    main()
