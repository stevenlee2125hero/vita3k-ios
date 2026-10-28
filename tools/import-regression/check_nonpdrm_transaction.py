#!/usr/bin/env python3
"""Check production decrypt commit with a simulated decryptor and real files."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root/'vita3k/packages/src/pkg.cpp').read_text()
start = source.index('bool decrypt_install_nonpdrm(')
body = source[start:source.index('\nbool install_pkg(', start)]
code = r'''
#include <filesystem>
#include <fstream>
#include <string>
#include <cassert>
namespace fs { using namespace std::filesystem; using std::ifstream;
path unique_path(const char*){return "_dec-test";} }
namespace fs_utils { fs::path path_concat(const fs::path&p,const fs::path&s){return p.string()+s.string();} }
#define LOG_ERROR(...) ((void)0)
struct EmuEnvState {struct {std::string app_category="gd";}app_info;};
enum class F00DEncryptorTypes{native};
std::string rif2zrif(fs::ifstream&){return "fixture";}
bool copy_license(EmuEnvState&,const fs::path&){return true;}
int mode;
int execute(std::string&,fs::path&,fs::path&dst,F00DEncryptorTypes,std::string&){
 if(mode==0)return -1;
 if(mode==1)return 0; // decryptor returned success but produced no output
 fs::create_directories(dst/"sce_sys");
 std::ofstream(dst/"sce_sys/param.sfo")<<"metadata";
 std::ofstream(dst/"eboot.bin")<<"decrypted";
 return 0;
}
'''+body+r'''
int main(int argc,char**argv){
 assert(argc==2);fs::path root=argv[1];EmuEnvState env;
 for(mode=0;mode<4;++mode){
  const auto title=root/std::to_string(mode);fs::create_directories(title);
  std::ofstream(title/"eboot.bin")<<"original";
  if(mode==3)fs::create_directories(title.string()+"_encrypted_backup");
  bool ok=decrypt_install_nonpdrm(env,root/"license.rif",title);
  assert(ok==(mode==2));
  std::ifstream f(title/"eboot.bin");std::string value;f>>value;
  assert(value==(ok?"decrypted":"original"));
  if(ok)assert(!fs::exists(title.string()+"_encrypted_backup"));
 }
}
'''
with tempfile.TemporaryDirectory() as directory:
    work = Path(directory)
    (work/'test.cpp').write_text(code)
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++23','-Wall','-Wextra',
                    str(work/'test.cpp'),'-o',str(work/'test')],check=True)
    subprocess.run([str(work/'test'),str(work/'data')],check=True)
assert 'iOS archive import decrypted bundled-license title' in (root/'ios/src/UpstreamMain.cpp').read_text()
print('PASS: decrypt failure/missing output/conflicting recovery preserve original; successful commit replaces it (decryptor stub)')
