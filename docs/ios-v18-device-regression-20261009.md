# v18 rejected on device; v19 stability candidate

The user reports Golden Abyss crashes and Undertale shows a black screen in
the delivered v18 IPA. Treat this as a failed release, not a visual success.

The report `Vita3K-iOS-2026-10-09-130218.ips` matches the delivered executable
UUID `c3eab0e8-c16e-3ed3-ba7a-7fb7759d3a5b`. Faulting thread 5 aborts in
`validateWithDevice` / `MTLRenderPipelineDescriptorInternal`, reached through
`MVKRenderPipelineCompiler`. It is a Metal descriptor validation failure,
not an unrecognized binary, Jetsam termination or demonstrated CPU/JIT fault.
The IPS has no assertion message. The exact invalid descriptor condition is
therefore not established. The prior host SPIR-V validation did not cover
Apple pipeline construction and did not establish device compatibility.

## Corrective scope

- Disable the experimental packed integer attachment policy on every iOS
  launch. Float output, framebuffer fetch and render attachments return to
  the earlier contract. Typed experimental implementation is retained but
  no title enables it.
- Retain resolved SFO title dispatch and exact Golden Abyss material crops.
  These were missing from the earlier working launch path.
- Force synchronous pipeline compilation on iOS at the setter, including
  settings applied before initialization and changes during a session.
  The existing workers publish module and pipeline handles to readers without
  synchronization; deferred draws are also dropped while compilation runs.
  This is a protective policy, not proof that either issue caused this
  Undertale black screen. Desktop asynchronous behavior is unchanged.
- Flush pipeline diagnostics before each Metal creation call, including
  shader hashes, surface/hint formats, mask stage, blend and write mask.
- Increment shader/pipeline cache version to 19; preserve the real uniform
  shuffle literal fix, import fixes, Chinese support, trophy bypass and JIT.

## Validation and remaining evidence

Run the seven renderer regressions and both import regressions, format checks
and the full upstream-core device build. The new async policy test executes
the production setter with real worker threads and a recording queue stub,
for iOS and desktop configurations, repeated settings, initialization and
teardown. Crop/title regression must prove the rejected integer path remains
disabled for Golden -> Undertale -> Golden launches.

First-use compilation can pause rendering longer with this synchronous
policy. The subsequently supplied `tsubomi(4).log` identifies Undertale
PCSG01112 on the rejected v18 binary. JIT allocation succeeds, the synthetic
trophy context initializes, audio files open and guest framebuffers advance.
At 13:04:14.939 the run ends with `vk::Queue::submit: ErrorDeviceLost` and
SIGABRT. Pipeline compilation uses four workers and the watchdog reports
zero completed pipelines. This narrows the failure to the GPU/render path;
it does not establish whether worker concurrency, a shader or another GPU
resource caused device loss. This log is not the Golden Abyss crash session.

The new Golden Abyss shader dump contains one vertex and one fragment
program. Fragment `4cd547a78d48677d0e5773bfac1ecd44a0d1c3ef7f73ded396f068ea68d21f2a`
has variant tag `FF00F85435F659E4`. Recomputing the production XXH64 variant
key matches F32F32_GR, normal output (not mask), feature mask 56 and sixteen
default U8U8U8U8_ABGR texture hints. Feature bit 5 therefore enables the
rejected integer path in this actual dump. Host translation of this fragment
produces `uint4 [[color(0)]]` with that path enabled and `float4 [[color(0)]]`
when disabled. All four normal/mask, integer/float SPIR-V variants validate.
This supports disabling the integer path but still does not identify the
Metal assertion's exact descriptor condition without its assertion text.

The v19 full upstream-core iOS build and all renderer, importer, format and
fixture CI checks succeeded. The downloaded IPA was checked for archive CRC,
SHA-256, arm64 device executable, source/version markers and all 22 bundled
shaders. Executable UUID is `09c2c640-e380-398a-830b-d342be6193da`.
These are build and host checks, not an A16 gameplay test.
Golden Abyss purple material corruption remains unresolved on-device.
