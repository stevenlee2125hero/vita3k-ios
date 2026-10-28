# Golden Abyss v22: raw shader register transport (candidate)

The user's installed IPA SHA256 is
`8f4b23842cf0d3b89cbe0a64ed65df87e2cd07084dc2398bb1809328af8ad455`.
It is exactly v21. The user reports purple character rendering persists.
Remote branch checked at 13580e8f00b1cbec07da98530043ae69334ce42c.

Read-only inspection of the user's local MaiDump gamedata finds fragment
programs with U32 output and two components, consistent with the previously
logged RG32 material buffer. No game assets are committed or uploaded.

V21 protects the final attachment but transports packed words through float
private-memory register banks and float pack/unpack function boundaries first.
This candidate makes arbitrary packed words explicitly integer throughout those
paths, avoiding dependence on special floating-value handling in the backend.
This is defensive transport hardening, not a demonstrated A16 corruption cause.
In particular, Vulkan requires bit-preserving operations (including float loads,
stores and copies) not to flush denormals; the mere presence of float storage is
not evidence of denormal loss. Special NaN handling and actual Metal lowering
must be distinguished from that requirement. See the normative precision rules:
https://docs.vulkan.org/spec/latest/appendices/spirvenv.html#spirvenv-precision
No device trace currently proves that this transport change fixes the symptom.

This candidate uses uint4 input, temporary, internal and output banks only for
Vulkan fragment variants of the title. Both the RG32 producer and the
RGBA8 lighting consumer use byte/half packed input registers, so restricting
raw banks to the producer would leave the sampling half unprotected. Numeric operations still use
float values via bitcasts at the instruction boundary. Integer moves remain
integer, including masked/cross-vector stores. Packed byte/half/FX10 helper
interfaces use uint words under the existing title policy. Other titles and vertex variants retain float banks. Uniform registers remain on the existing float path.
The final packed export loads raw UINT32 words without normalization.

Retain v20's proven blend attachment lifetime repair, v21's integer attachment
and exact alias/crop rules, MaiDump launch, Chinese text and synchronous pipeline
compilation. Shader cache advances to 22 to invalidate v21 shader code.

Tests must include the existing suites plus real glslang generation of the
production utility functions, spirv-val and SPIRV-Cross MSL translation. The
latter checks type correctness, not Apple GPU results. iPhone A16 visual
acceptance remains outstanding until the user tests the complete IPA.

The iOS Vulkan PCSD00001 profile also enforces native (1x) resolution at renderer
configuration time. The existing observed RG32/RGBA8 raw alias path explicitly
rejects upscaling, which otherwise falls back to stale CPU data. This does not
mutate the user's saved graphics setting; unrelated titles retain that setting.

## Completed build and package verification

All final-head renderer, import, format and both iOS build workflows succeeded.
The delivered package is from **Build upstream-core iOS IPA**, not the bootstrap
fixture. No iPhone visual result has been received for this candidate.

- Development code: `85bf3db581dad187c38ac36f5d6c805d94eed95f`.
- PR merge build source: `2d7dd0c5c84bf2e8fff0cc3264560a8a395a773a`.
- Both have source tree `26fd6c2dd5a4968ae108622d990b8cffed33a17b`.
- Full build: https://github.com/stevenlee2125hero/vita3k-ios/actions/runs/40665178426
- Artifact 12809622384, `Vita3K-upstream-core-iOS-2d7dd0c5c84bf2e8fff0cc3264560a8a395a773a-unsigned`.
- Artifact ZIP SHA256: `45c3106360e0e68840fa4264fe7349895207c8e7f878c4340286328ebdde3d6f`.
- IPA SHA256: `a7642b13218ee8e28d89c44484e92124bf87e42919effa6eed94799dea803313`.
- IPA bytes: 19,522,283. arm64 executable: 59,258,088 bytes.
- Mach-O UUID: `cd27b9cd-24e0-3629-9e6e-9cb13472add2`; iPhoneOS platform;
  minimum iOS 26.0; SDK 26.2.
- All 22 bundled shaders match canonical Git blob bytes. Comparing Windows
  working-tree text bytes directly is invalid because checkout uses CRLF.
- Artifact digest, outer/inner ZIP CRC, source/v22/native-profile markers and
  complete-core identity verified after download. The IPA was not modified.
- Rendering checks: https://github.com/stevenlee2125hero/vita3k-ios/actions/runs/40665178402
- Format: https://github.com/stevenlee2125hero/vita3k-ios/actions/runs/40665178480
- Import: https://github.com/stevenlee2125hero/vita3k-ios/actions/runs/40665178420

The new register test validates 8,640 production utility code-generation cases
with real pinned glslang, spirv-val and SPIRV-Cross. It does not execute those
operations on A16 or compile their MSL with Apple's runtime compiler. Earlier
builder/model tests retain their explicitly documented limitations.

Read-only game metadata inspection found the separate VPK is category `gp`
(APP_VER 01.03), while the NoNpDrm directory has `app` category `gd` 01.00 and
`patch` category `gp` 01.03. Do not infer an independently installable base game
from the VPK filename. No game content was changed or uploaded.
