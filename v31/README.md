# BTTV PR #740 for Twitch 31.8.0 — standalone APK builder

This branch is based on PR #740 and contains the 31.8.0 smali rebase. It also
fixes version metadata handling and offers a single-command Docker/BuildKit
build that exports **one signed APK** instead of a split APK installation set.

## Windows PowerShell build

Place an **unmodified, legally obtained Twitch 31.8.0** `.apkm` bundle in the
repository root as `twitch.zip`. Docker Desktop with Linux containers and
BuildKit must be available. Run from the repository root:

```powershell
docker build --progress=plain --output "type=local,dest=./dist" .
```

The exported file will be `dist/bttv-31.8.0.apk`. The Dockerfile copies the
scripts and sources, converts shell entrypoints to Unix LF, then runs setup,
hook application, compilation, split merger, signing, and verification. There
is no `docker run`, `docker exec`, container mount, or separate setup step.

On an ARM64 phone:

```powershell
adb install -r .\dist\bttv-31.8.0.apk
```

The source Twitch bundle used by this build contains only ARM64 native code,
so the single APK is not universal across CPU architectures. It **does** fold
all supplied screen-density resources into the package.

## Version fix

`bttv.manifest.json` controls both versionName and versionCode. The old
`v31/build_mod.sh` did not read it; the new script updates the compiled binary
AXML manifest (without re-encoding Twitch's resources), and validates the
resulting signed APK via `aapt2 dump badging`. With the current JSON values:

- `versionName` = `0.44.0-beta`
- `versionCode` = `1208000339` (JSON stores `01208000339`; interpreted as decimal)
- `package` = `tv.twitch.bttvandroid.app`

The split merger is [APKEditor](https://github.com/REAndroid/APKEditor), pinned
to V1.4.9. The final APK is aligned and signed by `uber-apk-signer` and checked
with Android SDK `apksigner` and `aapt2`. Its filename is
`dist/bttv-31.8.0.apk`.

## Signatures, compatibility, testing

The default local signing key may differ from the one used by any BTTV already
installed on the phone. A version bump does NOT fix
`INSTALL_FAILED_UPDATE_INCOMPATIBLE`. If signatures differ, use the original
signing key (not implemented in this streamlined local build), or back up data
before uninstalling the old package. Uninstalling erases that app's local data.

The rebase is still a source-level compatibility candidate. The eight smali
hooks can apply and the APK can build without guaranteeing that chat, 7TV/FFZ
emotes, or wide-emote layout all work at runtime. An actual Docker build and
Android install require the user's Twitch bundle and device; neither is
included in this repository snapshot. See the previous PR #740 rebase
history and `v31/apply_hooks_31_8.py` for hook details.

`docker build` without `--output` only stores its results as an image/build
cache; `--output type=local` exports the generated APK to the Windows folder.
