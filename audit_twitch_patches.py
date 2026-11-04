#!/usr/bin/env python3
"""Audit every PR #741 patch against the staged/decoded Twitch APK in Docker.

Run through the existing compose service with a NEW BTTV_OUTPUT_DIR:

  docker compose run --rm --entrypoint python3 build /source/audit_twitch_patches.py

This does not change /source. It runs the normal preparation steps with NOBUILD=1,
then resumes patch application *after* the first failure rather than stopping.
Later failures may be consequences of earlier failed patches.
"""

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile


def patch_files(patch_dir):
    """Use the actual Bash glob order from the PR's `patch` script.

    Python's sorted() uses Unicode code-point order, whereas Bash globbing
    uses the active locale's collation order. For example, bttvcompat may
    precede bttv.emote in Bash even though Python sorts them the other way.
    The original patch script loops over: *.patch **/*.patch
    """
    script = r'''cd "$1" || exit 1
for file in *.patch **/*.patch; do
    [ -f "$file" ] && printf '%s\0' "$file"
done
'''
    proc = subprocess.run(
        ["bash", "-c", script, "bash", str(patch_dir.resolve())],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    names = [os.fsdecode(p) for p in proc.stdout.split(b"\0") if p]
    return [patch_dir / name for name in names]


def relative_names(patches, patch_dir):
    return [p.relative_to(patch_dir).as_posix() for p in patches]


def old_targets(patch):
    """Old paths from every diff within a patch (including rename-only diffs)."""
    targets = []
    for line in patch.read_text(encoding="utf-8").splitlines():
        if line.startswith("--- a/"):
            targets.append(line[6:].split("\t", 1)[0])
        elif line.startswith("rename from "):
            targets.append(line[len("rename from "):])
    return list(dict.fromkeys(targets))


def safe_file(root, relative):
    path = root / relative
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return path


def classify(message):
    low = message.lower()
    if "does not exist in index" in low or "no such file" in low:
        return "missing target / dependency"
    if "patch does not apply" in low or "patch failed" in low:
        return "content mismatch"
    if "already exists in working directory" in low:
        return "file already exists"
    if "does not match index" in low:
        return "index / working tree mismatch"
    return "other git apply error"


def get_context(patch, disass, filename_index):
    result = []
    for rel in old_targets(patch):
        file = safe_file(disass, rel)
        if file is None:
            result.append({"target": rel, "exists": False, "error": "unsafe path"})
            continue
        exists = file.is_file()
        entry = {"target": rel, "exists": exists}
        if not exists:
            entry["same_filename_elsewhere"] = filename_index.get(Path(rel).name, [])[:20]
        result.append(entry)
    return result


def format_report(results, prep_error, audit_note, output):
    passed = sum(item["status"] == "PASS" for item in results)
    failed = sum(item["status"] == "FAIL" for item in results)
    lines = [
        "BTTV Twitch 31.8.0 patch compatibility audit",
        "=" * 48,
        f"Patches examined: {len(results)}",
        f"Applied: {passed}",
        f"Failed: {failed}",
        "",
        "IMPORTANT: Later failures may be caused by earlier failed patches.",
        "PASS only means a patch applied; it does NOT prove runtime compatibility.",
        "No patches were changed in your source checkout.",
        "",
    ]
    if prep_error:
        lines += ["PREPARATION RESULT:", prep_error, ""]
    if audit_note:
        lines += ["AUDIT NOTE:", audit_note, ""]
    lines += ["ALL PATCHES (in build order):"]
    lines += [f"  {item['status']:4s}  {item['patch']}" for item in results]
    lines += ["", "FAILED PATCH DETAILS:"]
    for item in results:
        if item["status"] != "FAIL":
            continue
        lines += [
            "", f"--- {item['patch']} ---",
            f"Classification: {item['category']}",
            f"Stage: {item['stage']}",
        ]
        if item.get("error"):
            lines += ["Git error:", item["error"].rstrip()]
        for target in item.get("targets", []):
            if target["exists"]:
                lines.append(f"Target exists:  {target['target']}")
            else:
                lines.append(f"MISSING TARGET: {target['target']}")
                lines.append("  Filename matches: " + repr(target.get("same_filename_elsewhere", [])))
    lines += ["", f"Raw log: {output / 'build' / 'build.log'}",
              f"JSON report: {output / 'patch-audit.json'}",
              f"Failed patch/source files: {output / 'failed-targets.zip'}", ""]
    return "\n".join(lines)


def collect_failure_files(results, patch_dir, disass, output):
    """Package only failed patch files and their decoded old-side targets locally."""
    archived = set()
    zpath = output / "failed-targets.zip"
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for item in results:
            if item["status"] != "FAIL":
                continue
            patch = patch_dir / item["patch"]
            if patch.is_file():
                arcname = "patches/" + item["patch"]
                if arcname not in archived:
                    archive.write(patch, arcname)
                    archived.add(arcname)
            for target in item.get("targets", []):
                if not target["exists"]:
                    candidates = target.get("same_filename_elsewhere", [])
                else:
                    candidates = [target["target"]]
                for rel in candidates:
                    src = safe_file(disass, rel)
                    if src is None or not src.is_file():
                        continue
                    arcname = "decoded/" + rel
                    if arcname not in archived:
                        archive.write(src, arcname)
                        archived.add(arcname)
    return zpath


def audit(source, workspace, output):
    source = source.resolve()
    workspace = workspace.resolve()
    output = output.resolve()
    report_dir = output
    if report_dir.exists() and any(report_dir.iterdir()):
        raise ValueError("Report directory already has files; choose a NEW BTTV_OUTPUT_DIR")
    report_dir.mkdir(parents=True, exist_ok=True)

    # Reuse precisely the build's tracked-only staging and preparation pipeline.
    sys.path.insert(0, "/source/tools")
    from build_production import build

    prep_error = ""
    old_nobuild = os.environ.get("NOBUILD")
    os.environ["NOBUILD"] = "1"  # Do not compile/sign an APK after patch checks.
    try:
        build(source, workspace, report_dir / "build")
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as exc:
        prep_error = f"{type(exc).__name__}: {exc}"
    finally:
        if old_nobuild is None:
            os.environ.pop("NOBUILD", None)
        else:
            os.environ["NOBUILD"] = old_nobuild

    log_path = report_dir / "build" / "build.log"
    if not log_path.is_file():
        raise RuntimeError("Build didn't produce build.log; preparation likely failed: " + prep_error)
    log = log_path.read_text(encoding="utf-8", errors="replace")
    marker = "=== Apply patches (4/5) ==="
    if marker not in log:
        raise RuntimeError("Build did not reach patch stage; inspect " + str(log_path)
                           + "\n" + prep_error)

    patch_dir = workspace / "patches"
    disass = workspace / "disass"
    patches = patch_files(patch_dir)
    names = relative_names(patches, patch_dir)
    index = {name: n for n, name in enumerate(names)}
    section = log.split(marker, 1)[1].splitlines()
    printed = [line.strip() for line in section if line.strip() in index]
    if printed != names[:len(printed)]:
        raise RuntimeError("Observed patch order differs from expected build order.\n"
                           + "Observed: " + repr(printed) + "\n"
                           + "Expected prefix: " + repr(names[:len(printed)]))
    if not printed:
        raise RuntimeError("Patch stage started but no patch was attempted; check " + str(log_path))

    filename_index = defaultdict(list)
    for path in disass.glob("smali*/**/*.smali"):
        filename_index[path.name].append(path.relative_to(disass).as_posix())

    results = []
    # The original script prints each patch name before attempting it, then exits
    # on the first failure. Therefore all but the last printed patch passed.
    last_attempted = printed[-1]
    first_failed = names.index(last_attempted)
    raw_tail = section
    for pos, line in enumerate(section):
        if line.strip() == last_attempted:
            raw_tail = section[pos + 1:]
    # If the patch step itself succeeded, there is no patch failure to resume.
    full_patch_list_completed = len(printed) == len(names) and not any(
        line.startswith("error:") for line in raw_tail
    )
    prefix_count = len(printed) if full_patch_list_completed else len(printed) - 1
    for name in names[:prefix_count]:
        results.append({"patch": name, "status": "PASS", "stage": "original build"})

    if not full_patch_list_completed:
        error_lines = [line for line in raw_tail if line.startswith("error:") or line.startswith("fatal:")]
        error = "\n".join(error_lines) or "\n".join(raw_tail[-8:])
        failed_patch = patch_dir / names[first_failed]
        results.append({
            "patch": names[first_failed], "status": "FAIL", "stage": "original build",
            "category": classify(error), "error": error,
            "targets": get_context(failed_patch, disass, filename_index)
        })

        for patch in patches[first_failed + 1:]:
            name = patch.relative_to(patch_dir).as_posix()
            proc = subprocess.run(
                ["git", "-c", "safe.directory=" + str(disass), "apply", "--index", str(patch)],
                cwd=disass, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            if proc.returncode == 0:
                results.append({"patch": name, "status": "PASS", "stage": "continued audit"})
                print("PASS", name, flush=True)
            else:
                error = "\n".join(s for s in [proc.stdout, proc.stderr] if s).strip()
                results.append({
                    "patch": name, "status": "FAIL", "stage": "continued audit",
                    "category": classify(error), "error": error,
                    "targets": get_context(patch, disass, filename_index)
                })
                print("FAIL", name, "--", classify(error), flush=True)

    note = ("All patches applied in the original build; NOBUILD intentionally stopped "
            "APK compilation." if full_patch_list_completed else
            "Continuing after the first failed patch may cause dependent patches "
            "to fail too. This is an audit, not a complete automatic port.")
    info = {
        "total": len(names),
        "passed": sum(r["status"] == "PASS" for r in results),
        "failed": sum(r["status"] == "FAIL" for r in results),
        "preparation_result": prep_error,
        "note": note,
        "results": results,
    }
    (report_dir / "patch-audit.json").write_text(
        json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    summary = format_report(results, prep_error, note, report_dir)
    (report_dir / "patch-audit.txt").write_text(summary, encoding="utf-8")
    collect_failure_files(results, patch_dir, disass, report_dir)
    print("\n" + "=" * 55)
    print(f"Checked {info['total']} patches: {info['passed']} passed, {info['failed']} failed")
    print("Report: " + str(report_dir / "patch-audit.txt"))
    print("JSON: " + str(report_dir / "patch-audit.json"))
    print("Failure details: " + str(report_dir / "failed-targets.zip"))
    print("Full build log: " + str(log_path))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", type=Path, default=Path("/source/twitch.zip"))
    p.add_argument("--workspace", type=Path, default=Path("/tmp/bttv-build"))
    p.add_argument("--output", type=Path, default=Path("/output"))
    a = p.parse_args()
    audit(a.source, a.workspace, a.output)


if __name__ == "__main__":
    main()
