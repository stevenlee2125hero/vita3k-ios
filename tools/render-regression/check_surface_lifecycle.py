#!/usr/bin/env python3
"""Exercise the production surface retirement body with recording GPU stubs."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
s = (root / 'vita3k/renderer/src/vulkan/surface_cache.cpp').read_text()
a = s.index('void VKSurfaceCache::destroy_surface(ColorSurfaceCacheInfo &info)')
b = s.index('\nvk::ImageView VKSurfaceCache::retrieve_sampled_view', a)
body = s[a:b]
a = s.index('            copy_buffer.size = static_cast<vk::DeviceSize>(pixel_stride)')
b = s.index(';', a) + 1
allocation = s[a:b]
code = r'''
#include <cstdint>
#include <cassert>
#include <memory>
#include <vector>
namespace vk { using DeviceSize = uint64_t; unsigned blockSize(unsigned f){return f;} }
struct Image{void *view=nullptr;void *image=nullptr;unsigned format=4;};
struct Buffer{void *buffer=nullptr;uint64_t size=0;};
namespace vkutil {
struct DestroyQueue {
 std::vector<void*> views,images,buffers;
 void add(void *p){if(p)views.push_back(p);}
 void add_image(Image &i){if(i.image)images.push_back(i.image);i.image=nullptr;i.view=nullptr;}
 void add_buffer(Buffer &b){if(b.buffer)buffers.push_back(b.buffer);b.buffer=nullptr;}
}; }
unsigned freed=0;
void sws_freeContext(void *p){if(p)++freed;}
struct Cast {Buffer transition_buffer;Image texture;};
struct View {void *view;};
struct ColorSurfaceCacheInfo {
 std::vector<Cast> casted_textures;std::vector<View> sampled_views;
 void *alternate_view=nullptr;Image texture;
 std::unique_ptr<Image> blit_image;std::unique_ptr<Buffer> copy_buffer;
 void *sws_context=nullptr;bool need_post_surface_sync=true,need_buffer_sync=true;
 unsigned original_height=0;
};
struct Frame {vkutil::DestroyQueue destroy_queue;};
struct State {Frame f;Frame &frame(){return f;}};
struct VKSurfaceCache {
 State state;std::vector<void*> framebuffers;
 void destroy_framebuffers(void *p){assert(p);framebuffers.push_back(p);}
 void destroy_surface(ColorSurfaceCacheInfo &info);
};
'''+body+r'''
int main(){
 VKSurfaceCache cache; ColorSurfaceCacheInfo info;
 void *a=reinterpret_cast<void*>(1),*b=reinterpret_cast<void*>(2),*c=reinterpret_cast<void*>(3);
 info.texture.image=a;info.texture.view=b;info.alternate_view=c;
 info.blit_image=std::make_unique<Image>();info.blit_image->image=a;
 info.copy_buffer=std::make_unique<Buffer>();info.copy_buffer->buffer=b;
 info.sws_context=c;
 cache.destroy_surface(info);
 assert(!info.alternate_view && !info.blit_image && !info.copy_buffer && !info.sws_context);
 assert(!info.need_post_surface_sync && !info.need_buffer_sync);
 assert(cache.framebuffers.size()==2 && freed==1);
 assert(cache.state.f.destroy_queue.buffers.size()==1);
 assert(cache.state.f.destroy_queue.images.size()==2);
 // Reuse slot without an alternate view: no stale handle or null framebuffer lookup.
 info.texture.image=b;info.texture.view=a;cache.destroy_surface(info);
 assert(cache.framebuffers.size()==3 && freed==1);
 for(unsigned stride : {8u,960u,1024u})for(unsigned h : {1u,544u}) {
  ColorSurfaceCacheInfo surface; surface.original_height=h; surface.texture.format=4;
  auto *last_written_surface=&surface; const unsigned pixel_stride=stride;Buffer copy_buffer;
'''+allocation+r'''
  assert(copy_buffer.size==uint64_t(stride)*h*4);
  assert(copy_buffer.size>uint64_t(stride)*h*3);
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
print('PASS: production surface retirement, slot reuse and expanded RGB allocation (recording GPU stubs)')
