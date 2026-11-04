# BTTV Twitch 31.8.0 — DEX2 reference limit diagnostic

## Evidence

Latest probe `20261102-192624-34179f32` got past the earlier `pb6` register error, then Apktool 2.9.3 failed assembling `smali_classes2`:

```
Exception occurred while writing code_item for method Lq04;->values()[Lq04;
Error while writing instruction at code offset 0x2
Unsigned short value out of range: 65536
```

This is consistent with a 16-bit DEX method/type/field reference index limit, **not** a register range problem. The exact reference index type was not displayed by Apktool, though a method-reference overflow is particularly likely for an enum `values()` method. Editing `q04.values()` itself would not fix an overfull pool.

## Intended change

The helper `twitch318_dex_rebalance.py` inserts one line in the tracked `build` shell script, *before* `cd "$1"`, to rebalance smali classes **after** all patches have been applied but **before** Apktool assembly.

- Reads all `.smali` in decoded `smali_classes2` and `smali_classes7`.
- Estimates distinct method/field references from smali declarations and instructions. These are estimates, not actual dexlib2 indices.
- Plans to move whole outer/inner class groups from DEX2 to DEX7 until estimated references are <= 62,000 and at least 3,500 method refs have been removed.
- Refuses to move a class if destination path exists, refuses to overfill the destination on its estimated counts, prints the plan to build.log, and fails rather than silently proceeding if no safe plan is found.
- Does **not** change instructions, method signatures, patch files, or source repository smali. Moves only files within the disposable decoded workspace under `/tmp/bttv-build/disass`.
- Retains the existing seven-DEX layout; no eighth dex is added.

## Install (Windows PowerShell, repository root)

```powershell
Expand-Archive -LiteralPath .\twitch318-dex2-rebalance-diagnostic.zip -DestinationPath . -Force
python .\twitch318_dex_rebalance.py --install .\build

# Confirm the hook was inserted:
Select-String .\build -Pattern 'BEGIN BTTV TWITCH 31.8 DEX REBALANCE' -Context 0,3

# Uses your existing unique-output diagnostic probe and restores the 3 disabled patches:
.\probe_twitch318_build_v2.ps1
```

Upload the **new** unique `dist\twitch318-build-evidence-*.zip` file. If the rebalancer refuses, the last lines of this run's build.log will include its estimated method/field counts. If it succeeds but another DEX overflows, the new log will identify it.

**This is still a diagnostic APK, not a usable build:** the probe disables `cl2`, `r2k`, and `zy_gif_modes`, and other old helper references remain unverified.

## Undo the one-line build-script modification

```powershell
python .\twitch318_dex_rebalance.py --remove .\build
```

`build.before-twitch318-dex-rebalance` is a one-time local backup. The original script can also be restored with Git if its other modifications are not needed, but avoid doing so without inspecting current changes.

## Limitations

- DEX reference estimates can undercount complex smali references. A further overflow may require tuning the targets or additional relocation.
- Cross-DEX class references are supported by modern Android multidex, but **successful assembly does not verify runtime initialization or feature correctness**.
- This is a temporary workaround to move past the first assembler failure; production use requires a deterministic, reviewed DEX layout and full APK verification.
