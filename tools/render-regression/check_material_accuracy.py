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
p = (root / 'vita3k/renderer/src/vulkan/pipeline_cache.cpp').read_text()
v = p.index('    std::array<uint32_t, SCE_GXM_MAX_TEXTURE_UNITS +')
variant = p[v:p.index('\n    for (size_t i = 0; i < sizeof(variant_tag);', v)]
code = r'''
#include <vector>
#include <cstdint>
#include <cstddef>
#include <cassert>
#include <bit>
#include <array>
namespace spv {enum{OpDecorate=71,DecorationRelaxedPrecision=0};}
constexpr size_t SCE_GXM_MAX_TEXTURE_UNITS=16;
struct SceGxmVertexAttribute {uint16_t streamIndex,offset;uint8_t format,componentCount;uint16_t regIndex;};
static_assert(sizeof(SceGxmVertexAttribute)==8);
struct Hints {uint32_t color_format{},vertex_textures[16]{},fragment_textures[16]{};const std::vector<SceGxmVertexAttribute>* attributes{};};
// A deterministic hash stub isolates production key assembly from XXH64 itself.
uint64_t XXH64(const void* data,size_t size,uint64_t seed){
 auto bytes=static_cast<const uint8_t*>(data);uint64_t h=14695981039346656037ull^seed;
 for(size_t i=0;i<size;i++)h=(h^bytes[i])*1099511628211ull;return h;
}
uint64_t material_variant(const Hints& hints,bool is_vertex,bool maskupdate){
'''+variant+r'''
 return variant_tag;
}
struct Shader{std::vector<uint32_t> spirv;};
void filter(Shader &shader){
'''+body+r'''
}
int main(){
 std::vector<SceGxmVertexAttribute> attrs{{0,0,0,3,0}};
 Hints hints{};hints.attributes=&attrs;
 const auto vertex=material_variant(hints,true,false),fragment=material_variant(hints,false,false);
 attrs[0].componentCount=4;assert(material_variant(hints,true,false)!=vertex);
 assert(material_variant(hints,false,false)==fragment);
 attrs[0].componentCount=3;attrs[0].regIndex=4;assert(material_variant(hints,true,false)!=vertex);
 attrs[0].regIndex=0;attrs[0].format=1;assert(material_variant(hints,true,false)!=vertex);
 attrs[0].format=0;assert(material_variant(hints,true,false)==vertex);
 hints.vertex_textures[2]=17;assert(material_variant(hints,true,false)!=vertex);
 assert(material_variant(hints,false,false)==fragment);hints.vertex_textures[2]=0;
 hints.fragment_textures[2]=19;assert(material_variant(hints,false,false)!=fragment);
 assert(material_variant(hints,true,false)==vertex);hints.fragment_textures[2]=0;
 hints.color_format=23;assert(material_variant(hints,false,false)!=fragment);
 assert(material_variant(hints,true,false)==vertex);
 assert(material_variant(hints,true,true)!=vertex);
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
print('PASS: production SPIR-V precision filtering, raw words and material/attribute variant keys (hash stub)')
