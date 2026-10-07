# PCSD00001 iOS rendering investigation

## Status

This is a synchronization correctness and diagnostic build, not a confirmed
Golden Abyss rendering fix. Device verification is required. No game files,
MaiDump loading, system-language selection, input, or touch code were changed.
GPU Copy and Surface Sync settings are unchanged.

## Observed evidence

The supplied `tsubomi-1.log` identifies build `da8052d`, not `4cba7b3`.
It uses an Apple A16 GPU, texture viewport, disabled memory mapping,
`disable-surface-sync=true`, and disabled fault-based surface dirty tracking.
It ends with an orderly return to the game library, not a recorded crash.

The log includes:

```text
07:13:30.953 partial cached color surface:
requested=1440x408 offset=0,0 cached=720x408

07:13:33.946 surface-cache entries:
0x60600000 R16G16B16A16Sfloat 720x408 stride=2880 Linear
0x60849E00 R16G16B16A16Sfloat 720x408 stride=5888 Tiled
0x610627C0 R16G16B16A16Sfloat 180x102 stride=736 Linear

0x60A9FEC0 alternates between R8G8B8A8Srgb (stride=2880)
and R32G32Sfloat (stride=5760), both 720x408.
```

The stride is in *guest bytes*. An F16 Vulkan format does not prove that the
guest format is F16: `color::translate_format` also expands the 32-bit guest
`U2F10F10F10` format to 64-bit `R16G16B16A16Sfloat`. Native F16 at 720 pixels
would occupy 5760 bytes per row, not 2880. Do not apply raw host F16 byte-copy
assumptions to these expanded formats.

There are warnings for unimplemented ColorSurfaceSetClip and visibility-test
enables, and unsupported safe U/V address-mode requests. They are not proof of
the noise or dark-scene cause. The log contains no Vulkan validation report
and no per-lookup guest formats for the 1440-wide request.

## Code defects corrected

1. `pipeline_cache.cpp`: the incoming dependency previously exposed attachment
   writes only to attachment reads. The second dependency was the reverse
   shader-read -> attachment-write dependency, despite its misleading comment.
   Direct render-target texture sampling therefore lacked a matching
   attachment-write -> shader-read dependency. Include both vertex and fragment
   consumers, transfer producers, and early/late depth accesses. Correct the
   interlock dependency update that previously targeted an entry overwritten
   immediately afterward.
2. `surface_cache.cpp`: establish attachment/transfer-write -> transfer-read
   visibility before reading the source image for a cast/crop copy. `GENERAL`
   alone does not establish synchronization.
3. The typeless image -> buffer -> image path needs transfer-write ->
   transfer-read synchronization on the intermediate buffer. Order partial
   clears before overlapping copies as well.
4. Transition copied textures to `SampledImage`, not attachment read/write.
   Include vertex texture sampling in this layout's stage scope and invalidate
   texture descriptors if their declared image layout changes.

These are API-level correctness fixes. Their contribution to the reported
visual symptoms has not yet been measured on the device. There are no new
queue-idle waits, CPU readbacks, or forced tiled/F16 copies.

References:

- https://docs.vulkan.org/guide/latest/synchronization_examples.html
- https://docs.vulkan.org/spec/latest/chapters/synchronization.html

## Deliberately unresolved paths

- The 1440-vs-720 request could be a valid 32-bit/64-bit byte alias. Current
  bounds checks compare pixel widths before the typeless conversion and reject
  partial typeless surfaces. Without the requested/stored guest formats, it is
  not established that this particular lookup is such an alias. The new
  `partial-typeless` records supply those missing values. Do not remove the
  bounds guard blindly: it also prevents out-of-bounds Vulkan copies.
- Generic cast copies calculate sizes using guest bytes per pixel. Expanded
  host formats (notably U2F10F10F10) require separate conversion semantics, not
  merely a larger intermediate buffer. The diagnostic logs both sizes.
- Tiled/swizzled sub-address lookup currently uses a linear row-offset formula;
  nonzero offsets need layout-specific evidence before changing it.
- `feedback-viewport` detects a direct sampled view of the current attachment.
  Cross-render-pass barriers cannot make arbitrary same-pass texture feedback
  correct; this requires a separate investigation if observed.
- Reusing the same guest address with a different format recreates the cached
  image. Whether the game expects preservation across a specific transition
  needs a scene-correlated trace.
- Surface misses can lead to CPU-backed texture upload. Hash-based CPU texture
  invalidation cannot itself make GPU-only writes appear in guest memory.
- The existing tiled mip and swizzled sampler changes are retained. MSAA
  emulation, surface clip, tone mapping, and shader numerical output have not
  been verified by a GPU capture.

## New diagnostics and device test

`iOS RT lookup` logs the final lookup path, count, frame/scene, guest address,
dimensions, layout type, guest/Vulkan formats, guest/host bytes per pixel,
stride, gamma, mip count, and resolution scale. Its paired `iOS RT source`
record includes the cached surface, address delta, guest/host dimensions,
tiling, layout, dirty flag, last-rendered frame, and current-attachment status.

All exit paths are covered, including no matching surface and dirty surfaces.
Each path logs its first four occurrences and subsequently at most once per
300 frames. Counters reset on surface-cache cleanup, so boot or a prior game
session cannot exhaust the diagnostic budget. A `no-surface` result is normal
for ordinary CPU-loaded textures and is not intrinsically an error.

Keep the same settings for the comparison. Capture one session covering the
menu, settings, journal, and the same 3D scene, with timestamps/screenshots.
Check Chinese, controller, touch, scene brightness, UI legibility, and clean
exit. Return the complete new log with its build identifier. A successful IPA
build proves compilation/packaging only, not correct rendering or stability.
