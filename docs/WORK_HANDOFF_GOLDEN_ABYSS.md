# ChatGPT Work handoff — Vita3K iOS / Uncharted: Golden Abyss

Date: 2026-10-08. This is a handoff for an autonomous, substantial coding task, not a request for another status update.

## Repository and branches
- Repository: https://github.com/stevenlee2125hero/vita3k-ios
- Active development branch: `gpt6-golden-abyss-render-audit`
- Draft PR: https://github.com/stevenlee2125hero/vita3k-ios/pull/1
- Original stable branch: `fix-uncharted-golden-abyss`, stable starting commit `578a73f1ac7ba1fb15d9d3bb1506b7520ef51be7`.
- Known preferred scene-rendering baseline: `8c1b6780207c004c936dbc9be618a67f475e7d0e`; later commits contain protective fixes but are NOT yet confirmed to solve corruption.
- Latest render behavior change: `3ac052a76e963b32a4b9b61d54fd3c358cbd3b92` (refresh render-target feedback snapshots within same scene). Verify CI and behavior.

## User environment and exact symptoms
- iPhone with Apple A16 GPU, Vita3K iOS, game `Uncharted: Golden Abyss` title ID `PCSD00001`, MaiDump, `APP_VER=01.00`.
- Game boots and is playable; jungle, terrain, temples, mountains and other scene geometry look generally normal.
- Character skin/clothes show severe purple/magenta/cyan noise, stripes and black patches. Menus sometimes have unreadable colors. Traditional Chinese subtitles work.
- Do NOT misdiagnose as a general game crash or frozen virtual controller.
- Existing MaiDump LoadExec boot and Traditional Chinese loading/subtitle fixes are working. **Do not regress these**.
- Firmware/font reinstall is not a plausible primary explanation for character material corruption.
- The user strongly requests **one substantial release and one device test**, not repeated tiny IPA installations.

## Work objective
1. Investigate actual rendering root cause in texture decoding/upload and GPU sampling: GXM texture formats, compressed/tiled/swizzled layouts, channel order, gamma/sRGB, texture cache and Vulkan render-target-as-texture aliasing, image views, shader sampling, and feedback copies. Follow evidence rather than randomly adding integer guards.
2. Trace concrete code paths used for character materials and UI. Check swizzle and view caching keys, host-vs-guest row pitch and format equivalence, staging buffer copies and barriers, synchronization and render-target lifetime. Add narrowly scoped diagnostics or reproducible automated tests.
3. Make substantive fixes, run format checks and build the **upstream-core iOS IPA**, inspect CI failures, and iterate within the same Work task. Do not confuse tiny `Build unsigned iOS IPA` fixture with playable `Build upstream-core iOS IPA`.
4. Avoid breaking boot, subtitles, game environment or other games. Keep changes reviewable and explain risk/performance tradeoffs.
5. Once code and automated checks are ready, provide the single playable IPA GitHub Actions artifact URL and precise one-time device validation instructions. State honestly that device-only visual behavior remains unverified until user tests.

## Current implementation and history
- Most work is in `vita3k/renderer/src/vulkan/surface_cache.cpp`.
- `8c1b678`: guard incompatible typeless casts; restored by `e85a6d3`.
- `2177a62`: bounded iOS diagnostics. User installed this playable IPA and supplied screenshots confirming environment good, characters severely corrupted.
- `ed6c4c8`: partial copy bounds and staging-buffer clear.
- `fc1a70d`: `docs/golden-abyss-ios-major-render-fix.md` tracking plan.
- `a01d9ea`: 64-bit surface size.
- `65bb83d`: cache address start/end bounds.
- `d5e5d27`: reject offset aliases for nonlinear tiling.
- `0b45157`: align staging fill size to four bytes.
- `ae62dfa`: only direct-copy exact matching host Vulkan formats.
- `a1de7e4`: 64-bit packed row calculation.
- `502f439`: 64-bit overlap address.
- `fc57388`: validate source host row pitch.
- `2d46532`: 64-bit subview origin checks; format and full upstream-core build succeeded.
- `b311ed5`: comments documenting typeless row-span invariant; NOT a behavior fix.
- `3ac052a`: actual change to feedback snapshot cache reuse, not yet device validated.
- Existing rejection diagnostics cap logs to avoid flooding.
- Previous build known playable artifact from `2177a62`: https://github.com/stevenlee2125hero/vita3k-ios/actions/runs/37730003906/artifacts/11530500385 ; this is **not** a final fix.
- Review GitHub Actions for current artifact after final commit.

## Critical engineering cautions
- Do not claim purple character corruption is solved merely because CI compiles.
- Do not request testing every small patch.
- The current cache cast lookup compares crop coordinates/dimensions, guest base format, Vulkan format and scene timestamp; investigate whether component swizzle or other state must be included. The direct viewport path already applies `vkutil::color_to_texture_swizzle`, while casted image view creation may have separate mapping behavior.
- Distinguish byte-preserving format reinterpretation from pixel format conversion. Row equality and block sizes alone may be insufficient for valid host copies.
- Existing scene-rendering baseline is important; use comparisons to isolate regressions.
- User is in China and uses an iPhone; give accessible links and concise Chinese updates.

## Delivery acceptance
- Significant code changes addressing a plausible proven corruption cause.
- Format check and real upstream-core IPA build passing.
- No regressions in MaiDump launch and Traditional Chinese.
- One clear candidate build, with direct artifact link, short test checklist, and explicit remaining uncertainties.
- Report what was *actually* done, not promises of unattended work.

Proceed with development and GitHub commits on `gpt6-golden-abyss-render-audit`; do not wait for the user to type '开发' after each small step.
