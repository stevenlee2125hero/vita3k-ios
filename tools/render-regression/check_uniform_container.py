#!/usr/bin/env python3
"""Exercise the production uniform-buffer category branch with metadata stubs.

Tests parser branch logic and ordering under ASan/UBSan, not whole GXP decoding.
No guest assets are needed.
"""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
text = (root/'vita3k/shader/src/gxp_parser.cpp').read_text()
begin = text.index('case SCE_GXM_PARAMETER_CATEGORY_UNIFORM_BUFFER: {')
end = text.index('        default: {', begin)
body = text[begin:end]
harness = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <map>
enum { SCE_GXM_PARAMETER_CATEGORY_UNIFORM_BUFFER=4 };
struct Container { uint16_t index,base_sa_offset,size_in_f32; };
struct Program { std::map<uint16_t,Container> containers; };
struct Parameter { uint32_t resource_index,array_size,container_index; };
struct UniformBuffer { uint32_t index,reg_block_size; bool rw; uint32_t reg_start_offset,size; };
namespace gxp {
const Container* get_container_by_index(const Program& p,uint16_t index) {
 auto found=p.containers.find(index);return found==p.containers.end()?nullptr:&found->second;
}
}
void parse(const Program& program,const Parameter& parameter,std::map<int,UniformBuffer>& uniform_buffers) {
 switch(SCE_GXM_PARAMETER_CATEGORY_UNIFORM_BUFFER) { PRODUCTION_BODY }
}
int main() {
 int cases=0;
 for(uint16_t base : {uint16_t(1),uint16_t(3),uint16_t(16),uint16_t(63)})
 for(uint16_t count : {uint16_t(1),uint16_t(4),uint16_t(17)})
 for(uint32_t bytes : {1u,4u,7u,64u}) {
  Program program;program.containers.emplace(7,Container{7,base,count});
  // container_index deliberately differs: uniform-buffer lookup uses resource_index.
  Parameter parameter{7,bytes,14};std::map<int,UniformBuffer> buffers;
  parse(program,parameter,buffers);auto b=buffers.at(7);
  assert(b.index==7 && b.reg_start_offset==base && b.reg_block_size==count);
  assert(!b.rw && b.size==(bytes+3)/4);
  // A buffer discovered earlier without register metadata must be repaired.
  buffers[7]={7,0,false,0,128};parse(program,parameter,buffers);b=buffers.at(7);
  assert(b.reg_start_offset==base && b.reg_block_size==count && b.size==128);
  // Known mappings stay stable; later declarations can only extend the size.
  buffers[7]={7,9,true,5,1};parse(program,Parameter{7,1024,14},buffers);b=buffers.at(7);
  assert(b.reg_start_offset==5 && b.reg_block_size==9 && b.rw && b.size==256);
  // Missing container keeps the memory-only/fallback representation.
  buffers.clear();parse(Program{},parameter,buffers);b=buffers.at(7);
  assert(b.reg_start_offset==0 && b.reg_block_size==0 && b.size==(bytes+3)/4);
  cases+=4;
 }
 std::cout<<"PASS: "<<cases<<" production uniform-container cases (metadata stubs)\n";
}
'''
with tempfile.TemporaryDirectory() as folder:
    tmp=Path(folder)
    cpp=tmp/'test.cpp'
    cpp.write_text(harness.replace('PRODUCTION_BODY',body))
    binary=tmp/'test'
    subprocess.run(['c++','-std=c++20','-fsanitize=address,undefined',str(cpp),'-o',str(binary)],check=True)
    env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0')
    subprocess.run([str(binary)],check=True,env=env)
    # Explicitly demonstrate that discarding container mappings fails the test.
    old=body.replace('container ? container->size_in_f32 : 0','0').replace('container ? container->base_sa_offset : 0','0')
    old=old.replace('buffer.reg_block_size = container->size_in_f32;','buffer.reg_block_size = 0;').replace('buffer.reg_start_offset = container->base_sa_offset;','buffer.reg_start_offset = 0;')
    assert old!=body
    cpp.write_text(harness.replace('PRODUCTION_BODY',old))
    subprocess.run(['c++','-std=c++20',str(cpp),'-o',str(binary)],check=True)
    result=subprocess.run([str(binary)],capture_output=True,env=env)
    assert result.returncode!=0 and b'Assertion' in result.stderr, result
    print('PASS: previous zero-mapping behavior rejected')
