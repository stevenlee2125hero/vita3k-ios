#!/usr/bin/env python3
"""Test production SPIR-V precision filtering and packed word preservation."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
s = (root / 'vita3k/shader/src/spirv_recompiler.cpp').read_text()
p = (root / 'vita3k/renderer/src/vulkan/pipeline_cache.cpp').read_text()
v = p.index('    std::array<uint32_t, SCE_GXM_MAX_TEXTURE_UNITS +')
variant = p[v:p.index('\n    for (size_t i = 0; i < sizeof(variant_tag);', v)]
mask_stage = p[p.index('    maskupdate = maskupdate && !is_vertex;'):p.index('    maskupdate = maskupdate && !is_vertex;') + len('    maskupdate = maskupdate && !is_vertex;')]
mask_start = s.index('static void generate_update_mask_body(')
mask_body = s[mask_start:s.index('\nstatic SpirvCode convert_gxp_to_spirv_impl', mask_start)]
mask_guard_start = s.index('    translation_state.is_maskupdate = maskupdate &&')
mask_guard = s[mask_guard_start:s.index(';', mask_guard_start)+1]
c = (root / 'vita3k/renderer/src/vulkan/context.cpp').read_text()
fallback_start = c.index('    if (color_surface_fin->data.address() == 0)')
fallback = c[fallback_start:c.index('\n    context.current_color_format', fallback_start)]
# Every record field consumed by compile_pipeline must be in the copied prefix.
record_header = (root / 'vita3k/renderer/include/renderer/types.h').read_text()
record_start = record_header.index('struct GxmRecordState {')
prefix = record_header[record_start:record_header.index('std::array<GXMStreamInfo,', record_start)]
compile_start = p.index('vk::Pipeline PipelineCache::compile_pipeline(')
compile_body = p[compile_start:p.index('\nvk::Pipeline PipelineCache::retrieve_pipeline(', compile_start)]
import re
for field in set(re.findall(r'\brecord\.(\w+)', compile_body)):
    assert re.search(r'\b' + re.escape(field) + r'\b', prefix), 'Async pipeline reads uncopied field: ' + field
fmt = (root / 'vita3k/renderer/src/vulkan/gxm_to_vulkan.cpp').read_text()
color = fmt[fmt.index('namespace color {'):fmt.index('namespace texture {')]
assert 'return vk::Format::eR32G32Sfloat;' in color
assert 'return vk::Format::eR32G32Uint;' not in color
assert 'raw_rg32' not in s
assert 'output_type = b.makeVectorType(b.makeUintType(32), 4);' not in s
code = r'''
#include <vector>
#include <cstdint>
#include <cstddef>
#include <cassert>
#include <bit>
#include <array>
#include <map>
#include <string_view>
#include <cstring>
#include <memory>
#define LOG_INFO(...) ((void)0)
#define VITA3K_PLATFORM_IOS 1
namespace spv {
using Id=uint32_t;
enum{OpDecorate=71,DecorationRelaxedPrecision=0,NoPrecision=0,StorageClassUniform=2,StorageClassOutput=3,DecorationLocation=30,OpBitcast=124};
struct Builder {
 std::map<Id,Id> types;Id next=100,output_type=0;
 Id makeFloatType(int){return 1;}Id makeUintType(int){return 2;}Id makeIntConstant(int){return 3;}
 Id makeVectorType(Id scalar,int count){assert(count==4);return 10+scalar;}
 Id createLoad(Id,int){return 4;}
 Id createCompositeConstruct(Id type,std::initializer_list<Id>){types[next]=type;return next++;}
 Id createUnaryOp(int,Id type,Id){types[next]=type;return next++;}
 Id createVariable(int,int,Id type,const char*){output_type=type;types[next]=type;return next++;}
 void addDecoration(Id,int,int){}void createStore(Id value,Id output){assert(types[value]==types[output]);}
};
}
enum class SceGxmProgramType{Vertex,Fragment};
constexpr uint32_t SCE_GXM_COLOR_BASE_FORMAT_F32F32=11;
constexpr uint32_t SCE_GXM_COLOR_BASE_FORMAT_U8U8U8U8=3;
constexpr uint32_t SCE_GXM_COLOR_FORMAT_U8U8U8U8_ABGR=3;
namespace vk {enum class Format{eR8G8B8A8Unorm,eR32G32Uint};}
struct Address {uint32_t value;uint32_t address()const{return value;}};
struct Surface {Address data{};uint32_t colorFormat=11;bool downscale=false;};
struct Record {Surface color_surface;bool is_gamma_corrected=true,is_maskupdate=true;uint32_t color_base_format=11;};
struct Context {Record record;};
struct Target {bool multisample_mode=true;};
void check_transient_fallback(){
 Context context;Target target;auto rt=&target;
 auto color_surface_fin=&context.record.color_surface;
 auto vk_format=vk::Format::eR32G32Uint;
'''+fallback+r'''
 assert(color_surface_fin==nullptr);
 assert(vk_format==vk::Format::eR8G8B8A8Unorm);
 assert(context.record.color_surface.colorFormat==SCE_GXM_COLOR_FORMAT_U8U8U8U8_ABGR);
 assert(context.record.color_base_format==SCE_GXM_COLOR_BASE_FORMAT_U8U8U8U8);
 assert(!context.record.is_gamma_corrected && !context.record.is_maskupdate);
}
constexpr int FRAG_UNIFORM_writing_mask=0;
namespace gxm {uint32_t get_base_format(uint32_t f){return f;}}
namespace utils {spv::Id create_access_chain(spv::Builder&,int,spv::Id,std::initializer_list<spv::Id>){return 1;}}
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
'''+mask_stage+variant+r'''
 return variant_tag;
}
struct TranslationState {spv::Id render_info_id=0;bool is_vulkan=true,is_maskupdate=false;const Hints* hints;std::vector<spv::Id> interfaces;};
'''+mask_body+r'''
struct Program {SceGxmProgramType type;auto get_type()const{return type;}};
bool mask_enabled(const Program& program,bool maskupdate){TranslationState translation_state{};
'''+mask_guard+r'''
 return translation_state.is_maskupdate;
}
int main(){
 check_transient_fallback();
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
 assert(material_variant(hints,true,true)==vertex);
 assert(material_variant(hints,false,true)!=material_variant(hints,false,false));
 assert(!mask_enabled({SceGxmProgramType::Vertex},true));
 assert(mask_enabled({SceGxmProgramType::Fragment},true));
 assert(!mask_enabled({SceGxmProgramType::Fragment},false));
 TranslationState state{};state.hints=&hints;
 hints.color_format=0;spv::Builder float_builder;generate_update_mask_body(float_builder,state);assert(float_builder.output_type==11);
 hints.color_format=SCE_GXM_COLOR_BASE_FORMAT_F32F32;spv::Builder uint_builder;generate_update_mask_body(uint_builder,state);assert(uint_builder.output_type==11);
 state.is_vulkan=false;spv::Builder gl_builder;generate_update_mask_body(gl_builder,state);assert(gl_builder.output_type==11);

}
'''
with tempfile.TemporaryDirectory() as tmp:
    cpp = Path(tmp) / 'test.cpp'
    cpp.write_text(code)
    exe = Path(tmp) / 'test'
    subprocess.run(['c++', '-std=c++20', '-fsanitize=address,undefined',
                    str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0'))
print('PASS: restored float mask outputs, stage/attribute variant keys, transient format and async prefix bounds (builder/hash stubs)')
