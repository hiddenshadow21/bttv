# Docker-only Twitch 31.8.0 decompiler (Windows PowerShell)

**Nothing except Docker Desktop is installed on Windows.** This uses a separate
image and script; the BTTV builder, release APK and production source code are
not modified.

## Input

Use the **original, unmodified** Twitch 31.8.0 bundle that you already use for
your BTTV build. Default source (first found at repository root):

- twitch.zip (ZIP containing base.apk + split APKs)
- twitch.apkm (APKMirror bundle)
- twitch.apk (single base APK)

Other paths are supported with the -InputPath argument.

## Run

From the BTTV repository root, in Windows PowerShell:

    powershell -ExecutionPolicy Bypass -File .\v31\diagnostics\decompile\run.ps1

Or specify a custom input and output directory:

    powershell -ExecutionPolicy Bypass -File .\v31\diagnostics\decompile\run.ps1 -InputPath "D:\Twitch\twitch.apkm" -OutputDirectory "D:\Twitch\twitch318-decoded"

The PowerShell script builds the small, standalone Docker image from the
v31/diagnostics/decompile subdirectory. It bind-mounts the input bundle
read-only and writes output only to the chosen directory. The source bundle is
never included in the Docker image and is not uploaded anywhere by these
scripts. Docker downloads the pinned public Apktool/JADX releases to build
the tool image.

Do **not** run the repository root Dockerfile for this task: that builds
and signs BTTV, not the analysis output.

## Output

Default directory: dist/twitch318-decompiled/

- apktool-base/ — decoded base.apk resources and smali.
- apktool-splits/ — smali from any DEX-containing split APKs.
- jadx-java/ — readable Java-like source from DEX-bearing APKs.
- hermes-bundles/ — raw .bundle, .hbc or .jsbundle files found under
  assets/ in base/splits. These are binary data, not decompiled JS.
- chat-review/ — a targeted subset of chat/theatre/player/React Native
  classes, manifest (if decodable), and a report with class/token matches.
- chat-restore-review.zip — targeted classes plus raw Hermes bundles.
- logs/ — Apktool/JADX logs. Read these if any output looks incomplete.

**Upload chat-restore-review.zip**, not the entire decompiled tree. Check the
ZIP first. If a particular obfuscated lifecycle class is missing, the full
local output will let us gather it later. Never include app data, login
sessions, auth tokens, or personal logs.

Apktool first tries full resource decode, then retries with --no-res if
resources are not decodable. JADX errors are recorded in logs/jadx.log; a
partial Java output doesn't mean the smali decode failed. A successful Docker
run cannot prove that any later APK patch works on-device.

Rerunning the script **replaces** the previous apktool-base/,
apktool-splits/, jadx-java/, hermes-bundles/, and chat-review/
directories in that output folder. Save any manual edits elsewhere.

## Branch hygiene

This tool lives only on diagnostics/chat-restore-31.8.0, not on your active
feature branch. To use it without changing your current checkout:

    $repo = (Get-Location).Path
    git fetch origin diagnostics/chat-restore-31.8.0
    git worktree add --detach ..\bttv-chat-tools FETCH_HEAD
    powershell -ExecutionPolicy Bypass -File ..\bttv-chat-tools\v31\diagnostics\decompile\run.ps1 -InputPath "$repo\twitch.zip" -OutputDirectory "$repo\dist\twitch318-decompiled"

Replace -InputPath if your file is .apkm or stored elsewhere.
