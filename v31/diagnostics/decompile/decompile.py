#!/usr/bin/env python3
"""Decode a locally supplied Twitch APK/APKM/ZIP in an isolated container."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

APKTOOL = ["java", "-jar", "/opt/tools/apktool.jar"]
JADX = ["/opt/jadx/bin/jadx", "--no-res", "-j", "4"]
TARGET_NAME = re.compile(
    r"TwitchRNTheatre|TheatreModeFragment|MiniPlayer|MinimizedPlayer|"
    r"Miniplayer|SurfaceMountingManager|FabricUIManager|ViewerLandingActivity|"
    r"ReactRootView|ReactFragment|WindowInsets|SoftInput|KeyboardAvoidingView",
    re.IGNORECASE,
)
BUNDLE_NAME = re.compile(r"(?:\.hbc$|\.jsbundle$|\.bundle$)", re.IGNORECASE)
TOKENS = (b"theatre-chat", b"chat-input-bar", b"theatre-screen",
          b"rn_theatre_container", b"adjustResize", b"keyboardDidShow")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def input_apks(source, stage):
    """Extract only APK members, never arbitrary archive paths."""
    stage.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() == ".apk":
        target = stage / "base.apk"
        shutil.copyfile(source, target)
        return [target], target
    if source.suffix.lower() not in (".zip", ".apkm", ".apks", ".xapk"):
        raise ValueError("Input must be .apk, .zip, .apkm, .apks or .xapk")
    files = []
    with zipfile.ZipFile(source) as archive:
        members = [item for item in archive.infolist()
                   if not item.is_dir() and item.filename.lower().endswith(".apk")]
        if not members:
            raise ValueError("Archive contains no APK files")
        used = set()
        for item in members:
            basename = Path(item.filename.replace("\\", "/")).name
            if basename.lower() in used:
                raise ValueError("Duplicate APK basename in bundle: " + basename)
            used.add(basename.lower())
            destination = stage / basename
            with archive.open(item) as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            files.append(destination)
    bases = [file for file in files if file.name.lower() == "base.apk"]
    if not bases:
        bases = [file for file in files if file.stem.lower().startswith("base")]
    if len(bases) != 1:
        raise ValueError("Expected one base APK, found " + str(len(bases)))
    return files, bases[0]


def has_dex(apk):
    with zipfile.ZipFile(apk) as archive:
        return any(re.fullmatch(r"classes\d*\.dex", name.split("/")[-1])
                   for name in archive.namelist())


def pull_bundles(apks, target):
    total = []
    for apk in apks:
        with zipfile.ZipFile(apk) as archive:
            for item in archive.infolist():
                name = item.filename.replace("\\", "/")
                if (item.is_dir() or not name.startswith("assets/") or
                        not BUNDLE_NAME.search(name) or item.file_size > 128 * 1024 * 1024):
                    continue
                dst = target / apk.stem / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as src, dst.open("wb") as output:
                    shutil.copyfileobj(src, output)
                total.append(dst)
    return total


def command(argv, logfile):
    print("Running:", " ".join(argv[:6]), "...", flush=True)
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with logfile.open("w", encoding="utf-8") as log:
        process = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT,
                                 check=False)
    return process.returncode


def review_candidates(paths, review_root):
    copied = []
    for kind, root in paths:
        if not root.is_dir():
            continue
        for file in root.rglob("*"):
            if not file.is_file() or not TARGET_NAME.search(file.name):
                continue
            if file.suffix.lower() not in (".java", ".smali"):
                continue
            relative = file.relative_to(root)
            destination = review_root / kind / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, destination)
            copied.append(str(Path(kind) / relative))
    return sorted(copied)


def scan_tokens(paths, max_hits=200):
    hits = []
    for kind, root in paths:
        if not root.is_dir():
            continue
        for file in root.rglob("*"):
            if not file.is_file() or file.suffix.lower() not in (".java", ".smali"):
                continue
            with file.open("rb") as src:
                for line_no, line in enumerate(src, 1):
                    found = [token.decode("ascii") for token in TOKENS if token in line]
                    if found:
                        hits.append({"file": str(Path(kind) / file.relative_to(root)),
                                     "line": line_no, "tokens": found})
                        if len(hits) >= max_hits:
                            return hits
    return hits


def pack_review(folder, bundle_folder, zip_path):
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as out:
        for root in (folder, bundle_folder):
            if not root.exists():
                continue
            for file in sorted(root.rglob("*")):
                if file.is_file():
                    out.write(file, arcname=str(Path(root.name) / file.relative_to(root)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("/input/twitch.zip"))
    parser.add_argument("--output", type=Path, default=Path("/out"))
    args = parser.parse_args()
    source = args.input.resolve()
    output = args.output.resolve()
    if not source.is_file():
        parser.error("Input bundle does not exist: " + str(source))
    output.mkdir(parents=True, exist_ok=True)
    smali = output / "apktool-base"
    split_smali = output / "apktool-splits"
    java = output / "jadx-java"
    bundles = output / "hermes-bundles"
    review = output / "chat-review"
    staging = output / "_staging-apks"
    for directory in (smali, split_smali, java, bundles, review, staging):
        if directory.exists():
            shutil.rmtree(directory)
    logs = output / "logs"
    logs.mkdir(exist_ok=True)
    report = {"input_filename": source.name, "input_sha256": sha256(source),
              "tools": {"apktool": "2.12.1", "jadx": "1.5.3"}, "warnings": []}
    try:
        apks, base = input_apks(source, staging)
        report["apk_files"] = [file.name for file in apks]
        report["base_apk"] = base.name
        report["dex_apks"] = [file.name for file in apks if has_dex(file)]
        # Default resource decoding may fail for OEM/newer APKs; keep smali.
        rc = command(APKTOOL + ["d", "-f", "-o", str(smali), str(base)],
                     logs / "apktool.log")
        if rc:
            report["warnings"].append("Full Apktool resource decode failed; trying --no-res")
            shutil.rmtree(smali, ignore_errors=True)
            rc = command(APKTOOL + ["d", "-f", "--no-res", "-o", str(smali), str(base)],
                         logs / "apktool-no-res.log")
        if rc:
            raise RuntimeError("Apktool failed; see logs/apktool*.log")
        dex = [file for file in apks if has_dex(file)]
        paths = [("smali", smali), ("java", java)]
        for split in dex:
            if split == base:
                continue
            split_dest = split_smali / split.stem
            rc = command(APKTOOL + ["d", "-f", "--no-res", "-o", str(split_dest), str(split)],
                         logs / ("apktool-" + split.stem + ".log"))
            if rc:
                report["warnings"].append("Could not decode split " + split.name + "; see apktool log")
            else:
                paths.append(("split-smali/" + split.stem, split_dest))
        if dex:
            rc = command(JADX + ["-d", str(java), *map(str, dex)], logs / "jadx.log")
            if rc:
                report["warnings"].append("JADX exited non-zero; see logs/jadx.log; smali may still be usable")
        else:
            report["warnings"].append("No classes.dex found in supplied APK files")
        extracted = pull_bundles(apks, bundles)
        report["hermes_or_js_bundles"] = [str(file.relative_to(bundles)) for file in extracted]
        copied = review_candidates(paths, review)
        report["review_files"] = copied
        report["string_matches"] = scan_tokens(paths)
        (review / "REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        # Manifest may help check soft-input handling.
        manifest = smali / "AndroidManifest.xml"
        if manifest.is_file() and manifest.stat().st_size < 5_000_000:
            shutil.copy2(manifest, review / "AndroidManifest.xml")
        zip_path = output / "chat-restore-review.zip"
        if zip_path.exists():
            zip_path.unlink()
        pack_review(review, bundles, zip_path)
        print("Base smali:", smali)
        print("Split smali:", split_smali)
        print("Full Java:", java)
        print("Targeted review ZIP:", zip_path)
        print("Review files:", len(copied), "bundles:", len(extracted))
        if report["warnings"]:
            print("WARNINGS:", *report["warnings"], sep="\n - ")
    finally:
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError, zipfile.BadZipFile) as error:
        print("Decompiler failed:", error, file=sys.stderr)
        sys.exit(1)
