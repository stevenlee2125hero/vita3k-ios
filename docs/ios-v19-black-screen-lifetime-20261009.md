# v19 black screens: dangling pipeline attachment descriptor

## Device evidence

The supplied `tsubomi(5).log` identifies the v19 merge `0b9062a`. It records
both Golden Abyss PCSD00001 and Undertale PCSG01112. The user reports Golden
Abyss renders only red menu text, and Undertale renders no game image.
Both titles progress through guest execution and pipeline compilation.
Every logged enabled fragment pipeline has `blend=28 write_mask=0x1`, while
disabled/no-output pipelines have `blend=0 write_mask=0x0`. VkBool32 blend
enable must be VK_FALSE (0) or VK_TRUE (1), so 28 is invalid input.
The log ends with user shutdown rather than ErrorDeviceLost or a fatal signal.

## Proven source defect

Commit 5a1a4bb3 introduced an attachment copy declared inside the `else`
branch of `PipelineCache::compile_pipeline`. Vulkan-Hpp `setAttachments`
retains the supplied object's address; it does not copy the attachment.
The copy's lifetime ended at the branch closing brace. Creation of layout,
dynamic-state, viewport and graphics-pipeline structures then occurred
before `createGraphicsPipeline` consumed the dangling attachment pointer.
This defect affects ordinary float pipelines as well as the experimental
integer path. Disabling integer output in v19 therefore did not remove it.

The new regression extracts the actual production code from color blending
through graphics pipeline descriptor setup, uses real Vulkan-Hpp types, and
reads all seven blend fields through `pipeline_info.pColorBlendState` after
the branch has ended. The unmodified v19 code fails under AddressSanitizer:
`stack-use-after-scope`, read of 32 bytes in local variable `blending`.
The fixed code passes 1024 combinations of fragment disable, undefined
output, interlock, packed policy, surface format, blend enable and all sixteen
write masks. Shared guest blend state is also checked for mutation.

This is a reproduced host memory-lifetime defect with matching device
descriptor corruption, not a diagnosis based solely on a black screenshot.
It may explain the earlier Metal validation abort/device loss, but the
previous reports did not include the specific Metal assertion text.

## v20 correction

Keep one attachment copy in function scope until synchronous Vulkan pipeline
creation returns, apply disabled/integer policies to that copy, and bind it
once after branch selection. Retain float attachments, synchronous iOS
pipeline compilation, resolved title dispatch, Chinese/import/trophy/JIT
fixes and exact Golden Abyss crops. Increment shader/pipeline cache version
to 20 so malformed v18/v19 pipeline state is not reused from disk.

The earlier material policy test consumed blend values inside the branch,
and its stub never modeled Vulkan-Hpp's retained pointer. It consequently
missed the defect. The new lifetime test covers the actual consuming scope
and runs in CI with ASan/UBSan and real Vulkan headers.

Golden Abyss packed material color correctness remains a separate issue.
Removing the shared black-screen defect does not establish correct character
materials on an Apple GPU. Full-core IPA construction and device verification
must not be described as interchangeable.
