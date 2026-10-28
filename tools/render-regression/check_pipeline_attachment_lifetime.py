#!/usr/bin/env python3
"""Consume the production pipeline descriptor after its attachment branch.

Use real Vulkan-Hpp structures: setAttachments stores a pointer, not a copy.
ASan must reject the old branch-local attachment, not merely validate values
inside that branch as the earlier material policy test did.
"""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / 'vita3k/renderer/src/vulkan/pipeline_cache.cpp').read_text()
start = source.index('    vk::PipelineColorBlendStateCreateInfo color_blending{};')
end = source.index('\n#ifdef VITA3K_PLATFORM_IOS', start)
body = source[start:end]
include = Path(os.environ.get('VULKAN_HEADER_ROOT', '/usr/include'))
if not (include / 'vulkan/vulkan.hpp').exists():
    include = root.parent / 'analysis/host-deps/root/usr/include'
assert (include / 'vulkan/vulkan.hpp').exists(), 'Install libvulkan-dev or set VULKAN_HEADER_ROOT'

code = r'''
#define VULKAN_HPP_NO_STRUCT_CONSTRUCTORS
#include <vulkan/vulkan.hpp>
#include <array>
#include <cassert>
constexpr uint32_t SCE_GXM_PROGRAM_FLAG_OUTPUT_UNDEFINED=1;
constexpr uint32_t SCE_GXM_COLOR_BASE_FORMAT_F32F32=11;
struct Program {uint32_t program_flags=0; bool is_frag_color_used()const{return false;}};
struct State {
 struct {bool preserve_packed_rg32;} features;
 struct {bool wideLines;} physical_device_features{true};
};
__attribute__((noinline)) void check(bool disabled,bool no_output,bool interlock,
 bool packed,bool rg32,bool blend_enabled,vk::ColorComponentFlags write_mask) {
 State state{{packed}};
 struct {uint32_t color_base_format;} record{rg32?11u:3u};
 Program program{no_output?1u:0u};auto gxm_fragment_shader=&program;
 bool is_fragment_disabled=disabled,use_shader_interlock=interlock;
 bool support_coherent_framebuffer_fetch=false;
 struct {vk::PipelineColorBlendAttachmentState blending;uint32_t texture_count=0;} fragment_program;
 fragment_program.blending={
  .blendEnable=blend_enabled?VK_TRUE:VK_FALSE,
  .srcColorBlendFactor=vk::BlendFactor::eSrcAlpha,
  .dstColorBlendFactor=vk::BlendFactor::eOneMinusSrcAlpha,
  .colorBlendOp=vk::BlendOp::eAdd,
  .srcAlphaBlendFactor=vk::BlendFactor::eOne,
  .dstAlphaBlendFactor=vk::BlendFactor::eZero,
  .alphaBlendOp=vk::BlendOp::eReverseSubtract,
  .colorWriteMask=write_mask
 };
 const auto original=fragment_program.blending;
 struct {uint32_t texture_count=0;} vertex_program;
 std::array<std::array<vk::PipelineLayout,1>,1> pipeline_layouts{};
 vk::PipelineVertexInputStateCreateInfo vertex_input{};
 vk::PipelineInputAssemblyStateCreateInfo input_assembly{};
 vk::PipelineRasterizationStateCreateInfo rasterizer{};
 vk::PipelineMultisampleStateCreateInfo multisampling{};
 vk::PipelineDepthStencilStateCreateInfo ds_info{};
 vk::PipelineShaderStageCreateInfo shader_stages[2]{};
 uint32_t shader_stage_count=2;vk::RenderPass render_pass{};
''' + body + r'''
 // Consume through the same nested pointer which createGraphicsPipeline
 // reads, after dynamic_info, viewport and pipeline_info have been built.
 const auto& info=*pipeline_info.pColorBlendState;
 assert(info.attachmentCount==1 && info.pAttachments);
 const auto actual=*info.pAttachments;
 const bool muted=disabled||no_output||interlock;
 auto expected=original;
 if(muted)expected={.blendEnable=VK_FALSE,.colorWriteMask=vk::ColorComponentFlags()};
 else if(packed&&rg32)expected.blendEnable=VK_FALSE;
 assert(actual==expected);
 assert(actual.blendEnable==VK_TRUE||actual.blendEnable==VK_FALSE);
 assert(fragment_program.blending==original); // never mutate shared guest state
}
int main(){
 for(bool disabled:{false,true})for(bool no_output:{false,true})
 for(bool interlock:{false,true})for(bool packed:{false,true})
 for(bool rg32:{false,true})for(bool blend:{false,true})
 for(uint32_t mask=0;mask<16;mask++)
  check(disabled,no_output,interlock,packed,rg32,blend,vk::ColorComponentFlags(mask));
}
'''
with tempfile.TemporaryDirectory() as tmp:
    cpp = Path(tmp) / 'test.cpp'
    exe = Path(tmp) / 'test'
    cpp.write_text(code)
    subprocess.run(['c++', '-std=c++20', '-O1', '-g', '-fsanitize=address,undefined',
                    '-fsanitize-address-use-after-scope', '-fno-omit-frame-pointer',
                    '-I' + str(include), str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True,
                   env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0'))
print('PASS: 1024 production pipeline attachment cases, real Vulkan-Hpp pointer lifetime and all blend fields (ASan/UBSan)')
