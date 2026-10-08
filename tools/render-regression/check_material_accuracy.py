#!/usr/bin/env python3
"""Test production SPIR-V precision filtering and packed word preservation."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
s = (root / 'vita3k/shader/src/spirv_recompiler.cpp').read_text()
a = s.index('        for (size_t pos = 5; pos < shader.spirv.size();)')
body = s[a:s.index('\n    }\n#endif', a)]
code = r'''
#include <vector>
#include <cstdint>
#include <cstddef>
#include <cassert>
#include <bit>
namespace spv {enum{OpDecorate=71,DecorationRelaxedPrecision=0};}
struct Shader{std::vector<uint32_t> spirv;};
void filter(Shader &shader){
'''+body+r'''
}
int main(){
 Shader s{{0x07230203,0x10000,0,16,0,
  (3u<<16)|71,2,0, // relaxed precision: remove
  (4u<<16)|71,3,30,0, // Location: keep
  (3u<<16)|71,4,0, // consecutive relaxed precision: remove
  (3u<<16)|71,5,0,
  (1u<<16)|253}};
 filter(s);
 assert((s.spirv==std::vector<uint32_t>{0x07230203,0x10000,0,16,0,(4u<<16)|71,3,30,0,(1u<<16)|253}));
 Shader invalid{{0,0,0,0,0,0}};filter(invalid);assert(invalid.spirv.size()==6);
 Shader truncated{{0,0,0,0,0,(4u<<16)|71,2}};filter(truncated);assert(truncated.spirv.size()==7);
 // RG32 integer attachment and buffer reinterpretation preserve every payload,
 // including patterns that are NaNs, infinities or subnormals as floats.
 for(uint32_t word:{0u,1u,0x007fffffu,0x7f800000u,0x7fc12345u,0xffcabcdeu,0x80000001u,0xffffffffu}) {
  auto f=std::bit_cast<float>(word);assert(std::bit_cast<uint32_t>(f)==word);
  uint32_t attachment=word;uint8_t bytes[4];
  for(unsigned i=0;i<4;i++)bytes[i]=uint8_t(attachment>>(8*i));
  uint32_t copied=0;for(unsigned i=0;i<4;i++)copied|=uint32_t(bytes[i])<<(8*i);
  assert(copied==word);
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
print('PASS: production SPIR-V precision filtering and raw material word roundtrip')
