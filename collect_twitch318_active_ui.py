#!/usr/bin/env python3
"""Collect bounded React Native hook targets and settings/version evidence from Twitch 31.8.0.

Uses the earlier decode helper; read-only. Run inside the user's builder container.
No app data or credentials are collected. Never outputs an APK.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
import tempfile
import zipfile
from collect_twitch_port_reference import decode

HINTS = {
    'websocketMessage': 14,
    'WebSocketModule': 6,
    'EmotePickerTray': 16,
    'ChatEmoteSets': 12,
    'EmoteCard': 9,
    'MainSettingsFragmentV2': 18,
    'ChatEmoteSets': 20,
    'EmotePickerTray': 20,
    'onWebSocketText': 18,
    'setSource': 3,
    'EmoteSpanTarget': 18,
    'EmoteImageSpan': 18,
    'EmoteImageLoader': 18,
    'sendRequest': 3,
    'NetworkingModule': 4,
    'ReactImageView': 4,
    'ImageSource': 3,
    'ReactImageManager': 4,
    'EmoteImageLoader': 9,
    'TwitchEmoteInputView': 10,
    'SurfaceMountingManager': 4,
    'RNEmote': 4,
    'versionName': 2,
    'twitch_version': 3,
}
PREFIXES = (
    'com/facebook/react/modules/websocket/',
    'com/facebook/react/modules/network/',
    'com/facebook/react/fabric/mounting/',
    'com/twitchrn/emoteinput/',
    'tv/twitch/android/settings/',
)
BASENAMES = {'NetworkingModule.smali','WebSocketModule.smali','SurfaceMountingManager.smali',
             'MainSettingsFragmentV2.smali','EmotePickerTray.smali','ReactImageView.smali',
             'EmoteSpanTarget.smali','EmoteImageLoader.smali','EmoteImageSpan.smali',
             'ReactImageManager.smali','ImageSource.smali'}
VERSION_RE = re.compile(r'(?i)(?:twitch.{0,60}31\.8|31\.8.{0,50}twitch|app.{0,25}version|version.{0,25}name|settings_logout_footer|bttv)', re.I)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--new',type=Path,default=Path('/source/twitch.zip'))
    p.add_argument('--output',type=Path,default=Path('/output/twitch318-active-ui-context.zip'))
    p.add_argument('--source',type=Path,default=Path('/source'))
    a=p.parse_args()
    if a.output.exists(): p.error('Output exists; select a fresh output directory (no overwrite).')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='twitch318-active-ui-') as temp:
        root, hashes=decode(a.new,Path(temp)/'current','31.8.0')
        candidates=[]
        for path in root.rglob('*.smali'):
            rel=path.relative_to(root).as_posix()
            if not rel.startswith('smali'): continue
            classrel=rel.split('/',1)[-1]
            exact=(classrel.startswith(PREFIXES) or path.name in BASENAMES)
            data=None
            size=path.stat().st_size
            if not exact and size>400_000: continue
            data=path.read_bytes()
            # Only inspect string literals and stable source metadata, not arbitrary byte matches.
            text=data.decode('utf-8','replace')
            score=sum(weight for hint,weight in HINTS.items() if hint in text)
            if exact: score+=25
            if score>=12:
                candidates.append((score,size,rel,path))
        # Prefer named RN classes over packages with many unrelated nested classes.
        # The previous alphabetical cap could omit WebSocketModule / NetworkingModule.
        exact=[x for x in candidates if x[2].split('/',1)[-1].startswith(PREFIXES) or Path(x[2]).name in BASENAMES]
        exact_paths={x[2] for x in exact}
        other=[x for x in candidates if x[2] not in exact_paths]
        chosen=(sorted(exact,key=lambda x:(-x[0],x[1],x[2]))[:105]
                +sorted(other,key=lambda x:(-x[0],x[1],x[2]))[:100])
        unique={x[2]:x for x in chosen}
        version_hits=[]
        for path in root.rglob('*.xml'):
            rel=path.relative_to(root).as_posix()
            if not rel.startswith('res/') or path.stat().st_size>1_500_000:continue
            content=path.read_text(encoding='utf-8',errors='replace')
            hits=[]
            for idx,line in enumerate(content.splitlines(),1):
                if VERSION_RE.search(line) and len(line)<1000:
                    hits.append({'line':idx,'text':line.strip()[:400]})
                if len(hits)==30:break
            if hits:
                version_hits.append({'file':rel,'matches':hits})
        report={'source_apk_sha256':hashes,'selected_smali_count':len(unique),
                'smali_candidates':[{'path':k,'score':v[0],'bytes':v[1]} for k,v in sorted(unique.items())],
                'resource_matches':len(version_hits),
                'note':'Candidates are anchors only. Obfuscated name matches are NOT semantic proof; PR 740 is for 31.5.2 and must NOT be applied directly to 31.8.0.'}
        with zipfile.ZipFile(a.output,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            z.writestr('manifest.json',json.dumps(report,indent=2))
            z.writestr('resources/version-string-candidates.json',json.dumps(version_hits,indent=2,ensure_ascii=False))
            for rel,(_,size,_,path) in sorted(unique.items()):
                if size<=500_000:z.write(path,'decoded/'+rel)
            for sourcefile in [
                 'mod/app/src/main/java/bttv/settings/SettingsNavigation.java',
                 'mod/app/src/main/java/bttv/emote/LiveEmotes.java',
                 'mod/app/src/main/java/bttv/emote/LiveEmoteGlobals.java',
                 'patches/live/zzzz_bttv_runtime_diagnostics.patch',
                 'patches/live/z86.smali.patch',
                 'patches/live/ffo.smali.patch',
                 'patches/live/r2k.smali.patch',
                 'patches/settings/tv.twitch.android.settings.SettingsActivity.smali.patch',
            ]:
                path=a.source/sourcefile
                if path.is_file() and path.stat().st_size<200_000:z.write(path,'checkout/'+sourcefile)
        print(f'Created {a.output} ({len(unique)} smali, {len(version_hits)} XML files with version/name leads, {a.output.stat().st_size/1048576:.2f} MiB)')
if __name__=='__main__': main()
