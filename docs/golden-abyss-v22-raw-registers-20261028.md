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
Without float-controls guarantees, these are not a bit-preserving storage
contract for arbitrary NaN/subnormal payloads. This is a concrete gap in the
previous contract, not proof that the A16 driver actually corrupted those words.

This candidate uses uint4 input, temporary, internal and output banks only for
Vulkan fragment variants targeting packed RG32. Numeric operations still use
float values via bitcasts at the instruction boundary. Integer moves remain
integer, including masked/cross-vector stores. Packed byte/half/FX10 helper
interfaces use uint words under the existing title policy. Non-packed variants
retain float banks. Uniform registers remain on the existing float path.
The final packed export loads raw UINT32 words without normalization.

Retain v20's proven blend attachment lifetime repair, v21's integer attachment
and exact alias/crop rules, MaiDump launch, Chinese text and synchronous pipeline
compilation. Shader cache advances to 22 to invalidate v21 shader code.

Tests must include the existing suites plus real glslang generation of the
production utility functions, spirv-val and SPIRV-Cross MSL translation. The
latter checks type correctness, not Apple GPU results. iPhone A16 visual
acceptance remains outstanding until the user tests the complete IPA.
