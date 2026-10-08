# Golden Abyss renderer candidate — 2026-10-08

Base: 2bb5c884 on gpt6-golden-abyss-render-audit.

## Changes and evidence

- Include the effective component mapping in cropped/cast surface cache identity.
  Previously two texture descriptors with identical crops/formats but different
  channel mappings returned the first immutable image view. This is a concrete
  wrong-color path, not proof that PCSD00001 hits it in every corrupted draw.
- Use the existing format/mapping-keyed sampled-view cache for presentation.
  `alternate_view` belongs to framebuffer linear/sRGB attachment switching and
  cannot also represent arbitrary presentation swizzles.
- BC2 and BC3 software color decoding always uses four colors, including when
  color endpoint 0 is less than or equal to endpoint 1. BC1 retains transparency.
  A black/white selector-3 block reproduces incorrect black vs expected 170 gray.
- Decode partial BC blocks into the actual output extent without overwriting
  a width*height allocation. Normal four-aligned cache uploads are unchanged.
- Align every staging copy region to lcm(4, host block size), with padding in
  the allocation estimate. This covers byte/two-byte tail mips and BC blocks.

## Validation

`python3 tools/render-regression/check_bc_decoder.py` compiles the production
BC decoder in isolation and passes BC1 transparency, BC2/3 endpoint-order tests,
and 567 format/extent cases under AddressSanitizer and UndefinedBehaviorSanitizer.
Leak checking is disabled because the local runner prevents process inspection;
address and undefined-behavior instrumentation remain enabled.

Changed C++ files were formatted; `git diff --check` passes.
The new regression workflow runs the same decoder test in CI.
The real upstream-core IPA workflow must complete before device delivery.

## Scope and remaining uncertainty

MaiDump launch, LoadExec, language/font loading, game files and controller code
are untouched. Their runtime behavior is still part of final device validation.
No local iOS SDK or A16 device exists here. Software BC fixes affect devices
without native BC support. Correct compilation alone does not establish that
purple characters are fixed. No game GPU capture/log was provided in this task.
The inherited feedback change records copies in prerender_cmd, which is submitted
before render_cmd; repeated copies therefore do not prove draw-level same-scene
feedback is synchronized. It is retained rather than pretending that refreshing
a cache entry resolves this separate scheduling issue.

One-time candidate validation: reuse current game/save/settings, inspect character
skin and clothing in the same jungle scene, open pause/settings/notebook menus,
confirm Traditional Chinese subtitles, then play through one scene transition.


## Self-audit follow-up

The initial candidate e6153789 compiled and packaged successfully (run
37785422118). A subsequent self-audit found two additional concrete defects:

- `destroy_surface` queued alternate_view for destruction but left its handle
  non-null in the reusable cache slot. It also retained old readback buffers,
  downscale images and swscale contexts. A replacement surface could therefore
  reuse a destroyed view, an undersized staging buffer or an old conversion
  layout. Retirement now clears the handle, retires associated framebuffers,
  defers GPU resource destruction, and resets all auxiliary resources/state.
- RGB24 surfaces use RGBA8 host texels. The readback staging allocation was
  sized from 3-byte guest rows although Vulkan writes 4-byte host texels.
  It now uses a 64-bit host footprint from the copy's pixel stride.

`check_surface_lifecycle.py` compiles the production retirement body with
recording GPU stubs and checks slot reuse, null/stale view rejection, deferred
resource retirement and six RGB staging sizes under ASan/UBSan. These are host
logic tests; they do not execute a Vulkan driver. The decoder tests still pass.
Initial artifact is superseded; only the follow-up candidate should be tested.


## Device rejection and packed-float upload defect

The user tested 2dec3141 and reported no improvement. Screenshots show dense
purple/cyan noise on the character while stone/vegetation and Chinese subtitles
remain legible; a menu view is extensively corrupted. This rejects that candidate
as a solution to the actual reported corruption, despite its passing host tests.

A subsequent texture-source audit found a concrete guest/host footprint defect:
`TextureCache::upload_texture` skipped U2F10F10F10 expansion when
`support_a2rgb10` was true. That capability describes integer UNORM
A2R10G10B10, not unsigned F10 floating-point components. Meanwhile Vulkan
`texture::translate_format` always chooses RGBA16F for U2F10F10F10. Thus raw
4-byte packed texels were uploaded with an 8-byte-per-texel Vulkan copy layout.
The copy reads beyond the region actually populated for that mip, including
neighboring/stale staging data. This is consistent with dense noise, but a
screenshot alone does not establish the game's exact descriptor/capability path.

Vulkan now always expands U2F10F10F10 into RGBA16F; OpenGL is unchanged.
`check_u2f10_upload.py` compiles the production selection branch and conversion
routine and checks both capability states and both alpha bit layouts with
known half-float values. The previous candidate fails the capability=true case;
the corrected branch passes 16 cases. An INFO-once marker records real use of
this conversion in a device log. The former decoder/lifecycle suites still pass.

This candidate needs a full upstream-core build and one device comparison.
If corruption persists, collect the existing Share log file output from the same
session; do not infer another root cause solely from screenshots. Packed-float
surface aliases and same-pass feedback remain separate unverified paths.
