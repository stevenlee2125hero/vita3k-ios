#!/usr/bin/env python3
"""Check device-observed RT aliases and production feedback scheduling logic."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
s = (root / 'vita3k/renderer/src/vulkan/surface_cache.cpp').read_text()
a = s.index('    const bool byte_equivalent_linear_alias =')
predicate = s[a:s.index(';', a) + 1]
a = s.index('        if (is_same_image && context->has_rendered_in_recording)')
feedback = s[a:s.index('\n#endif', a)]
a = s.index('    bool can_use_viewport =')
viewport = s[a:s.index('    if (can_use_viewport)', a)]
a = s.index('            const vk::DeviceSize destination_offset =')
offset = s[a:s.index(';', a) + 1]
a = s.index('        const bool host_copy_compatible =')
copy_policy = s[a:s.index('            trace_color_lookup', a)]
ctx_source = (root / 'vita3k/renderer/src/vulkan/context.cpp').read_text()
a = ctx_source.index('        if (!ignore_macroblock) {\n            // A fresh macroblock')
macroblock = ctx_source[a:ctx_source.index('\n#endif', a)]
code = r'''
#include <cassert>
#include <cstdint>
#include <algorithm>
#include <vector>
#define VITA3K_PLATFORM_IOS 1
namespace vk { using DeviceSize=uint64_t; enum class Format {
 eR32G32Sfloat,eR32G32Uint,eR8G8B8A8Unorm,eR8G8B8A8Srgb,eR8G8B8A8Snorm,eR16G16B16A16Sfloat};
 unsigned blockSize(Format f){return f==Format::eR32G32Sfloat||f==Format::eR32G32Uint||f==Format::eR16G16B16A16Sfloat?8:4;}
}
enum class SurfaceTiling { Linear,Tiled };
struct Info {SurfaceTiling tiling=SurfaceTiling::Linear;unsigned original_width=720,original_height=408,stride_bytes=5760;
 struct {vk::Format format=vk::Format::eR32G32Sfloat;} texture;unsigned format=1;};
struct SceGxmNotification {};
struct State {unsigned res_multiplier=1;
 struct {bool use_texture_viewport=true;} features;
 struct {bool called_load=false;int retrieve_render_pass(int,bool load,bool store,bool){assert(store);called_load=load;return 7;}} pipeline_cache;
};
struct Context {
 bool has_rendered_in_recording=false,in_renderpass=false;
 bool load_depth_on_resume=false;
 unsigned scene_timestamp=10;int current_render_pass=0,current_color_format=0;
 struct {struct {int data=1;} color_surface;
  struct {int depth_data=0,stencil_data=0;bool force_load=false;} depth_stencil_surface;} record;
 std::vector<int> submitted,pre,render;
 void stop_recording(SceGxmNotification,SceGxmNotification,bool submit){
  assert(!submit);submitted.insert(submitted.end(),pre.begin(),pre.end());
  submitted.insert(submitted.end(),render.begin(),render.end());pre.clear();render.clear();in_renderpass=false;
 }
 void start_recording(){has_rendered_in_recording=false;}
 void enter_macroblock(State &state,bool ignore_macroblock){
'''+macroblock+r'''
 }
};
bool alias(Info info,State state,unsigned data_delta,vk::Format vk_format,
 unsigned original_width=1440,unsigned original_height=408,SurfaceTiling tiling=SurfaceTiling::Linear){
 unsigned start_sourced_line=data_delta/info.stride_bytes,start_x=(data_delta%info.stride_bytes)/4;
 unsigned bytes_per_pixel_requested=4,bytes_per_pixel_in_store=8,stride_bytes=5760;
'''+predicate+r'''
 return byte_equivalent_linear_alias;
}
bool direct_copy(Info info,vk::Format vk_format,unsigned bytes_per_pixel_requested,unsigned bytes_per_pixel_in_store){
'''+copy_policy+r'''
 return true;
 }
 return false;
}
int main(){
 Info info;State state;
 for(bool load:{false,true})for(bool backing:{false,true}) {
  Context c;c.load_depth_on_resume=true;
  c.record.depth_stencil_surface.force_load=load;
  c.record.depth_stencil_surface.depth_data=backing;
  c.enter_macroblock(state,false);
  assert(c.load_depth_on_resume==(load&&backing));
  c.load_depth_on_resume=true;c.enter_macroblock(state,true);
  assert(c.load_depth_on_resume); // slow full-scene path preserves prior depth
 }
 for(auto fmt:{vk::Format::eR8G8B8A8Unorm,vk::Format::eR8G8B8A8Srgb,vk::Format::eR8G8B8A8Snorm}) {
  assert(alias(info,state,0,fmt));assert(alias(info,state,4,fmt));
  assert(!alias(info,state,2,fmt));assert(!alias(info,state,8,fmt));
  assert(!alias(info,state,4,fmt,1440,408,SurfaceTiling::Tiled));
  assert(!alias(info,state,4,fmt,1440,407));
  State scaled;scaled.res_multiplier=2;assert(!alias(info,scaled,4,fmt));
 }
 Info expanded;expanded.texture.format=vk::Format::eR16G16B16A16Sfloat;
 assert(!alias(expanded,state,4,vk::Format::eR8G8B8A8Snorm));
 Info raw;raw.texture.format=vk::Format::eR32G32Uint;
 assert(alias(raw,state,0,vk::Format::eR8G8B8A8Unorm));
 assert(alias(raw,state,4,vk::Format::eR8G8B8A8Snorm));
 // Integer and floating RG32 have equal footprints but must use the raw
 // staging route; a same-format copy may use the image route.
 assert(direct_copy(raw,vk::Format::eR32G32Uint,8,8));
 assert(!direct_copy(raw,vk::Format::eR32G32Sfloat,8,8));
 assert(!direct_copy(raw,vk::Format::eR8G8B8A8Unorm,4,8));
 assert(!direct_copy(raw,vk::Format::eR8G8B8A8Snorm,4,8));
 // Emulate the Vulkan buffer copies with byte-distinct rows, preserving raw
 // float bits (no numeric conversion), row crossing and the last +4 tail.
 for(unsigned h:{1u,2u,408u})for(unsigned start_x:{0u,1u}) {
  const auto vk_format=vk::Format::eR8G8B8A8Snorm;
'''+offset+r'''
  std::vector<uint8_t> source(5760*h),buffer(5760*h+4,0),dest(5760*h);
  for(unsigned i=0;i<source.size();i++)source[i]=uint8_t((i*37+i/5760*11)%251);
  std::copy(source.begin(),source.end(),buffer.begin());
  for(unsigned row=0;row<h;row++)
   std::copy_n(buffer.begin()+destination_offset+row*5760,5760,dest.begin()+row*5760);
  for(unsigned i=0;i<dest.size();i++)assert(dest[i]==(i+destination_offset<source.size()?source[i+destination_offset]:0));
 }
 for(bool is_same_image:{false,true}) {
  unsigned base_format=info.format;
'''+viewport+r'''
  assert(can_use_viewport==!is_same_image);
 }
 // Packed colors/normals can look like NaNs, infinities or subnormals when
 // viewed as float. Integer -> buffer -> RGBA8 must preserve every bit,
 // including the +4-byte normal-word alias and its zero-filled final tail.
 const uint32_t payloads[]={0x7fc12345u,0x7f812345u,0xffcabcdeu,0x7f800000u,
  0xff800000u,0x00000001u,0x007fffffu,0x80000000u,0xdeadbeefu,0xffffffffu};
 std::vector<uint8_t> bytes;
 for(auto word:payloads)for(unsigned shift:{0u,8u,16u,24u})bytes.push_back(uint8_t(word>>shift));
 auto staging=bytes;staging.resize(bytes.size()+4,0);
 for(unsigned shift:{0u,4u}) {
  std::vector<uint8_t> rgba(bytes.size());
  std::copy_n(staging.begin()+shift,rgba.size(),rgba.begin());
  for(unsigned i=0;i<rgba.size();i++)assert(rgba[i]==(i+shift<bytes.size()?bytes[i+shift]:0));
 }
 // A macroblock may already have ended the pass, but its writes are still in
 // render_cmd. Both open and closed passes must precede the new snapshot.
 for(bool load_depth:{false,true})for(bool open:{false,true})for(bool prior_writes:{false,true})for(bool is_same_image:{false,true}) {
  Context c;auto *context=&c;c.in_renderpass=open;c.has_rendered_in_recording=prior_writes;
  c.load_depth_on_resume=load_depth;
  c.render.push_back(1);
'''+feedback+r'''
  c.pre.push_back(2); // snapshot recorded after production scheduling block
  if(prior_writes&&is_same_image) {
   assert(c.submitted==std::vector<int>{1});assert(c.scene_timestamp==11);
   assert(c.current_render_pass==7);assert(!c.has_rendered_in_recording);
   assert(state.pipeline_cache.called_load==load_depth);
   c.render.push_back(3); // upcoming draw consuming the snapshot
   c.stop_recording({}, {}, false);
   assert((c.submitted==std::vector<int>{1,2,3}));
  }else {assert(c.submitted.empty());assert(c.scene_timestamp==10);}
 }
}
'''
with tempfile.TemporaryDirectory() as tmp:
    cpp = Path(tmp) / 'test.cpp'
    cpp.write_text(code)
    exe = Path(tmp) / 'test'
    subprocess.run(['c++', '-std=c++20', '-fsanitize=address,undefined',
                    str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0'))
print('PASS: production offset/SNORM alias admission, row crossing/tail bounds and feedback command ordering')
