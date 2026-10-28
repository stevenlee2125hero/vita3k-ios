#!/usr/bin/env python3
"""Validate production register/pack code with real glslang and SPIR-V Tools.

No game assets or model builder. The production utility implementation generates
both raw and legacy register variants, including byte/half masked stores. This
checks SPIR-V typing and MSL compilation; device rendering remains a separate gate.
Requires the pinned external/glslang submodule, libfmt-dev, spirv-tools
and spirv-cross on Linux.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / 'vita3k/shader/src/usse_utilities.cpp').read_text()
# These two headers introduce unrelated emulator memory/GXM dependencies.
# All implementation bodies and register/feature types below remain production.
source = source.replace('#include <shader/spirv_recompiler.h>', '')
source = source.replace('#include <shader/usse_program_analyzer.h>', '')

harness = r'''
#include <algorithm>
#include <bit>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <stack>
#include <fmt/format.h>
#include <SPIRV/GLSL.std.450.h>
#include <features/state.h>
PRODUCTION_SOURCE
using namespace shader::usse;
int main(int argc, char** argv) {
 for (bool policy : {false, true}) for (bool raw : {false, true}) {
  spv::SpvBuildLogger logger;
  spv::Builder b(spv::Spv_1_0, 0, &logger);
  b.setMemoryModel(spv::AddressingModelLogical, spv::MemoryModelGLSL450);
  b.addCapability(spv::CapabilityShader);
  auto main = b.makeEntryPoint("main");
  auto entry = b.addEntryPoint(spv::ExecutionModelFragment, main, "main");
  b.addExecutionMode(main, spv::ExecutionModeOriginUpperLeft);
  FeatureState features{}; features.preserve_packed_rg32 = policy;
  utils::SpirvUtilFunctions funcs; funcs.std_builtins = b.import("GLSL.std.450");
  auto u32 = b.makeUintType(32), f32 = b.makeFloatType(32);
  auto u4 = b.makeVectorType(u32, 4), f4 = b.makeVectorType(f32, 4);
  auto vec = raw ? u4 : f4;
  auto banktype = b.makeArrayType(vec, b.makeIntConstant(32), 0);
  SpirvShaderParameters params{};
  params.ins = b.createVariable(spv::NoPrecision, spv::StorageClassPrivate, banktype, "pa");
  params.temps = b.createVariable(spv::NoPrecision, spv::StorageClassPrivate, banktype, "r");
  params.outs = b.createVariable(spv::NoPrecision, spv::StorageClassPrivate, banktype, "outs");
  params.internals = b.createVariable(spv::NoPrecision, spv::StorageClassPrivate, banktype, "internals");
  params.uniforms = b.createVariable(spv::NoPrecision, spv::StorageClassPrivate, banktype, "sa");
  auto zero = raw ? b.makeUintConstant(0) : b.makeFloatConstant(0);
  auto zeros = b.makeCompositeConstant(vec, {zero,zero,zero,zero});
  for (auto bank : {params.ins,params.temps,params.outs,params.internals,params.uniforms})
   for (int index=0;index<32;index++)
    b.createStore(zeros, utils::create_access_chain(b,spv::StorageClassPrivate,bank,{b.makeIntConstant(index)}));
  auto output=b.createVariable(spv::NoPrecision,spv::StorageClassOutput,u4,"out_color");
  b.addDecoration(output,spv::DecorationLocation,0); entry->addIdOperand(output);
  // Export each result so the generated instruction graph remains live.
  auto emit=[&](spv::Id value) {
   int count=b.getNumComponents(value);
   auto bits=utils::make_vector_or_scalar_type(b,u32,count);
   if(b.getTypeId(value)!=bits)value=b.createUnaryOp(spv::OpBitcast,bits,value);
   std::vector<spv::Id> lanes;
   for(int i=0;i<4;i++)lanes.push_back(count==1?value:b.createCompositeExtract(value,u32,i%count));
   b.createStore(b.createCompositeConstruct(u4,lanes),output);
  };
  for (auto bank : {RegisterBank::PRIMATTR, RegisterBank::TEMP, RegisterBank::OUTPUT, RegisterBank::FPINTERNAL})
   for (auto dtype : {DataType::UINT32,DataType::INT32,DataType::F32,DataType::UINT8,DataType::INT8,DataType::UINT16,DataType::INT16,DataType::F16,DataType::C10})
    for (int offset : {0,1,3,4}) for (int mask=1;mask<16;mask++) {
     Operand dest;dest.bank=bank;dest.num=offset;dest.type=dtype;dest.swizzle=SWIZZLE_CHANNEL_4_DEFAULT;
     int count=utils::dest_mask_to_comp_count(mask);
     auto scalar=is_unsigned_integer_data_type(dtype)?u32:(is_signed_integer_data_type(dtype)?b.makeIntType(32):f32);
     std::vector<spv::Id> lanes;
     for(int i=0;i<count;i++) {
      // Payloads cover NaN/Inf/subnormal/signed-zero encodings in raw 32-bit moves.
      uint32_t words[]={0x7fc12345,0x00000001,0x80000000,0xff800000};
      auto val=b.makeUintConstant(get_data_type_size(dtype)==4?words[i]:uint32_t(17+i));
      if(scalar==f32) val=get_data_type_size(dtype)==4?b.createUnaryOp(spv::OpBitcast,f32,val):b.makeFloatConstant(0.25f*i);
      else if(scalar!=u32)val=b.createUnaryOp(spv::OpBitcast,scalar,val);
      lanes.push_back(val);
     }
     auto value=count==1?lanes[0]:b.createCompositeConstruct(b.makeVectorType(scalar,count),lanes);
     utils::store(b,params,funcs,features,dest,value,mask,0);
     emit(utils::load(b,params,funcs,features,dest,mask,0));
     // Constant selectors in a raw word bank must have the same scalar type.
     dest.type=DataType::UINT32;dest.swizzle=SWIZZLE_CHANNEL_4(X,1,Z,0);
     emit(utils::load(b,params,funcs,features,dest,15,0));
    }
  b.leaveFunction();
  std::vector<uint32_t> words;b.dump(words);
  std::string file=std::string(argv[1])+"/registers-"+std::to_string(policy)+"-"+std::to_string(raw)+".spv";
  std::ofstream out(file,std::ios::binary);out.write(reinterpret_cast<const char*>(words.data()),words.size()*4);
  if(!logger.getAllMessages().empty()){std::cerr<<logger.getAllMessages();return 1;}
 }
}
'''

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    (tmp / 'util').mkdir()
    (tmp / 'SPIRV').mkdir()
    (tmp / 'SPIRV/GLSL.std.450.h').write_text('#include <spirv/unified1/GLSL.std.450.h>\n')
    (tmp / 'util/log.h').write_text('''#pragma once
#include <cassert>
#include <fmt/format.h>
#define LOG_ERROR(...) do { fmt::print(stderr, __VA_ARGS__); assert(false); } while(0)
#define LOG_WARN(...) LOG_ERROR(__VA_ARGS__)
#define LOG_CRITICAL(...) LOG_ERROR(__VA_ARGS__)
''')
    cpp = tmp / 'test.cpp'
    cpp.write_text(harness.replace('PRODUCTION_SOURCE', source))
    cmake = f"""cmake_minimum_required(VERSION 3.20)
project(raw_material_registers LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(ENABLE_OPT OFF CACHE BOOL "" FORCE)
set(ENABLE_GLSLANG_BINARIES OFF CACHE BOOL "" FORCE)
set(BUILD_EXTERNAL OFF CACHE BOOL "" FORCE)
set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
find_package(Threads REQUIRED)
find_package(fmt REQUIRED)
add_subdirectory("{(root/'external/glslang').as_posix()}" glslang)
add_executable(register_test test.cpp)
target_include_directories(register_test PRIVATE "{tmp.as_posix()}"
 "{(root/'external/glslang').as_posix()}"
 "{(root/'vita3k/shader/include').as_posix()}"
 "{(root/'vita3k/features/include').as_posix()}"
 "{(root/'vita3k/util/include').as_posix()}")
target_link_libraries(register_test PRIVATE SPIRV glslang fmt::fmt Threads::Threads)
"""
    (tmp / 'CMakeLists.txt').write_text(cmake)
    subprocess.run(['cmake', '-S', str(tmp), '-B', str(tmp/'build'),
                    '-DCMAKE_BUILD_TYPE=Debug'], check=True)
    subprocess.run(['cmake', '--build', str(tmp/'build'), '--target', 'register_test', '-j', '4'], check=True)
    subprocess.run([str(tmp/'build/register_test'), str(tmp)], check=True)
    for binary in sorted(tmp.glob('*.spv')):
        subprocess.run(['spirv-val', '--target-env', 'vulkan1.0', str(binary)], check=True)
        subprocess.run(['spirv-cross', str(binary), '--msl', '--msl-version', '20300',
                        '--output', str(binary.with_suffix('.metal'))], check=True)
        print('PASS:', binary.name)
print('PASS: real production utility SPIR-V and MSL: 4 policies, 8640 masked register cases')
