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


Follow-through audit of that conversion also found that generic swizzle/tile
processing retained the original 32-bit texel size after expanding to 64-bit
RGBA16F. The conversion now sets bpp=64 and bytes_per_pixel=8 so layout
processing preserves complete host texels. Guest bpp is restored at the start
of every mip/face, keeping source stride/advance calculations independent of
previous host expansion. The production-branch regression asserts the expanded
layout metadata as well as the decoded bytes. The first entry-only correction
b1c8435e is superseded before device delivery.

## Second device rejection: log-guided alias and feedback correction

The 23:23 session identifies the installed merge revision 2cf0659, corresponding
to candidate 6fb93d23. It still shows purple/cyan character noise and corrupt
menus. This candidate is rejected as a visual fix. The log has no packed F10
upload marker; the previous CPU-upload correction was not demonstrated to be
the relevant game path. Surface sync is disabled in the active configuration.

The actual log repeatedly records a GPU RG32F 720x408 render target at
0x60A9FEC0, stride 5760, sampled both as RGBA8 1440x408 at its base and as
RGBA8 SNORM 1440x408 at 0x60A9FEC4. The latter is rejected as partial-typeless
(48,945 occurrences by frame 2438), although its byte rows match exactly.
Reverting to guest memory when GPU readback is disabled cannot preserve the
rendered words. The alias admission now includes the observed aligned +4
SNORM view. The staging copy preserves raw words and row crossings, allocates
the additional four bytes and clears the uncopied terminal word.

The same session also logs thousands of feedback-viewport lookups on the active
F11F11F10 color attachment (including 128x64 crops of a 256x512 target). On iOS,
these now use distinct cropped snapshot images instead of sampling the bound
attachment. If any earlier pass has been recorded, both command buffers are
closed first: prior prerender, prior render, new snapshot prerender, new render.
This also covers macroblock code that already ended a render pass without
ending its command buffers. Scene timestamps advance after the split.

Depth/stencil is stored from the first pass and loaded after the first draw,
including subsequent macroblocks. The iOS fallback depth image no longer has
transient usage, preventing memoryless allocation from losing depth across
snapshot splits. Other platforms retain their previous feedback/depth behavior.

check_rt_alias_feedback.py extracts production alias admission, byte offset,
viewport selection and feedback split code. It checks +0/+4 UNORM/sRGB/SNORM,
rejects incompatible layouts/expanded formats, checks byte-distinct rows and
terminal padding for heights 1/2/408, and tests prior-draw/snapshot/next-draw
ordering for open and already-closed passes under ASan/UBSan. The prior three
regression suites also pass. These tests do not execute Metal and do not prove
the actual game's colors restored. A full upstream-core build is required.

Only the combined log-guided candidate is to be delivered after complete build
and self-audit; intermediate edits are not device-install requests.
