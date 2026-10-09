#!/usr/bin/env python3
"""Execute production unaligned uniform-copy code with typed SPIR-V operands."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / 'vita3k/shader/src/spirv_recompiler.cpp').read_text()
a = source.index('static void copy_uniform_block_to_register(')
body = source[a:source.index('\nstatic SpirvShaderParameters create_parameters', a)]
code = r'''
#include <cassert>
#include <array>
#include <map>
#include <vector>
#include <cstdint>
namespace spv {
using Id=uint32_t;
constexpr int NoResult=0,NoPrecision=0,StorageClassStorageBuffer=12,StorageClassPrivate=6,OpIAdd=128,OpVectorShuffle=79;
struct IdImmediate {bool isId;uint32_t word;IdImmediate(bool id,uint32_t w):isId(id),word(w){}};
struct Builder {
 using Vec=std::array<int,4>;
 std::array<Vec,64> bank{},block{};
 std::map<Id,int> numbers;
 std::map<Id,Vec> vectors;
 std::map<Id,std::pair<Id,int>> addresses;
 Id next=100;int iteration=0;
 Id makeIntConstant(int n){numbers[next]=n;return next++;}
 Id createLoad(Id id,int){
  if(id==3)return makeIntConstant(iteration);
  auto [which,index]=addresses.at(id);assert(index>=0 && index<64);
  vectors[next]=which==1?bank[index]:block[index];return next++;
 }
 Id getTypeId(Id){return 1;}
 Id createBinOp(int op,Id,Id x,Id y){assert(op==OpIAdd);return makeIntConstant(numbers.at(x)+numbers.at(y));}
 Id createOp(int op,Id,const std::vector<IdImmediate>& args){
  assert(op==OpVectorShuffle && args.size()==6);
  assert(args[0].isId && args[1].isId && args[0].word && args[1].word);
  auto left=vectors.at(args[0].word),right=vectors.at(args[1].word);Vec out{};
  for(int i=0;i<4;i++){
   assert(!args[i+2].isId);auto lane=args[i+2].word;assert(lane<8);
   out[i]=lane<4?left[lane]:right[lane-4];
  }
  vectors[next]=out;return next++;
 }
 void createStore(Id value,Id dest){auto [which,index]=addresses.at(dest);assert(which==1);bank[index]=vectors.at(value);}
};
}
namespace utils {
spv::Id create_access_chain(spv::Builder& b,int,spv::Id bank,std::initializer_list<spv::Id> indices){
 auto index=b.numbers.at(*indices.begin());b.addresses[b.next]={bank,index};return b.next++;
}
template<class F>void make_for_loop(spv::Builder& b,spv::Id,spv::Id begin,spv::Id end,F fn){
 for(b.iteration=b.numbers.at(begin);b.iteration<b.numbers.at(end);++b.iteration)fn();
}
}
'''+body+r'''
int main(){
 for(int start=0;start<8;start++)for(int count=1;count<=7;count++){
  spv::Builder b;
  for(int i=0;i<256;i++){b.bank[i/4][i%4]=-1000-i;b.block[i/4][i%4]=i+10;}
  auto original=b.bank;
  copy_uniform_block_to_register(b,1,2,3,start,count);
  for(int i=0;i<256;i++){
   auto expected=(i>=start && i<start+count*4)?i-start+10:original[i/4][i%4];
   assert(b.bank[i/4][i%4]==expected);
  }
 }
}
'''
with tempfile.TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'test.cpp';cpp.write_text(code);exe=Path(tmp)/'test'
    subprocess.run(['c++','-std=c++20','-fsanitize=address,undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0'))
print('PASS: 56 production uniform-copy alignment/extent cases, literal shuffle indices and preserved neighboring registers (typed builder stub)')
