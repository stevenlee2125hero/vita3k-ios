#!/usr/bin/env python3
"""Test typed material masks, title identity and pipeline compatibility."""
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
r = (root / 'vita3k/renderer/src/vulkan/renderer.cpp').read_text()
crop_start = r.index('    features.use_texture_viewport = support_standard_layout && !use_high_accuracy;')
crop_selection = r[crop_start:r.index('    // parse the mapping method', crop_start)]
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
assert 'preserve_packed_rg32 ? vk::Format::eR32G32Uint : vk::Format::eR32G32Sfloat' in color
assert 'features.preserve_packed_rg32' in c
app_init = (root / 'vita3k/app/src/app_init.cpp').read_text()
dispatch = next(line for line in app_init.splitlines() if 'state.renderer->late_init(' in line)
apps = (root / 'vita3k/app/src/apps_list.cpp').read_text()
identity_start = apps.index('    emuenv.io.app_path = it->path;')
identity_assignment = apps[identity_start:apps.index('    return true;', identity_start)]
output_start = s.index('        const bool packed_rg32 = translate_state.is_vulkan')
output = s[output_start:s.index('        if (features.preserve_f16_nan_as_u16)', output_start)]
fetch_start = s.index('            const bool packed_rg32 = translation_state.is_vulkan')
fetch = s[fetch_start:s.index('            translation_state.last_frag_data_id', fetch_start)]
blend_start = p.index('        vk::PipelineColorBlendAttachmentState blending = fragment_program.blending;')
blend = p[blend_start:p.index('        color_blending.setAttachments(blending);', blend_start)]
code = r'''
#include <vector>
#include <cstdint>
#include <cstddef>
#include <cassert>
#include <bit>
#include <array>
#include <map>
#include <string_view>
#include <string>
#include <cstring>
#include <memory>
#define LOG_INFO(...) ((void)0)
#define VITA3K_PLATFORM_IOS 1
#define VK_FALSE 0
namespace spv {
using Id=uint32_t;
enum{OpDecorate=71,DecorationRelaxedPrecision=0,NoPrecision=0,StorageClassUniform=2,StorageClassOutput=3,DecorationLocation=30,OpBitcast=124,StorageClassUniformConstant=0,DimSubpassData=6,ImageFormatUnknown=0,DecorationInputAttachmentIndex=43,DecorationBinding=33,DecorationDescriptorSet=34,OpImageRead=98};
struct Builder {
 std::map<Id,Id> types;Id next=100,output_type=0;
 Id makeFloatType(int){return 1;}Id makeUintType(int){return 2;}Id makeIntConstant(int){return 3;}
 Id makeVectorType(Id scalar,int count){assert(count==2||count==4);return count==4?10+scalar:30+scalar;}
 Id makeIntType(int){return 3;}
 Id makeImageType(Id scalar,int,bool,bool,bool,int,int){return 20+scalar;}
 Id makeCompositeConstant(Id type,std::initializer_list<Id>){types[next]=type;return next++;}
 Id createLoad(Id var,int){if(types.contains(var))return var;types[4]=1;return 4;}
 Id createOp(int op,Id type,std::initializer_list<Id> args){assert(op==OpImageRead);assert(type==types[*args.begin()]-10);types[next]=type;return next++;}
 void setPrecision(Id,int){}
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
namespace vk {enum class Format{eR8G8B8A8Unorm,eR32G32Uint};
struct PipelineColorBlendAttachmentState{bool blendEnable=true;};}
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
struct FeatureStateStub {uint32_t mask=0;uint32_t get_features_mask()const{return mask;}} state;
uint64_t material_variant(const Hints& hints,bool is_vertex,bool maskupdate){
'''+mask_stage+variant+r'''
 return variant_tag;
}
struct FeatureState {bool preserve_packed_rg32=false;};
struct TranslationState {spv::Id render_info_id=0;bool is_vulkan=true,is_maskupdate=false;const Hints* hints;std::vector<spv::Id> interfaces;};
'''+mask_body+r'''
struct Program {SceGxmProgramType type;auto get_type()const{return type;}};
bool mask_enabled(const Program& program,bool maskupdate){TranslationState translation_state{};
'''+mask_guard+r'''
 return translation_state.is_maskupdate;
}
struct CropFeatures {bool use_texture_viewport=false,preserve_packed_rg32=false,support_shader_interlock=true,direct_fragcolor=false;};
void select_crop(CropFeatures& features,bool support_standard_layout,bool use_high_accuracy,std::string_view game_id){
'''+crop_selection+r'''
}
struct Entry {std::string path,title_id,addcont,content_id,savedata,title,app_ver,category,stitle;};
struct RendererStub {std::string received;void late_init(int,std::string_view title,int){received=title;}};
struct Env {std::string app_path,current_app_title;
 struct {std::string app_path,title_id,addcont,content_id,savedata;} io;
 struct {std::string app_version,app_category,app_short_title;} app_info;
 int cfg=0,mem=0;RendererStub* renderer;};
void check_material_pipeline(bool enabled,bool vulkan,uint32_t format){
 FeatureState features;features.preserve_packed_rg32=enabled;
 Hints hints{};hints.color_format=format;
 TranslationState translate_state{};translate_state.is_vulkan=vulkan;translate_state.hints=&hints;
 spv::Builder b;spv::Id color=99;b.types[color]=11;int precision=spv::NoPrecision;
'''+output+r'''
 assert(b.output_type==((enabled && vulkan && format==SCE_GXM_COLOR_BASE_FORMAT_F32F32)?12:11));
 if(format==SCE_GXM_COLOR_BASE_FORMAT_F32F32){
  TranslationState translation_state=translate_state;
  const auto f32=b.makeFloatType(32),v4=b.makeVectorType(f32,4);spv::Id source=0;
'''+fetch+r'''
  assert(b.types[source]==11); // integer fetch must bitcast back to the guest float register bank
 }
 struct {FeatureState features;} state;state.features=features;
 struct {uint32_t color_base_format;} record;record.color_base_format=format;
 struct {vk::PipelineColorBlendAttachmentState blending;} fragment_program;
'''+blend+r'''
 assert(blending.blendEnable==!(enabled && format==SCE_GXM_COLOR_BASE_FORMAT_F32F32));
}
void check_real_title_dispatch(){
 RendererStub renderer;Env emuenv;emuenv.renderer=&renderer;
 for(auto title:{"PCSD00001","PCSG01112","PCSD00001"}) {
  Entry entry;entry.path="renamed-library-directory";entry.title_id=title;
  auto it=&entry;
'''+identity_assignment+r'''
  auto& state=emuenv;
'''+dispatch+r'''
  assert(renderer.received==title);
  CropFeatures features;select_crop(features,true,false,renderer.received);
  assert(!features.preserve_packed_rg32); // rejected v18 Metal path stays disabled for every title
 }
}
void check_crop_sessions(){
 CropFeatures features;
 select_crop(features,true,false,"PCSD00001");assert(!features.use_texture_viewport && !features.preserve_packed_rg32);
 select_crop(features,true,false,"PCSG01112");assert(features.use_texture_viewport && !features.preserve_packed_rg32);
 select_crop(features,true,true,"PCSG01112");assert(!features.use_texture_viewport);
 select_crop(features,true,false,"PCSG01112");assert(features.use_texture_viewport);
 select_crop(features,false,false,"PCSG01112");assert(!features.use_texture_viewport);
 // Crop texels [2,3] from an eight-texel target. Wrapping normalized
 // coordinates before applying the crop differs from wrapping the target
 // after applying a viewport transform. Verify both repeat and clamp edges.
 const int image[8]={0,1,2,3,4,5,6,7};
 auto clamp=[](int n,int lo,int hi){return n<lo?lo:n>hi?hi:n;};
 for(int i=-3;i<5;++i){
  int repeat=((i%2)+2)%2;
  assert(image[2+repeat]==(repeat?3:2));
  assert(image[2+clamp(i,0,1)]==(i<1?2:3));
 }
 assert(image[4]!=image[2]); // u=1 must repeat at the crop, not at target texel 4.
 assert(image[1]!=image[2]); // negative u must clamp at the crop, not target texel 1.
}
int main(){
 for(bool enabled:{false,true})for(bool vulkan:{false,true})
  for(auto format:{0u,SCE_GXM_COLOR_BASE_FORMAT_F32F32})check_material_pipeline(enabled,vulkan,format);
 check_real_title_dispatch();
 check_crop_sessions();
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
 state.mask=2;assert(material_variant(hints,true,false)!=vertex);
 state.mask=0;hints.color_format=0;assert(material_variant(hints,true,false)==vertex);
 FeatureState features;
 TranslationState state{};state.hints=&hints;
 hints.color_format=0;spv::Builder float_builder;generate_update_mask_body(float_builder,state,features);assert(float_builder.output_type==11);
 hints.color_format=SCE_GXM_COLOR_BASE_FORMAT_F32F32;spv::Builder uint_builder;generate_update_mask_body(uint_builder,state,features);assert(uint_builder.output_type==11);
 features.preserve_packed_rg32=true;spv::Builder packed_builder;generate_update_mask_body(packed_builder,state,features);assert(packed_builder.output_type==12);
 state.is_vulkan=false;spv::Builder gl_builder;generate_update_mask_body(gl_builder,state,features);assert(gl_builder.output_type==11);

}
'''
with tempfile.TemporaryDirectory() as tmp:
    cpp = Path(tmp) / 'test.cpp'
    cpp.write_text(code)
    exe = Path(tmp) / 'test'
    subprocess.run(['c++', '-std=c++20', '-fsanitize=address,undefined',
                    str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0'))
print('PASS: production output/fetch/blend type agreement, title dispatch and mask outputs, feature/stage/attribute variant keys, per-title crop reset, transient format and async prefix bounds (builder/hash stubs)')
