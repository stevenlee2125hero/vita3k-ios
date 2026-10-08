#!/usr/bin/env python3
"""Test production U2F10 conversion selection against Vulkan host footprint."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
f = (root / 'vita3k/renderer/src/texture/format.cpp').read_text()
a = f.index('static uint16_t f10_to_f16(')
b = f.index('// Based on this:', a)
conversion = f[a:b]
s = (root / 'vita3k/renderer/src/texture/cache.cpp').read_text()
a = s.index('        case SCE_GXM_TEXTURE_BASE_FORMAT_U2F10F10F10:')
b = s.index('        case SCE_GXM_TEXTURE_BASE_FORMAT_X8U24:', a)
selection = s[a:b]
code = r'''
#include <cstdint>
#include <array>
#include <vector>
#include <cassert>
#include <cstring>
#define LOG_INFO_ONCE(...) ((void)0)
using SceGxmTextureFormat=int;
constexpr int SCE_GXM_TEXTURE_FORMAT_U2F10F10F10_ABGR=0;
constexpr int SCE_GXM_TEXTURE_FORMAT_U2F10F10F10_ARGB=1;
constexpr int SCE_GXM_TEXTURE_FORMAT_X2F10F10F10_1BGR=2;
constexpr int SCE_GXM_TEXTURE_FORMAT_X2F10F10F10_1RGB=3;
constexpr int SCE_GXM_TEXTURE_BASE_FORMAT_U2F10F10F10=1;
constexpr int SCE_GXM_TEXTURE_BASE_FORMAT_F16F16F16F16=2;
'''+conversion+r'''
int main(){
 // Integer format availability must NEVER select raw packed-float upload.
 for(bool support_a2rgb10 : {false,true})for(int fmt=0;fmt<8;++fmt){
  bool is_vulkan=true;uint32_t pixels_per_stride=8,memory_height=3;
  // F10 values 1, 2, 0.5 and 2-bit alpha=1 in both packed alpha layouts.
  uint32_t packed=fmt<4 ? (3u<<30)|480u|(512u<<10)|(448u<<20)
                         : 3u|(480u<<2)|(512u<<12)|(448u<<22);
  std::vector<uint32_t> input(pixels_per_stride*memory_height,packed);
  const void *pixels=input.data();
  std::vector<uint8_t> texture_data_decompressed;
  int upload_format=SCE_GXM_TEXTURE_BASE_FORMAT_U2F10F10F10;
  switch(upload_format){
'''+selection+r'''
  }
  assert(upload_format==SCE_GXM_TEXTURE_BASE_FORMAT_F16F16F16F16);
  assert(texture_data_decompressed.size()==pixels_per_stride*memory_height*8);
  assert(pixels==texture_data_decompressed.data());
  const uint16_t upper[4]={0x3c00,0x4000,0x3800,0x3c00};
  const uint16_t lower[4]={0x3c00,0x3c00,0x4000,0x3800};
  for(unsigned i=0;i<pixels_per_stride*memory_height;i++){
   uint16_t decoded[4];std::memcpy(decoded,texture_data_decompressed.data()+i*8,8);
   assert(std::memcmp(decoded,fmt<4?upper:lower,8)==0);
  }
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
print('PASS: production U2F10 upload selection and half-float values, 16 format/capability cases')
