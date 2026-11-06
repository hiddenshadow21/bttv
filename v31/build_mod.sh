#!/bin/bash
# Builds PR #740's code, updates bttv.manifest.json metadata in the binary AXML,
# merges Twitch's split APKs to one standalone APK, signs and verifies it.
# Output: /artifact/bttv-31.8.0.apk (run after setup.sh and apply_hooks.sh).
#
# The app gets its own package name and name, so it can be installed next to the official app:
#   BTTV_PACKAGE (default tv.twitch.bttvandroid.app), BTTV_NAME (default BTTV)
# The background of the launcher icon gets the color of the mod.
set -eu
cd /usr/build

TWITCH_PACKAGE=tv.twitch.android.app
[ -z "${BTTV_PACKAGE:-}" ] && BTTV_PACKAGE=tv.twitch.bttvandroid.app
[ -z "${BTTV_NAME:-}" ] && BTTV_NAME=BTTV
# bttv_mega, the launcher icon needs a color resource of the app with this value
ICON_COLOR=ff00fafa
AAPT2="$ANDROID_SDK_ROOT/build-tools/30.0.3/aapt2"
APKSIGNER="$ANDROID_SDK_ROOT/build-tools/30.0.3/apksigner"
VERSION=$(jq -er '.version | select(type == "string" and length > 0)' /repo/bttv.manifest.json)
VERSIONCODE=$(jq -er '.versionCode | select(type == "string" and test("^[0-9]+$"))' /repo/bttv.manifest.json)
echo "BTTV version: $VERSION, code: $VERSIONCODE"
echo "BTTV_PACKAGE: $BTTV_PACKAGE"
echo "BTTV_NAME: $BTTV_NAME"

echo "== prepare mod project"
rm -rf mod
cp -r /repo/mod mod
rm -rf mod/.gradle mod/build mod/*/build mod/local.properties

echo "== gradle"
# Windows checkouts may have converted gradlew to CRLF.
sed -i 's/\r$//' mod/gradlew
(cd mod && bash gradlew assemble --console=plain -q)

echo "== dex -> smali"
rm -rf modsmali && mkdir modsmali
unzip -q -o mod/consumer/build/outputs/apk/release/consumer-release-unsigned.apk classes.dex -d modsmali
java -jar $BAKSMALI_PATH d -o modsmali/out modsmali/classes.dex
find modsmali/out/bttv -type f -exec sed -i -e 's/BTTVDefaultConstructorMarker/DefaultConstructorMarker/g' {} \;

# Put mod code into a NEW DEX. 31.8.0 may already have classes7.dex;
# deleting smali_classes7 (as the 31.5.2 build did) would destroy Twitch code.
if [ -f work/.bttv-generated-dex-dir ]; then
  previous=$(cat work/.bttv-generated-dex-dir)
  if [[ "$previous" =~ ^smali_classes[0-9]+$ ]]; then
    rm -rf "work/$previous"
  else
    echo "Invalid previous DEX marker" >&2
    exit 1
  fi
fi
max_dex=1
for d in work/smali_classes[0-9]*; do
  [ -d "$d" ] || continue
  dex_num=${d##*smali_classes}
  if [[ "$dex_num" =~ ^[0-9]+$ ]] && (( 10#$dex_num > max_dex )); then
    max_dex=$((10#$dex_num))
  fi
done
mod_dir="smali_classes$((max_dex + 1))"
mkdir -p "work/$mod_dir"
cp -r modsmali/out/bttv "work/$mod_dir/bttv"
printf '%s\n' "$mod_dir" > work/.bttv-generated-dex-dir
echo "BTTV classes -> $mod_dir"

echo "== rename package"
rm -rf out && mkdir -p out/tool
javac -d out/tool /repo/v31/RenamePackage.java
ICON=res/mipmap-anydpi-v26/ic_launcher.xml
(cd work && git checkout -q base -- AndroidManifest.xml resources.arsc $ICON)
ICON_COLOR_ID=$($AAPT2 dump resources split/base.apk | grep -B1 -m1 -E "^ +\(\) #$ICON_COLOR\$" | grep -oE "0x7f[0-9a-f]+" | head -1)
[ -z "$ICON_COLOR_ID" ] && echo "no color resource with the value $ICON_COLOR" && exit 1
java -cp out/tool RenamePackage icon work/$ICON ${ICON_COLOR_ID#0x}
java -cp out/tool RenamePackage manifest work/AndroidManifest.xml \
  "$TWITCH_PACKAGE" "$BTTV_PACKAGE" "$BTTV_NAME" "$VERSION" "$VERSIONCODE"
java -cp out/tool RenamePackage arsc work/resources.arsc $TWITCH_PACKAGE $BTTV_PACKAGE

echo "== rebuild base APK"
java -Xmx5g -jar "$APKTOOL_PATH" b work -o out/base.apk

echo "== prepare renamed split APKs"
mkdir -p out/merge
cp out/base.apk out/merge/base.apk
for f in split/split_config.*.apk; do
  [ -f "$f" ] || { echo "Missing Twitch config splits" >&2; exit 1; }
  java -cp out/tool RenamePackage apk "$f" "out/merge/$(basename "$f")" \
    "$TWITCH_PACKAGE" "$BTTV_PACKAGE" "$VERSION" "$VERSIONCODE" > /dev/null
done

echo "== merge all split APKs into one standalone APK"
# All split manifests now use the exact same BTTV package and versionCode as
# the patched base. Treat any remaining incompatible-merge warning as a failure.
if ! java -Xmx5g -jar "$APKEDITOR_PATH" m \
  -i out/merge -o out/bttv-merged.apk > out/merge.log 2>&1; then
  cat out/merge.log
  exit 1
fi
cat out/merge.log
if grep -Fq 'WARN: Incompatible to merge:' out/merge.log; then
  echo "ERROR: APKEditor refused an incompatible split; check split manifest versions" >&2
  exit 1
fi

echo "== sign merged APK"
java -jar "$UBER_APK_SIGNER_PATH" -a out/bttv-merged.apk > out/sign.log
cat out/sign.log
signed_apk=out/bttv-merged-aligned-debugSigned.apk
[ -s "$signed_apk" ] || { echo "APK signing failed: $signed_apk was not produced" >&2; exit 1; }

echo "== verify output APK and BTTV metadata"
"$APKSIGNER" verify --verbose "$signed_apk"
"$AAPT2" dump badging "$signed_apk" > out/badging.txt
sed -n '1,3p' out/badging.txt
# Compare integer versions as decimal (the JSON code has a leading zero).
EXPECTED_CODE=$(python3 -c 'import sys; print(int(sys.argv[1], 10))' "$VERSIONCODE")
grep -F "name='$BTTV_PACKAGE'" out/badging.txt | grep -F "versionCode='$EXPECTED_CODE'" | grep -F "versionName='$VERSION'" > /dev/null || {
  echo "Incorrect package name, version code, or version name in signed APK" >&2
  exit 1
}
mkdir -p /artifact
cp "$signed_apk" /artifact/bttv-31.8.0.apk
ls -lh /artifact/bttv-31.8.0.apk
