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
