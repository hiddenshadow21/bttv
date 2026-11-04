# Twitch 31.8.0 compilation fix: pb6.smali / z86.smali.patch

The Round 10 build evidence shows that the probe reached Apktool 2.9.3 DEX assembly but stopped at:

`smali_classes2/pb6.smali[2591,4] Invalid register: v29. Must be between v0 and v15, inclusive.`

Cause: Round 5 `z86.smali.patch` increased `.locals` in the
`Lpb6;->a(Ltv/twitch/android/models/Tuid;Lx5o;Ljava/lang/String;Lu76;)La56;` method from 26 to 28.
The injected `invoke-virtual {p1}` becomes a reference to register `v29`, which is
not encodable in an ordinary (35c) invoke.

The replacement uses `invoke-virtual/range {p1 .. p1}` instead. It keeps the
method's 28 locals, the `Tuid.toString()` call, and the bridge call intact.

Checks performed:
- Git indexed check/application against the uploaded 31.8.0 unmodified `pb6.smali`: PASS.
- Method register relationship (`p1 == v29`) and range form: checked.
- Complete Apktool assembly / installation / device runtime: NOT tested.

This is a single-file fix. Unzip it at your repository root. It does not
replace the other 62 patch files. Run your diagnostic build probe again to
reveal the *next* assembly error (if any). The three omitted hooks are still
omitted only during the probe.
