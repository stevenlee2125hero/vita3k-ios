# Golden Abyss v18: device shader evidence and typed packed materials

Device feedback on c7124fd1 / IPA merge 0da0afc confirms Undertale is playable.
Golden Abyss PCSD00001 still has purple material noise, dark scenery and menu
corruption. The v17 crop policy was **not active** in either the initial launch
or the LoadExec relaunch: the log has no Golden policy marker and continues
using viewport lookups.

## Confirmed integration defect

`setup_game_launch` calls `set_app_info`, which resolves the selected library
entry to `emuenv.io.title_id`. `app::late_init` instead passed the legacy
`emuenv.app_path`, cleared by teardown and never populated by that launch path.
The renderer now receives the resolved title ID. The regression test executes
the production identity assignments and dispatch with an empty legacy field,
a renamed installation directory and a Golden -> Undertale -> Golden sequence.

## Shader evidence

User shaderlog ZIP contains 482 GXP/DSM pairs. Parsing the production GXP header
layout found 422 fragment variants: 279 F16x4, 130 U32x2 and 13 F32x1.
The U32x2 variants represent 28 distinct GXP programs. Their USSE instructions
pack normalized color bytes with VPCKU8F16 and signed normal bytes with
VPCKS8F16, then move the two raw words to output. The log shows RG32F 720x408
surfaces subsequently sampled as RGBA8 1440x408 at +0 and SNORM at +4.
A float render attachment can interpret some packed words as NaNs/subnormals,
so later byte-preserving copies cannot repair bits already changed at export.
This is a strong causal hypothesis, not a verified A16 visual result.

## Changes

Only PCSD00001 on iOS enables `preserve_packed_rg32`. Its RG32 framebuffer uses
R32G32Uint; normal framebuffer output and mask output use matching unsigned
vectors with bitcasts, not numeric integer conversion. Programmable framebuffer
fetch also uses an unsigned subpass input and bitcasts back into guest registers.
Floating storage-image interlock is disabled for this policy; typed subpass fetch
is used instead. Fixed-function blending is disabled for the integer attachment,
which Vulkan/Metal cannot blend; USSE framebuffer fetch is retained.
Ordinary sampled RG32 textures still use a float destination populated by the
existing byte copy. Existing +0/+4 alias admission and bounds remain unchanged.

The previous global integer experiment did not provide this complete typed
framebuffer-fetch contract. Its Metal assertion has no diagnostic text in the
uploaded IPS, so its precise assertion condition remains unproven.

Undertale and other titles keep the previous float attachment/output behavior.
The new feature bit is included in shader variants and cache version is 18.
Import, trophy bypass, CPU/JIT, LoadExec and Chinese text behavior are unchanged.

## Validation scope

Production output/fetch/mask/blend snippets, actual title identity dispatch,
feature-key separation, transient fallback and copied async record bounds are
checked under ASan/UBSan with typed builder/hash stubs. BC decoding, U2F10 upload,
GPU retirement stubs and +4 alias/copy ordering tests are retained.
These CPU tests cannot establish that the game renders correctly on the iPhone.
The final IPA must pass full iOS compilation and package/source verification,
then the remaining visual result requires device validation.

## Real shader conversion follow-up

A standalone host audit compiled the production shader translator and pinned
SPIR-V builder/SPIRV-Cross sources. The 482 dump variants contain 77 unique
fragment GXP programs. Each was converted with float/integer RG32 attachment
policies and normal/mask output: 308 SPIR-V modules and iOS MSL source variants.
All 308 modules passed `spirv-val --target-env vulkan1.0` after fixing the
following pre-existing uniform-copy defect. Texture format hints were default
RGBA8, not a replay of every recorded runtime sampler binding. No Apple Metal
compiler or A16 GPU execution was performed.

The initial conversion asserted in `copy_uniform_block_to_register` for actual
material GXP adb5702727ae8ca52248f169cc0d93e0ac2c09d9ad9b65db5bd1e9888504e5b7,
even with the float baseline policy. Unaligned uniform `VectorShuffle` used
`vector<Id>` for component selectors. Selector zero became invalid SPIR-V ID 0.
Selectors now use `IdImmediate` with `isId=false`; only the two vector sources
are IDs. A separate production-function regression checks 56 alignment/extent
cases and preservation of neighboring registers under ASan/UBSan.

This fixes a real shader-construction defect, but does not by itself establish
that it caused the observed release-build purple materials.
