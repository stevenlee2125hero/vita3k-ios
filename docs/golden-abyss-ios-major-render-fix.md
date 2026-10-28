# Golden Abyss iOS — major character and menu rendering release

## Verified baseline
- PCSD00001 MaiDump APP_VER=01.00; Apple iOS Vulkan.
- Keep rendering changes through 8c1b678 (restored in e85a6d3), including the narrow RG32F→RGBA8 render-target alias.
- Chinese subtitles, MaiDump LoadExec and scenery render correctly.
- User screenshots of 2177a62 show character skin/clothing as magenta/cyan/green noise, black patches and stripes; menu colors are also unreadable. The game **is not frozen**.
- ed6c4c8 fixes partial staging buffer initialization/bounds but is **not device validated**.

## Work items
1. Trace character texture uploads and source GXM formats (tiled, swizzled, compressed), decoded Vulkan formats, row pitch and texture cache invalidation.
2. Independently trace menu UI render-targets, swizzle, sRGB views, alpha and blend paths; do not assume the same cause as characters.
3. Audit surface-cache cast key, scene timestamp reuse, guest vs host texel footprints and source/destination byte ranges.
4. Add focused tests for texture format/stride/alias conversion and partial staging-copy edge cases.
5. Keep diagnostic logs bounded and avoid introducing GPU stalls.

## Single device validation gate
Do not request another user IPA test until there is a coherent set of implementation fixes, passing formatting and arm64 upstream-core IPA build. Clearly identify what is changed and what remains unverified.

## Acceptance
- Characters display recognizable natural skin and clothing colors, without stripes/black patches.
- Menus are legible.
- Background, gameplay, traditional Chinese text and startup are preserved.

## Evidence needed
A device Vulkan log from a scene exhibiting corruption can establish whether rejected typeless casts, wrong texture decode or shader material inputs are involved. Screenshots alone do not establish root cause.
