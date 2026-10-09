"""Exercise production async policy with real worker threads and queue stubs."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / 'vita3k/renderer/src/vulkan/pipeline_cache.cpp').read_text()
start = source.index('void PipelineCache::set_async_compilation(bool enable)')
body = source[start:source.index('// magic number put at the beginning', start)]
code = r'''
#include <atomic>
#include <cassert>
#include <thread>
#include <vector>
#include <functional>
#define LOG_INFO(...) ((void)0)
#define LOG_INFO_ONCE(...) ((void)0)
struct PipelineCache {
 bool use_async_compilation=false;
 int nb_worker_threads=4;
 int mem=0;
 struct {int* mem;} state{&mem};
 struct Queue {int sent=0;void enqueue(std::nullptr_t){++sent;}} pipeline_compile_queue;
 std::vector<std::thread> worker_threads;
 std::atomic<int> entered{0};
 void compiler_thread(int&){++entered;}
 void set_async_compilation(bool);
};
''' + body + r'''
int main(){
 PipelineCache cache;
 for(int workers:{0,1,4}) {
  cache.nb_worker_threads=workers;
  cache.set_async_compilation(true);
#ifdef VITA3K_PLATFORM_IOS
  assert(!cache.use_async_compilation);
  assert(cache.worker_threads.empty());
  assert(cache.entered==0);
#else
  assert(cache.use_async_compilation);
  assert(cache.worker_threads.size()==static_cast<size_t>(workers));
#endif
  cache.set_async_compilation(true); // repeated settings must not add workers
  cache.set_async_compilation(false);
  assert(!cache.use_async_compilation && cache.worker_threads.empty());
 }
#ifdef VITA3K_PLATFORM_IOS
 assert(cache.pipeline_compile_queue.sent==0);
 // An existing worker must still be drained if configuration was enabled
 // before applying the iOS policy (e.g. initialization or session teardown).
 cache.use_async_compilation=true;
 cache.worker_threads.emplace_back([&]{++cache.entered;});
 cache.set_async_compilation(true);
 assert(!cache.use_async_compilation && cache.worker_threads.empty());
 assert(cache.entered==1 && cache.pipeline_compile_queue.sent==1);
#else
 assert(cache.entered==5 && cache.pipeline_compile_queue.sent==5);
#endif
}
'''
with tempfile.TemporaryDirectory() as tmp:
    cpp = Path(tmp) / 'test.cpp'
    cpp.write_text(code)
    for ios in (False, True):
        exe = Path(tmp) / ('ios' if ios else 'desktop')
        subprocess.run(['c++', '-std=c++20', '-pthread', '-fsanitize=address,undefined',
                        *(['-DVITA3K_PLATFORM_IOS'] if ios else []), str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True, env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0'))
print('PASS: production iOS synchronous policy, repeated config, zero-worker initialization, worker teardown; desktop async retained (queue stub)')
