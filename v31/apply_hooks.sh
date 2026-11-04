#!/bin/bash
# Apply PR #740's RN hook implementation to verified Twitch 31.8.0 entry points.
set -euo pipefail
cd /usr/build/work
# Reset source changes before each patch pass; preserve untracked build outputs.
git checkout -q base -- .
python3 /repo/v31/apply_hooks_31_8.py --work /usr/build/work
git diff --stat
