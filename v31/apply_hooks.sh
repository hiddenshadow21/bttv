#!/bin/bash
# Diagnostic CONTROL build for Twitch 31.8.0.
# Intentionally apply NO BTTV smali hooks and NO Hermes timestamp bytecode patch.
# We still use the regular BTTV packaging/signing pipeline so it can be compared
# with the user's patched build without changing the underlying Twitch version.
set -euo pipefail
cd /usr/build/work
git checkout -q base -- .
# Fail closed: a dirty staged worktree or changed Hermes bundle invalidates
# the "stock Twitch code" control. No .smali or RN bundle modifications allowed.
if ! git diff --quiet base -- .; then
  echo 'ERROR: Twitch control sources differ from base' >&2
  exit 1
fi
echo 'BTTV_CONTROL_NO_HOOKS: clean Twitch 31.8.0 smali + original Hermes bundle'
