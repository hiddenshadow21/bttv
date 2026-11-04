#!/usr/bin/env python3
"""Safely update PR #741's native ABI verifier for the Twitch 31.8.0 input.

This keeps strict native integrity checks. It does NOT disable release verification.
It rejects missing/altered original Twitch .so files, unexpected extra libraries,
missing BTTV Glide-WebP, invalid ABI inventories, and conflicting duplicate names.

Usage: python fix_twitch318_native_verifier.py --apply tools/verify_release_apk.py
       python fix_twitch318_native_verifier.py --check tools/verify_release_apk.py
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys

MARKER = "BTTV318_INPUT_DERIVED_NATIVE_INVENTORY_V1"

HELPER = '''# BTTV318_INPUT_DERIVED_NATIVE_INVENTORY_V1
# Compare the output to the *pinned* Twitch input rather than the native counts
# of Twitch 31.2.0. The caller has already validated source with inspect().
def verify_twitch318_native_inventory(output_zip, source, output_names, native_counts):
    required_abis = ("arm64-v8a", "armeabi-v7a")
    selected = ("base.apk", "split_config.arm64_v8a.apk", "split_config.armeabi_v7a.apk")
    original_libraries = {abi: {} for abi in required_abis}
    with zipfile.ZipFile(source) as source_bundle:
        for apk_name in selected:
            if apk_name not in source_bundle.namelist():
                raise ValueError("Missing validated source split: " + apk_name)
            with zipfile.ZipFile(io.BytesIO(source_bundle.read(apk_name))) as source_apk:
                for entry in source_apk.infolist():
                    name = entry.filename
                    if not name.endswith(".so") or not name.startswith("lib/"):
                        continue
                    parts = name.split("/")
                    if len(parts) != 3 or parts[1] not in required_abis:
                        continue
                    abi = parts[1]
                    fingerprint = (entry.file_size, hashlib.sha256(source_apk.read(name)).digest())
                    previous = original_libraries[abi].setdefault(name, fingerprint)
                    if previous != fingerprint:
                        raise ValueError("Conflicting source native library across splits: " + name)

    for abi in required_abis:
        prefix = "lib/" + abi + "/"
        original = original_libraries[abi]
        built = {name for name in output_names
                 if name.startswith(prefix) and name.endswith(".so")}
        if not original:
            raise ValueError("Input lacks required native ABI libraries: " + abi)
        # Buildsource adds this one BTTV-owned library to each architecture.
        # Original Twitch libraries must remain byte-for-byte unchanged.
        glide = prefix + "libglide-webp.so"
        expected = set(original) | {glide}
        missing = sorted(expected - built)
        extra = sorted(built - expected)
        if missing or extra or native_counts.get(abi, 0) != len(built):
            raise ValueError(
                "Native inventory mismatch for " + abi +
                ": input=" + str(len(original)) +
                ", expected_output=" + str(len(expected)) +
                ", actual_output=" + str(len(built)) +
                ", missing=" + repr(missing[:12]) +
                ", unexpected=" + repr(extra[:12]))
        for name, (original_size, original_hash) in original.items():
            compiled_info = output_zip.getinfo(name)
            if compiled_info.file_size != original_size or hashlib.sha256(output_zip.read(name)).digest() != original_hash:
                raise ValueError("Original Twitch native library changed: " + name)
        # The calling verifier independently checks ELF type, architecture,
        # ZIP_STORED compression and 4096-byte native library alignment.
        print("Verified native inventory for " + abi +
              ": original=" + str(len(original)) +
              ", output=" + str(len(built)) +
              ", BTTV Glide-WebP=" + ("present" if glide in built else "MISSING"),
              flush=True)

'''

CALL = "        verify_twitch318_native_inventory(z, source, names, native_counts)\n"


def find_region(src: str) -> tuple[int, int]:
    # Target the old rigid 39+38 check, not the ELF architecture validation above.
    if "native_counts.get(abi) != 39" not in src:
        raise ValueError("Expected original 39-library rule is absent; refusing a blind edit")
    start = src.rfind("        for abi in ['arm64-v8a', 'armeabi-v7a']:", 0, src.index("native_counts.get(abi) != 39"))
    if start < 0:
        raise ValueError("Could not identify native check start")
    end = src.find("    return dict(", start)
    if end < 0:
        raise ValueError("Could not identify native check end")
    section = src[start:end]
    for required in ("with zipfile.ZipFile(source) as bundle:", "Original Twitch native library changed", "libglide-webp.so"):
        if required not in section:
            raise ValueError("Unexpected verifier native-check structure: missing " + required)
    return start, end


def modify(source: str) -> str:
    if MARKER in source:
        return source
    if "import hashlib" not in source or "import io" not in source or "import zipfile" not in source:
        raise ValueError("Verifier lacks required Python imports")
    start, end = find_region(source)
    rewritten = source[:start] + CALL + source[end:]
    function_start = rewritten.find("def verify(apk, source, sdk=None")
    if function_start < 0:
        raise ValueError("Could not find verify() definition")
    rewritten = rewritten[:function_start] + HELPER + rewritten[function_start:]
    rewritten = rewritten.replace("twitchVersion='31.2.0'", "twitchVersion='31.8.0'")
    ast.parse(rewritten)
    return rewritten


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--apply', type=Path, metavar='VERIFIER')
    mode.add_argument('--check', type=Path, metavar='VERIFIER')
    args = parser.parse_args()
    path = args.apply if args.apply else args.check
    current = path.read_text(encoding='utf-8')
    if MARKER in current:
        ast.parse(current)
        print('Already updated; syntax valid:', path)
        return
    candidate = modify(current)
    if args.check:
        print('Verifier matches the expected PR #741 structure and can be updated:', path)
        return
    backup = path.with_name(path.name + '.pre-twitch318-nativecheck.bak')
    if backup.exists():
        raise FileExistsError('Backup already exists; not overwriting: ' + str(backup))
    backup.write_bytes(path.read_bytes())
    try:
        path.write_text(candidate, encoding='utf-8', newline='\n')
    except Exception:
        path.write_bytes(backup.read_bytes())
        raise
    print('Updated:', path)
    print('Backup:', backup)
    print('Preserved: input pinning, ELF checks, alignment, DEX checks, APK signature, byte-for-byte native checks')
    print('Next: rerun Docker build with a NEW BTTV_OUTPUT_DIR.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
        sys.exit(1)
