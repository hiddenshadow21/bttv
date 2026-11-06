#!/bin/bash
# Apply PR #740's RN hook implementation to verified Twitch 31.8.0 entry points.
set -euo pipefail
cd /usr/build/work
# Reset source changes before each patch pass; preserve untracked build outputs.
git checkout -q base -- .
python3 /repo/v31/apply_hooks_31_8.py --work /usr/build/work
# Patch Hermes bytecode after smali hooks, before apktool repackages the base.
# The source/target instruction sequences are checked by the patch script.
python3 /repo/v31/patch_hermes_timestamps.py \
  --bundle /usr/build/work/assets/index.android.bundle \
  --tool /usr/local/bin/hermes-decomp

git diff --stat
