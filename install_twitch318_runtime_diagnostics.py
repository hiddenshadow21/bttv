#!/usr/bin/env python3
"""Install/revert a temporary BTTV 31.8.0 runtime probe; never modify production patches.

Run from the root of the local BTTV checkout. The additional late-stage .patch file
needs `git add` so build_production.py's tracked-file staging includes it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys


def sha(data):
    return hashlib.sha256(data).hexdigest()


def replace_once(source, before, after, label):
    if source.count(before) != 1:
        raise ValueError(f"{label}: expected anchor exactly once, found {source.count(before)}")
    return source.replace(before, after, 1)


def edit_nav(text):
    old = '''    public static void install(final Activity activity, Menu menu) {
        // Compatibility entry point for the existing settings-Activity patch.
        // The native main Settings row is now the sole BTTV entry. Do not add
        // or remove any native toolbar items here.
    }'''
    new = '''    public static void install(final Activity activity, Menu menu) {
        // BTTV 31.8.0 diagnostic fallback for the renamed settings navigation.
        // This only adds an overflow item on a SettingsActivity that calls install().
        if (activity == null || menu == null) {
            return;
        }
        try {
            final int itemId = 0x42747476;
            if (menu.findItem(itemId) != null) {
                return;
            }
            android.view.MenuItem item = menu.add(Menu.NONE, itemId, Menu.NONE, "BTTV Settings");
            item.setShowAsAction(android.view.MenuItem.SHOW_AS_ACTION_NEVER);
            item.setOnMenuItemClickListener(new android.view.MenuItem.OnMenuItemClickListener() {
                @Override
                public boolean onMenuItemClick(android.view.MenuItem clicked) {
                    return open(activity);
                }
            });
            android.util.Log.i("BTTV318Diag", "SettingsActivity overflow fallback installed");
        } catch (Throwable failure) {
            android.util.Log.e("BTTV318Diag", "SettingsActivity overflow fallback failed", failure);
        }
    }'''
    return replace_once(text, old, new, 'SettingsNavigation.install')


def edit_live(text):
    text = replace_once(text,
        '    private static volatile boolean lookupFailureLogged;',
        '    private static volatile boolean lookupFailureLogged;\n    private static volatile boolean bttv318DiagFirstSplit;',
        'LiveEmotes diagnostic flag')
    text = replace_once(text,
        '''    public static List<Part> split(String text, String channelId) {
        if (text == null || text.isEmpty() || Data.ctx == null) {''',
        '''    public static List<Part> split(String text, String channelId) {
        if (!bttv318DiagFirstSplit) {
            bttv318DiagFirstSplit = true;
            try {
                Log.i("BTTV318Diag", "LiveEmotes.split entered, contextReady=" + (Data.ctx != null)
                        + ", globals BTTV=" + Emotes.globalEmotesBTTV.size()
                        + " FFZ=" + Emotes.globalEmotesFFZ.size()
                        + " 7TV=" + Emotes.globalEmotes7TV.size());
            } catch (Throwable ignored) {
                // Diagnostic logging must not break chat.
            }
        }
        if (text == null || text.isEmpty() || Data.ctx == null) {''',
        'LiveEmotes.split diagnostics')
    return text


def edit_globals(text):
    return replace_once(text,
        '                    Emotes.setGlobal(Emote.fromJSONArray(fetch(url), source), source);',
        '''                    Emotes.setGlobal(Emote.fromJSONArray(fetch(url), source), source);
                    Log.i("BTTV318Diag", "Global catalog fetched " + source + " n="
                            + (source == Emotes.Source.BTTV ? Emotes.globalEmotesBTTV.size()
                            : source == Emotes.Source.FFZ ? Emotes.globalEmotesFFZ.size()
                            : Emotes.globalEmotes7TV.size()));''',
        'LiveEmoteGlobals.success')


EDITORS = {
    'mod/app/src/main/java/bttv/settings/SettingsNavigation.java': edit_nav,
    'mod/app/src/main/java/bttv/emote/LiveEmotes.java': edit_live,
    'mod/app/src/main/java/bttv/emote/LiveEmoteGlobals.java': edit_globals,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--revert', action='store_true')
    ap.add_argument('--root', default='.', type=Path)
    args = ap.parse_args()
    root = args.root.resolve()
    state = root / '.bttv318-runtime-diagnostics-backup'
    manifest = state / 'manifest.json'
    probe = root / 'patches/live/zzzz_bttv_runtime_diagnostics.patch'
    kit = Path(__file__).parent / 'zzzz_bttv_runtime_diagnostics.patch'
    if args.revert:
        if not manifest.exists():
            raise ValueError('No diagnostic manifest found; refusing to revert')
        data = json.loads(manifest.read_text())
        for rel, value in data['files'].items():
            path = root / rel
            if sha(path.read_bytes()) != value['modified_sha256']:
                raise ValueError(f'{rel} changed after installation. Refusing to overwrite it.')
        if not probe.exists() or sha(probe.read_bytes()) != data['probe_sha256']:
            raise ValueError('Diagnostic patch changed or missing; refusing automatic revert')
        for rel, value in data['files'].items():
            (root / rel).write_bytes((state / rel).read_bytes())
        probe.unlink()
        manifest.unlink()
        print('Reverted the three Java edits and removed the diagnostics patch.')
        print('If you staged the probe, run: git reset -q -- patches/live/zzzz_bttv_runtime_diagnostics.patch')
        return
    if manifest.exists() or probe.exists():
        raise ValueError('Diagnostic probe already present. Revert before reinstalling.')
    if not kit.is_file():
        raise ValueError(f'Missing kit patch: {kit}')
    data = {}
    for rel, editor in EDITORS.items():
        path = root / rel
        if not path.exists():
            raise ValueError(f'Missing source: {path}')
        raw = path.read_bytes()
        if b'\r\n' in raw:
            raise ValueError(f'CRLF source not expected: {rel}; convert to LF before applying')
        new = editor(raw.decode('utf-8')).encode('utf-8')
        if new == raw:
            raise ValueError(f'No change generated for {rel}')
        data[rel] = (raw,new)
        print('Validated:', rel)
    if args.check:
        print('All three Java edits can be applied; late-stage smali patch available.')
        return
    state.mkdir(parents=True,exist_ok=False)
    entries={}
    try:
        for rel,(old,new) in data.items():
            backup=state / rel
            backup.parent.mkdir(parents=True,exist_ok=True)
            backup.write_bytes(old)
            (root/rel).write_bytes(new)
            entries[rel]={'original_sha256':sha(old), 'modified_sha256':sha(new)}
        probe.write_bytes(kit.read_bytes())
        manifest.write_text(json.dumps({'files':entries,'probe_sha256':sha(kit.read_bytes())},indent=2))
    except Exception:
        for rel,(old,new) in data.items():
            if (root/rel).exists():
                (root/rel).write_bytes(old)
        if probe.exists():probe.unlink()
        if state.exists():shutil.rmtree(state)
        raise
    print('Installed the diagnostic fallback and logging probes.')
    print('IMPORTANT: stage the new probe patch using: git add -- patches/live/zzzz_bttv_runtime_diagnostics.patch')
    print('Then build using a NEW BTTV_OUTPUT_DIR; updating this same signing identity preserves app data.')

if __name__ == '__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',exc,file=sys.stderr)
        sys.exit(1)
