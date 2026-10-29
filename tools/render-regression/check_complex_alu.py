#!/usr/bin/env python3
"""Execute production USSE complex ALU lowering on a host Vulkan device.

Extract the four case bodies, use real pinned glslang/production utilities,
validate SPIR-V, translate to MSL, and dispatch the compute module on lavapipe.
This exercises the lowering, not GXP decoding or an Apple GPU.
"""
from pathlib import Path
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
alu = (root / 'vita3k/shader/src/translator/alu.cpp').read_text()
cases = []
for index, name in enumerate(('VLOG', 'VEXP', 'FLOG', 'FEXP')):
    pattern = rf'case Opcode::{name}: \{{(.*?)\n\s*break;\n\s*\}}'
    match = re.findall(pattern, alu, re.S)
    assert len(match) == 1, (name, len(match))
    cases.append(f'case {index}: {{' + match[0] + '\n break; }')
source = (root / 'vita3k/shader/src/usse_utilities.cpp').read_text()
source = source.replace('#include <shader/spirv_recompiler.h>', '')
source = source.replace('#include <shader/usse_program_analyzer.h>', '')
harness = r'''
#include <algorithm>
#include <bit>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <stack>
#include <stdexcept>
#include <vulkan/vulkan.h>
#include <fmt/format.h>
#include <SPIRV/GLSL.std.450.h>
#include <features/state.h>
PRODUCTION_SOURCE
using namespace shader::usse;
static void check(VkResult r) { if(r != VK_SUCCESS) throw std::runtime_error("Vulkan result " + std::to_string(r)); }
static std::vector<float> execute(const std::vector<uint32_t>& words) {
 VkApplicationInfo ai{VK_STRUCTURE_TYPE_APPLICATION_INFO}; ai.apiVersion=VK_API_VERSION_1_0;
 VkInstanceCreateInfo ici{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO}; ici.pApplicationInfo=&ai;
 VkInstance instance; check(vkCreateInstance(&ici,nullptr,&instance));
 uint32_t count=0; check(vkEnumeratePhysicalDevices(instance,&count,nullptr)); if(!count) throw std::runtime_error("No Vulkan device");
 std::vector<VkPhysicalDevice> devices(count); check(vkEnumeratePhysicalDevices(instance,&count,devices.data())); auto physical=devices[0];
 vkGetPhysicalDeviceQueueFamilyProperties(physical,&count,nullptr); std::vector<VkQueueFamilyProperties> props(count); vkGetPhysicalDeviceQueueFamilyProperties(physical,&count,props.data());
 uint32_t family=0; while(family<count && !(props[family].queueFlags&VK_QUEUE_COMPUTE_BIT)) ++family;
 if(family==count) throw std::runtime_error("No compute queue");
 float priority=1; VkDeviceQueueCreateInfo qci{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO}; qci.queueFamilyIndex=family; qci.queueCount=1; qci.pQueuePriorities=&priority;
 VkDeviceCreateInfo dci{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO}; dci.queueCreateInfoCount=1; dci.pQueueCreateInfos=&qci;
 VkDevice device; check(vkCreateDevice(physical,&dci,nullptr,&device)); VkQueue queue; vkGetDeviceQueue(device,family,0,&queue);
 VkBufferCreateInfo bci{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO}; bci.size=4096; bci.usage=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT;
 VkBuffer buffer; check(vkCreateBuffer(device,&bci,nullptr,&buffer)); VkMemoryRequirements req; vkGetBufferMemoryRequirements(device,buffer,&req);
 VkPhysicalDeviceMemoryProperties mem; vkGetPhysicalDeviceMemoryProperties(physical,&mem); uint32_t mi=0;
 for(;mi<mem.memoryTypeCount;mi++) if((req.memoryTypeBits&(1u<<mi)) && (mem.memoryTypes[mi].propertyFlags&(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))==(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) break;
 if(mi==mem.memoryTypeCount) throw std::runtime_error("No coherent host memory");
 VkMemoryAllocateInfo mai{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO}; mai.allocationSize=req.size; mai.memoryTypeIndex=mi;
 VkDeviceMemory memory; check(vkAllocateMemory(device,&mai,nullptr,&memory)); check(vkBindBufferMemory(device,buffer,memory,0));
 void* mapped; check(vkMapMemory(device,memory,0,4096,0,&mapped)); std::memset(mapped,0xff,4096);
 VkDescriptorSetLayoutBinding binding{0,VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,1,VK_SHADER_STAGE_COMPUTE_BIT,nullptr};
 VkDescriptorSetLayoutCreateInfo slci{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO}; slci.bindingCount=1; slci.pBindings=&binding;
 VkDescriptorSetLayout layout; check(vkCreateDescriptorSetLayout(device,&slci,nullptr,&layout));
 VkPipelineLayoutCreateInfo plci{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO}; plci.setLayoutCount=1; plci.pSetLayouts=&layout;
 VkPipelineLayout pipelineLayout; check(vkCreatePipelineLayout(device,&plci,nullptr,&pipelineLayout));
 VkShaderModuleCreateInfo smci{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO}; smci.codeSize=words.size()*4; smci.pCode=words.data();
 VkShaderModule module; check(vkCreateShaderModule(device,&smci,nullptr,&module));
 VkComputePipelineCreateInfo cpci{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO}; cpci.layout=pipelineLayout;
 cpci.stage={VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,nullptr,0,VK_SHADER_STAGE_COMPUTE_BIT,module,"main",nullptr};
 VkPipeline pipeline; check(vkCreateComputePipelines(device,VK_NULL_HANDLE,1,&cpci,nullptr,&pipeline));
 VkDescriptorPoolSize size{VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,1}; VkDescriptorPoolCreateInfo dpci{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO}; dpci.maxSets=1; dpci.poolSizeCount=1; dpci.pPoolSizes=&size;
 VkDescriptorPool pool; check(vkCreateDescriptorPool(device,&dpci,nullptr,&pool));
 VkDescriptorSetAllocateInfo dsai{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO}; dsai.descriptorPool=pool; dsai.descriptorSetCount=1; dsai.pSetLayouts=&layout;
 VkDescriptorSet set; check(vkAllocateDescriptorSets(device,&dsai,&set)); VkDescriptorBufferInfo bi{buffer,0,4096};
 VkWriteDescriptorSet write{VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET}; write.dstSet=set; write.descriptorCount=1; write.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; write.pBufferInfo=&bi; vkUpdateDescriptorSets(device,1,&write,0,nullptr);
 VkCommandPoolCreateInfo pci{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO}; pci.queueFamilyIndex=family; VkCommandPool commandPool; check(vkCreateCommandPool(device,&pci,nullptr,&commandPool));
 VkCommandBufferAllocateInfo cbai{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO}; cbai.commandPool=commandPool; cbai.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY; cbai.commandBufferCount=1; VkCommandBuffer command; check(vkAllocateCommandBuffers(device,&cbai,&command));
 VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO}; check(vkBeginCommandBuffer(command,&begin)); vkCmdBindPipeline(command,VK_PIPELINE_BIND_POINT_COMPUTE,pipeline); vkCmdBindDescriptorSets(command,VK_PIPELINE_BIND_POINT_COMPUTE,pipelineLayout,0,1,&set,0,nullptr); vkCmdDispatch(command,1,1,1);
 VkMemoryBarrier barrier{VK_STRUCTURE_TYPE_MEMORY_BARRIER}; barrier.srcAccessMask=VK_ACCESS_SHADER_WRITE_BIT; barrier.dstAccessMask=VK_ACCESS_HOST_READ_BIT;
 vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&barrier,0,nullptr,0,nullptr); check(vkEndCommandBuffer(command));
 VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO}; submit.commandBufferCount=1; submit.pCommandBuffers=&command; check(vkQueueSubmit(queue,1,&submit,VK_NULL_HANDLE)); check(vkQueueWaitIdle(queue));
 std::vector<float> values(1024); std::memcpy(values.data(),mapped,4096);
 vkDestroyCommandPool(device,commandPool,nullptr); vkDestroyDescriptorPool(device,pool,nullptr); vkDestroyPipeline(device,pipeline,nullptr); vkDestroyShaderModule(device,module,nullptr); vkDestroyPipelineLayout(device,pipelineLayout,nullptr); vkDestroyDescriptorSetLayout(device,layout,nullptr); vkUnmapMemory(device,memory); vkDestroyBuffer(device,buffer,nullptr); vkFreeMemory(device,memory,nullptr); vkDestroyDevice(device,nullptr); vkDestroyInstance(instance,nullptr); return values;
}
int main(int argc,char** argv) {
 spv::SpvBuildLogger logger; spv::Builder m_b(spv::Spv_1_0,0,&logger);
 m_b.setMemoryModel(spv::AddressingModelLogical,spv::MemoryModelGLSL450); m_b.addCapability(spv::CapabilityShader);
 auto main=m_b.makeEntryPoint("main"); m_b.addEntryPoint(spv::ExecutionModelGLCompute,main,"main"); m_b.addExecutionMode(main,spv::ExecutionModeLocalSize,1,1,1);
 auto std_builtins=m_b.import("GLSL.std.450"), f32=m_b.makeFloatType(32);
 auto array=m_b.makeArrayType(f32,m_b.makeIntConstant(1024),0); m_b.addDecoration(array,spv::DecorationArrayStride,4);
 auto block=m_b.makeStructType({array},"Results"); m_b.addDecoration(block,spv::DecorationBufferBlock); m_b.addMemberDecoration(block,0,spv::DecorationOffset,0);
 auto output=m_b.createVariable(spv::NoPrecision,spv::StorageClassUniform,block,"results"); m_b.addDecoration(output,spv::DecorationDescriptorSet,0); m_b.addDecoration(output,spv::DecorationBinding,0);
 std::vector<float> expected;
 for(int operation=0;operation<4;operation++) for(int lanes=1;lanes<=(operation<2?1:4);lanes++) for(int sample=0;sample<11;sample++) {
  const bool exponential=operation%2; std::vector<spv::Id> constants;
  for(int lane=0;lane<lanes;lane++) {
   const float x=sample==10 && exponential?std::numeric_limits<float>::quiet_NaN():exponential?float((sample+lane)%10-5)*0.5f:std::exp2(float((sample+lane)%10-5)*0.5f);
   constants.push_back(m_b.makeFloatConstant(x)); expected.push_back(std::isnan(x)?1.0f:exponential?std::exp2(x):std::log2(x));
  }
  auto input=lanes==1?constants[0]:m_b.makeCompositeConstant(m_b.makeVectorType(f32,lanes),constants);
  auto load=[&](int,uint32_t){return input;}; int ops[1]={0}; uint32_t write_mask_source=(1u<<lanes)-1; spv::Id result=input;
  switch(operation) { PRODUCTION_CASES }
  for(int lane=0;lane<lanes;lane++) {
   auto value=lanes==1?result:m_b.createCompositeExtract(result,f32,lane);
   auto pointer=utils::create_access_chain(m_b,spv::StorageClassUniform,output,{m_b.makeIntConstant(0),m_b.makeIntConstant(int(expected.size())-lanes+lane)}); m_b.createStore(value,pointer);
  }
 }
 m_b.leaveFunction(); std::vector<uint32_t> words; m_b.dump(words);
 if(!logger.getAllMessages().empty()) throw std::runtime_error(logger.getAllMessages());
 if(argc>2) for(size_t pos=5;pos<words.size();) { auto length=words[pos]>>16; if(!length) return 2; if((words[pos]&65535)==spv::OpExtInst) { if(words[pos+4]==GLSLstd450Exp2) words[pos+4]=GLSLstd450Exp; if(words[pos+4]==GLSLstd450Log2) words[pos+4]=GLSLstd450Log; } pos+=length; }
 std::ofstream out(argv[1],std::ios::binary); out.write(reinterpret_cast<const char*>(words.data()),words.size()*4); out.close();
 auto actual=execute(words); for(size_t i=0;i<expected.size();i++) if(!std::isfinite(actual[i]) || std::abs(actual[i]-expected[i])>2e-5f*std::max(1.0f,std::abs(expected[i]))) { std::cerr<<"numeric mismatch at "<<i<<": "<<actual[i]<<" != "<<expected[i]<<"\n"; return 1; }
 std::cout<<"PASS: "<<expected.size()<<" production ALU lane results on Vulkan\n";
}
'''
with tempfile.TemporaryDirectory() as folder:
    tmp = Path(folder)
    (tmp / 'util').mkdir()
    (tmp / 'SPIRV').mkdir()
    (tmp / 'SPIRV/GLSL.std.450.h').write_text('#include <spirv/unified1/GLSL.std.450.h>\n')
    (tmp / 'util/log.h').write_text('#pragma once\n#include <cassert>\n#include <fmt/format.h>\n#define LOG_ERROR(...) do { fmt::print(stderr, __VA_ARGS__); assert(false); } while(0)\n#define LOG_WARN(...) LOG_ERROR(__VA_ARGS__)\n#define LOG_CRITICAL(...) LOG_ERROR(__VA_ARGS__)\n')
    (tmp / 'test.cpp').write_text(harness.replace('PRODUCTION_SOURCE', source).replace('PRODUCTION_CASES', '\n'.join(cases)))
    (tmp / 'CMakeLists.txt').write_text(f'''cmake_minimum_required(VERSION 3.20)
project(complex_alu LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(ENABLE_OPT OFF CACHE BOOL "" FORCE)
set(ENABLE_GLSLANG_BINARIES OFF CACHE BOOL "" FORCE)
set(BUILD_EXTERNAL OFF CACHE BOOL "" FORCE)
set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
find_package(Threads REQUIRED)
find_package(fmt REQUIRED)
find_package(Vulkan REQUIRED)
add_subdirectory("{(root/'external/glslang').as_posix()}" glslang)
add_executable(alu_test test.cpp)
target_include_directories(alu_test PRIVATE "{tmp.as_posix()}" "{(root/'external/glslang').as_posix()}" "{(root/'vita3k/shader/include').as_posix()}" "{(root/'vita3k/features/include').as_posix()}" "{(root/'vita3k/util/include').as_posix()}")
target_link_libraries(alu_test PRIVATE SPIRV glslang fmt::fmt Threads::Threads Vulkan::Vulkan)
''')
    subprocess.run(['cmake', '-S', str(tmp), '-B', str(tmp/'build'), '-DCMAKE_BUILD_TYPE=Debug'], check=True)
    subprocess.run(['cmake', '--build', str(tmp/'build'), '--target', 'alu_test', '-j', '4'], check=True)
    binary = tmp/'complex.spv'
    subprocess.run([str(tmp/'build/alu_test'), str(binary)], check=True)
    subprocess.run(['spirv-val', '--target-env', 'vulkan1.0', str(binary)], check=True)
    subprocess.run(['spirv-cross', str(binary), '--msl', '--msl-version', '20300', '--output', str(tmp/'complex.metal')], check=True)
    old = subprocess.run([str(tmp/'build/alu_test'), str(tmp/'legacy.spv'), 'legacy'], text=True, capture_output=True)
    assert old.returncode == 1 and 'numeric mismatch' in old.stderr, old
    print('PASS: natural-base mutation rejected; valid SPIR-V and MSL generated')
