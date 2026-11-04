#!/usr/bin/env python3
"""Read-only check of diagnostic marker strings in an APK's DEX files."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

MARKERS = (
    'BTTV318Diag',
    'LiveEmoteBridge.rewrite entered',
    'LiveEmoteBridge.rewrite failed',
    'appendLegacy entered',
    'native BTTV row append failed',
    'SettingsActivity overflow fallback installed',
    'LiveEmotes.split entered',
    'Global catalog fetched',
)

def analyze(path):
    data = path.read_bytes()
    result = {'filename': path.name, 'sha256': hashlib.sha256(data).hexdigest().upper(), 'bytes': len(data)}
    try:
        with zipfile.ZipFile(path, 'r') as z:
            dexnames = [n for n in z.namelist() if re.fullmatch(r'classes\d*\.dex', n)]
            dexnames.sort(key=lambda n: 1 if n == 'classes.dex' else int(n[7:-4]))
            if not dexnames: raise ValueError('No classes*.dex found')
            result['dex_count'] = len(dexnames)
            bymarker = {m:[] for m in MARKERS}
            for dex in dexnames:
                payload = z.read(dex)
                for mark in MARKERS:
                    if mark.encode('ascii') in payload:
                        bymarker[mark].append(dex)
            result['markers'] = bymarker
    except (OSError, ValueError, zipfile.BadZipFile) as e:
        result['error'] = str(e)
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('apk', nargs='+', type=Path)
    p.add_argument('--json', dest='json_path', type=Path)
    a = p.parse_args()
    results=[]
    for path in a.apk:
        if not path.is_file():
            print('ERROR: not found: '+str(path), file=sys.stderr)
            return 2
        r=analyze(path)
        results.append(r)
        print('\nAPK:',path)
        print('SHA256:', r['sha256'])
        if 'error' in r:
            print('ERROR:',r['error']); continue
        print('DEX files:',r['dex_count'])
        for k,v in r['markers'].items():
            print(('FOUND  ' if v else 'ABSENT ')+k+(': '+', '.join(v) if v else ''))
        if not r['markers']['BTTV318Diag']:
            print('INTERPRETATION: diagnostic marker is absent. This APK does not contain the tested diagnostic smali log tag.')
        elif not r['markers']['LiveEmoteBridge.rewrite entered']:
            print('INTERPRETATION: diagnostic tag is present, but the emote-rewrite entry probe appears absent.')
        else:
            print('INTERPRETATION: diagnostic strings embedded. This does not prove their code paths execute.')
    if a.json_path:
        a.json_path.parent.mkdir(parents=True,exist_ok=True)
        a.json_path.write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    if len(results)==2 and all('error' not in r for r in results):
        print('\nCOMPARISON:', 'byte-identical' if results[0]['sha256']==results[1]['sha256'] else 'DIFFERENT FILES')
    return 1 if any('error' in r for r in results) else 0

if __name__ == '__main__':
    sys.exit(main())
