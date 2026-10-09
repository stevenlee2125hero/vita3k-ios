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
policy. No current Undertale runtime log was supplied with this feedback;
the black screenshot cannot distinguish pipeline compilation, trophy/HLE
waits, loader failure, JIT failure or presentation failure. Obtain the v18
`tsubomi.log` before declaring its root cause or the regression fixed.
Golden Abyss purple material corruption remains unresolved on-device.
