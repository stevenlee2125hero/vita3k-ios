# Golden Abyss v24: corrections on the v22 route

This build responds to the review of the user's v22 IPA, SHA256
`a7642b13218ee8e28d89c44484e92124bf87e42919effa6eed94799dea803313`.
It is a continuation of that Tsubomi-derived route, separate from the independent
full-Plus project. The source parent is `0db166640dd7bc90ae9e5433ffc440ce114afd05`,
which already contains the reviewed corrections and their regression tests.

Relative to v22:

- VLOG/FLOG lower to Log2 and VEXP/FEXP to Exp2. Existing NaN policy is retained.
- Uniform-buffer declarations preserve container size and SA base mappings;
  missing mappings may be filled without discarding existing valid ones.
- Existing PCSD00001 raw integer register banks, packed material attachments,
  exact alias/crop handling, native 1x resolution, synchronous pipelines,
  Chinese language and game-loading/JIT paths remain on the v22 route.
- Shader cache generation is 24, so v22/v23 translations are not reused.
- The application displays Tsubomi GA v24, version 0.47.24 / build 4724.
  The bundle identifier remains org.vita3k.experimental.ios for this update.
- GoldenAbyss-Provenance.txt records the exact build commit, v22 build source,
  correction source, MoltenVK 1.4.1 and cache generation. Startup logs include
  the exact commit. CI verifies those markers in the actual executable and IPA.

The ALU/Uniform code and numerical tests were authored in the preceding v23
commits; v24 does not claim those as newly discovered fixes. The independent
Plus IPA is not substituted for this package. No game's contents are bundled.

Validation gates: production complex-ALU lowering executes on software Vulkan;
uniform-container tests cover declaration ordering and missing mappings;
existing renderer regressions cover packed registers, formats and lifetimes;
generated MSL compiles with Apple's iPhone Metal compiler. Full arm64 linking,
unsigned packaging, CRC, canonical shader bytes, UUID and commit identity must
pass before an IPA is delivered. Software tests do not prove A16 GPU behavior.

There is still no proof that either correction is the sole cause of magenta
characters. The previous static game audit found no changed effective Uniform
mapping in its sample; that repair is a conditional correctness improvement.
On-device installation, JIT, materials, scene changes, controls, repeat launch
and sustained performance require acceptance on the iPhone 15 Plus.

For comparison, use the same game version, save and scene as the v22 test.
Confirm `iOS compatibility v24` and the build commit in tsubomi.log. If rendering
is still wrong, retain the complete startup-to-scene log, matching screenshot,
shader hashes/render-target state and any .ips report; keep licenses private.
