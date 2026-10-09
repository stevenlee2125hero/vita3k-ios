# Golden Abyss v21: activate the complete packed-material contract

## Device evidence and scope

The user confirmed Undertale works in v20. `tsubomi(6).log` identifies source
`5a2c7ba` and legal pipeline blend fields; the new Golden Abyss screenshots
still show purple character materials and a noisy ammo HUD. The v20 descriptor
lifetime fix therefore remains essential, but did not solve material corruption.

The device log observes the same guest bytes at `0x60A9FEC0` as an RG32F
720x408 render target (5760 bytes/row) and RGBA8 1440x408 textures. The normal
texture starts at `0x60A9FEC4`, four bytes later, and uses signed normalized
channels. Original guest fragment programs pack color/normal into 32-bit words.
Floating-point attachment export can change raw patterns that represent NaNs or
subnormals. This is a concrete remaining cause to test, not a device-proven fix.

## Candidate behavior

Only the iOS title `PCSD00001` now activates the previously implemented packed
RG32 contract. The flag is reset on every launch, including transitions to
Undertale and unrelated titles. Non-Golden RG32 targets keep the float contract.

The complete active path consists of:

- RG32 material attachments and render passes use `R32G32Uint`.
- Normal and mask fragment outputs use integer types with bitcasts, without
  numerical float-to-integer conversion. Framebuffer input reads integer words
  and bitcasts back to the emulated register bank.
- The float storage-image/interlock path is disabled for this title. Fixed
  numeric blending is disabled only on its packed RG32 attachment. The v20
  function-scope blend descriptor lifetime fix remains in place.
- RGBA8 UNORM/SRGB color and SNORM normal aliases use buffer reinterpretation,
  exact guest crops, byte-exact row pitches and the +4-byte offset. Integer to
  float views also use the buffer route; only identical formats use direct image
  copies. No integer image view is passed to a float sampler.
- Shader and pipeline cache version advances from 20 to 21 so old generated
  shaders cannot mask this behavioral change. Import, Chinese fonts, MaiDump
  launch, JIT, and Undertale bypass code are not changed.

This enables a coordinated renderer/shader/cache policy, rather than another
change to logging or a collection of unrelated experimental workarounds.

## Validation performed before submission

All eight renderer regression scripts and both import regression scripts pass.
The attachment lifetime test uses real Vulkan-Hpp types with ASan/UBSan and
checks 1024 combinations, including the active integer blend policy. Title
selection tests cover Golden -> Undertale -> Golden and unrelated titles.

Alias regression coverage now includes integer/float equal-footprint copy
routing and byte payloads resembling quiet/signaling NaNs, infinities, subnormals,
negative zero and arbitrary packed words, at offsets zero and four. These are
host copy models using the production predicate/offset, not GPU replay.

The actual production GXP translator generated 308 SPIR-V/MSL variants from
77 unique uploaded Golden fragment programs: float/integer paths and normal/mask
variants. All 308 validate with `spirv-val --target-env vulkan1.0`. MSL generation
succeeds; this does not execute Apple's Metal compiler or the A16 GPU.

Five review areas: title isolation and launch; attachment/output/fetch type
agreement; raw copy/crop bounds and barriers; pipeline lifetime and cache
invalidation; import/runtime regression and packaged binary identity. The final
upstream-core iOS build and binary/package verification must also pass before
this candidate is delivered.

## Acceptance still requiring the device

No host check proves the purple material issue is eliminated. The single
candidate test must check Golden's character, ammo HUD and notebook/menu,
Traditional Chinese and a playable scene, plus a short Undertale launch. Use
v21's startup marker to identify this candidate, and retain its log if any
corruption or startup failure persists. No zero-defect claim is made.
