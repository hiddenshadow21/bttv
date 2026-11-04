#!/usr/bin/env python3
"""Collect a focused old/new smali reference pack for BTTV PR #741.

Run in the existing builder container (read-only /source, writable /output):

    docker compose run --rm --entrypoint python3 build \
      /source/collect_twitch_port_reference.py \
      --old /source/twitch-31.2.0.apkm --new /source/twitch.zip \
      --output /output/twitch-port-reference.zip \
      --audit-json /source/dist/docker-patch-audit/patch-audit.json

Does not modify the checkout, APKs, or patches. No BTTV APK is built.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

OLD_EXPECTED = {
    'base.apk': '9C1EAC898EFFEC57B7DBBCC18BB959A48F8442C62550AEFC0B7053904DF40803',
    'split_config.arm64_v8a.apk': 'EFF111BE0A66EAC64F374E27A81AA34D320BC888C4E8734C806FAC4D941F7D23',
    'split_config.armeabi_v7a.apk': 'F7105074B4ED6763497691C9F0098D2EF35A076C921FF5EA10A467DF9BFFC945',
    'split_config.xxhdpi.apk': '85B5584715794D38CF95910F3DC809B04693D1E69ECBC014202A50AD59AF08A1',
    'split_config.xxxhdpi.apk': '3472B872C724231681E12FA21A4F180B530693B931C6B50272298E6C8DBD54C8',
}
SELECT = list(OLD_EXPECTED)
# A valid 31.2.0 ARM64-only bundle contains 4 of these 5 APKs.
REQUIRED = {'base.apk', 'split_config.arm64_v8a.apk'}
STABLE = ('Landroid/', 'Landroidx/', 'Ltv/twitch/', 'Lcom/facebook/', 'Lcom/google/',
          'Lcom/amazonaws/', 'Lcom/amazon/', 'Lkotlin/', 'Lorg/', 'Ljava/', 'Lio/')
RE_CLASS = re.compile(r'^\.class\s+.*?\s+(L[^;\s]+;)', re.M)
RE_SUPER = re.compile(r'^\.super\s+(L[^;\s]+;)', re.M)
RE_METHOD = re.compile(r'^\.method\b', re.M)
RE_FIELD = re.compile(r'^\.field\b', re.M)
RE_API = re.compile(r'(L[^;\s]+;->[^\s(]+)\(')
RE_LITERAL = re.compile(r'\bconst-string(?:/jumbo)?\s+[^,]+,\s*"([^"\r\n]+)"')
RE_PATCH = re.compile(r'^--- a/([^\t\r\n]+)$', re.M)


def sha(data):
    return hashlib.sha256(data).hexdigest().upper()


def choose_apks(source, destination, label):
    destination.mkdir(parents=True)
    if source.is_dir():
        present = {p.name for p in source.iterdir() if p.is_file() and p.suffix.lower() == '.apk'}
        def read(name): return (source / name).read_bytes()
    else:
        with zipfile.ZipFile(source) as bundle:
            present = {n for n in bundle.namelist() if n.endswith('.apk') and '/' not in n}
        def read(name):
            with zipfile.ZipFile(source) as bundle:
                return bundle.read(name)
    missing = REQUIRED - present
    if missing:
        raise ValueError(f'{label}: missing required root-level APK entries: {sorted(missing)}; found: {sorted(present)}')
    selected = sorted(present.intersection(SELECT))
    if not set(selected).intersection({'split_config.xxhdpi.apk', 'split_config.xxxhdpi.apk'}):
        raise ValueError(f'{label}: missing xxhdpi/xxxhdpi density split; supply a 480/640 dpi bundle')
    hashes = {}
    for name in selected:
        data = read(name)
        # Do not extract from an untrusted archive without checking the inner ZIP structure.
        with zipfile.ZipFile(io.BytesIO(data)) as apk:
            if apk.testzip() is not None:
                raise ValueError(f'{label}: corrupted {name}')
        (destination / name).write_bytes(data)
        hashes[name] = sha(data)
    return hashes


def run_logged(cmd, log):
    print('  ' + ' '.join(map(str, cmd[:5])) + ' ...', flush=True)
    with log.open('wb') as out:
        result = subprocess.run(cmd, stdout=out, stderr=subprocess.STDOUT)
    if result.returncode:
        tail = log.read_text(encoding='utf-8', errors='replace')[-4500:]
        raise RuntimeError(f'Command failed ({result.returncode}): {cmd}\nLog tail:\n{tail}')


def decode(input_path, root, label):
    apks = root / 'apks'
    hashes = choose_apks(input_path, apks, label)
    print(f'[{label}] selected {len(hashes)} APK components', flush=True)
    # The normal PR #741 pipeline merges APK splits and then decodes with apktool 2.9.3.
    merged = root / 'merged.apk'
    run_logged(['java', '-Xmx6g', '-jar', os.environ.get('APKEDITOR_PATH', '/opt/APKEditor-1.4.9.jar'),
                'm', '-i', str(apks), '-o', str(merged)], root / 'apkeditor.log')
    target = root / 'decoded'
    run_logged(['java', '-Xmx6g', '-jar', os.environ.get('APKTOOL_PATH', '/opt/apktool_2.9.3.jar'),
                'd', str(merged), '-o', str(target)], root / 'apktool.log')
    return target, hashes


def parse_patch_targets(patch_root, audit_json):
    if audit_json and audit_json.is_file():
        entries = json.loads(audit_json.read_text(encoding='utf-8'))['results']
        names = [e['patch'] for e in entries if e['status'] == 'FAIL']
    else:
        names = [p.relative_to(patch_root).as_posix() for p in sorted(patch_root.rglob('*.patch'))]
    names = list(dict.fromkeys(names))
    patch_by_file = defaultdict(set)
    for name in names:
        patch = patch_root / name
        if not patch.is_file():
            raise FileNotFoundError(f'Patch missing: {patch}')
        for path in RE_PATCH.findall(patch.read_text(encoding='utf-8')):
            if path.endswith('.smali'):
                patch_by_file[Path(path).name].add(name)
    return names, patch_by_file


def smali_index(root):
    index = defaultdict(list)
    for path in root.rglob('*.smali'):
        if path.parent == root:
            continue
        if not path.relative_to(root).parts[0].startswith('smali'):
            continue
        index[path.name].append(path)
    return index


def metadata(path, root):
    data = path.read_text(encoding='utf-8', errors='replace')
    class_match = RE_CLASS.search(data)
    superclass = RE_SUPER.search(data)
    apis = {ref for ref in RE_API.findall(data) if ref.startswith(STABLE)}
    strings = {s[:180] for s in RE_LITERAL.findall(data) if len(s) >= 7}
    # Stable API references and literal strings are useful R8 mapping anchors.
    tokens = {'api:' + x for x in apis} | {'str:' + x for x in strings}
    return {
        'path': path.relative_to(root).as_posix(),
        'class': class_match.group(1) if class_match else '',
        'super': superclass.group(1) if superclass else '',
        'methods': len(RE_METHOD.findall(data)),
        'fields': len(RE_FIELD.findall(data)),
        'api': sorted(apis)[:80],
        'strings': sorted(strings)[:80],
        '_tokens': tokens,
    }


def candidate_map(old_rows, new_rows, old_targets):
    inv = defaultdict(list)
    df = Counter()
    for i, info in enumerate(new_rows):
        for token in info['_tokens']:
            inv[token].append(i)
            df[token] += 1
    total = max(2, len(new_rows))
    results = []
    for old in old_rows:
        if Path(old['path']).name not in old_targets:
            continue
        scores = Counter()
        shared = Counter()
        for token in old['_tokens']:
            # Ignore extremely common tokens that overwhelm the candidate list.
            freq = df[token]
            if freq == 0 or freq > max(50, total // 10):
                continue
            weight = math.log(1 + total / freq) * (2.5 if token.startswith('str:') else 1)
            for i in inv[token]:
                scores[i] += weight
                shared[i] += 1
        matches = []
        for i, score in scores.most_common(12):
            # Score purely by shared stable APIs / string literals, never by obfuscated filename.
            if shared[i] < 2 and not any(
                tok.startswith('str:') and i in inv[tok] and df[tok] <= 3
                for tok in old['_tokens']
            ):
                continue
            matches.append({'path': new_rows[i]['path'], 'class': new_rows[i]['class'],
                            'score': round(score, 2), 'shared_anchors': shared[i]})
        results.append({'old': old['path'], 'candidates': matches[:8]})
    return results


def public_row(row):
    return {k: v for k, v in row.items() if not k.startswith('_')}


def write_zip(outpath, oldroot, newroot, oldidx, newidx, patchroot, names, targets, oldrows, newrows, maps, hashes):
    if outpath.exists():
        raise FileExistsError(f'Won\'t overwrite: {outpath}')
    outpath.parent.mkdir(parents=True, exist_ok=True)
    reports = {
        'README.txt': (
            'BTTV 31.2.0 -> Twitch 31.8.0 diagnostic reference.\n'
            'Only patches selected by the audit (if provided) are included.\n'
            'old/ and new/ are UNMODIFIED decoded smali files, not patched classes.\n'
            'Same short class names across versions do NOT imply equivalent behavior.\n'
            'mapping-candidates.json contains heuristic leads, not verified equivalents.\n'
            'Check original PR pinned base.apk hash in hashes.json before relying on old references.\n'
        ),
        'hashes.json': json.dumps(hashes, indent=2),
        'patch-targets.json': json.dumps({n: sorted(p) for n,p in targets.items()}, indent=2),
        'old-smali-index.jsonl': '\n'.join(json.dumps(public_row(r), ensure_ascii=False) for r in oldrows),
        'new-smali-index.jsonl': '\n'.join(json.dumps(public_row(r), ensure_ascii=False) for r in newrows),
        'mapping-candidates.json': json.dumps(maps, indent=2, ensure_ascii=False),
    }
    with zipfile.ZipFile(outpath, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, data in reports.items():
            z.writestr(name, data)
        for patch in names:
            z.write(patchroot / patch, 'patches/' + patch)
        # Capture likely NEW classes even when R8 renamed them to a different basename.
        candidate_paths = {c['path'] for entry in maps for c in entry['candidates'][:4]}
        for rel in sorted(candidate_paths):
            file = newroot / rel
            if file.is_file():
                z.write(file, 'new-candidates/' + rel)
        for version, root, index in [('old', oldroot, oldidx), ('new', newroot, newidx)]:
            for filename in sorted(targets):
                for file in index.get(filename, []):
                    z.write(file, version + '/' + file.relative_to(root).as_posix())
            manifest = root / 'AndroidManifest.xml'
            if manifest.is_file():
                z.write(manifest, version + '/AndroidManifest.xml')
    print(f'Created: {outpath} ({outpath.stat().st_size / 1024 / 1024:.1f} MiB)', flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--old', required=True, type=Path, help='31.2.0 APKM/ZIP with root-level APK entries, or extracted directory')
    p.add_argument('--new', required=True, type=Path, help='31.8.0 validated twitch.zip, or APKM/ZIP')
    p.add_argument('--output', required=True, type=Path, help='New ZIP in writable /output')
    p.add_argument('--audit-json', type=Path, help='Optional previous patch-audit.json; only failed patches are collected')
    p.add_argument('--patches', type=Path, default=Path('/source/patches'))
    args = p.parse_args()
    names, targets = parse_patch_targets(args.patches, args.audit_json)
    if not targets:
        raise ValueError('No smali targets found in patches')
    print(f'Collecting {len(targets)} smali filenames from {len(names)} patches', flush=True)
    with tempfile.TemporaryDirectory(prefix='bttv-port-', dir='/tmp') as temp:
        temp = Path(temp)
        oldroot, oldhash = decode(args.old, temp / 'old', '31.2.0')
        newroot, newhash = decode(args.new, temp / 'new', '31.8.0')
        oldidx = smali_index(oldroot)
        newidx = smali_index(newroot)
        print('Indexing decoded methods and stable anchors ...', flush=True)
        oldrows = [metadata(path, oldroot) for filename, paths in oldidx.items()
                   if filename in targets for path in paths]
        newrows = [metadata(path, newroot) for paths in newidx.values() for path in paths]
        maps = candidate_map(oldrows, newrows, targets)
        hashes = {'31.2.0': {'actual': oldhash,
                             'matches_original_PR_base': oldhash.get('base.apk') == OLD_EXPECTED['base.apk'],
                             'mismatches_against_PR_pin': {k: {'expected': OLD_EXPECTED[k], 'actual': v}
                                 for k,v in oldhash.items() if v != OLD_EXPECTED[k]}},
                  '31.8.0': {'actual': newhash}}
        if not hashes['31.2.0']['matches_original_PR_base']:
            print('WARNING: 31.2.0 base.apk hash does NOT match PR #741 pinned base.', flush=True)
            print('The old reference may not exactly correspond to the original smali patches.', flush=True)
        write_zip(args.output, oldroot, newroot, oldidx, newidx, args.patches,
                  names, targets, oldrows, newrows, maps, hashes)


if __name__ == '__main__':
    main()
