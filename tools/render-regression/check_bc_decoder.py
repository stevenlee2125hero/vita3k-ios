#!/usr/bin/env python3
"""Compile the production BC decoder standalone; no GPU or third-party deps."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / 'vita3k/renderer/src/texture/format.cpp').read_text()
start = source.index('static void decompress_block_bc1(')
end = source.index('\n/**', source.index('void decompress_bc_image('))
code = '#include <cstdint>\n#include <cassert>\n#include <vector>\n' + source[start:end]
code += r'''
int main() {
    // c0=black <= c1=white; selector 3 must be transparent ONLY in BC1.
    uint8_t block[16] = {};
    block[10] = block[11] = 255;
    for (int i = 12; i < 16; ++i) block[i] = 255;
    uint32_t pixels[16];
    decompress_block_bc1(block + 8, pixels);
    assert(pixels[0] == 0);
    for (int i = 0; i < 8; ++i) block[i] = 255;
    decompress_block_bc2(block, pixels);
    assert(pixels[0] == 0xffaaaaaa);
    block[0] = 255; block[1] = 0;
    for (int i = 2; i < 8; ++i) block[i] = 0;
    decompress_block_bc3(block, pixels);
    assert(pixels[0] == 0xffaaaaaa);
    // Every decoded component and partial block must stay inside the output.
    for (uint8_t fmt = 1; fmt <= 7; ++fmt) {
        for (uint32_t w = 1; w <= 9; ++w) {
            for (uint32_t h = 1; h <= 9; ++h) {
                unsigned components = fmt <= 3 ? 4 : fmt <= 5 ? 1 : 2;
                std::vector<uint8_t> encoded(((w+3)/4)*((h+3)/4)*16, 0);
                std::vector<uint32_t> decoded((w*h*components+3)/4, 0);
                decompress_bc_image(w, h, encoded.data(), decoded.data(), fmt);
            }
        }
    }
}
'''
with tempfile.TemporaryDirectory() as tmp:
    cpp = Path(tmp) / 'bc_test.cpp'
    cpp.write_text(code)
    exe = Path(tmp) / 'bc_test'
    subprocess.run(['c++', '-std=c++20', '-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer', str(cpp), '-o', str(exe)], check=True)
    env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0")
    subprocess.run([str(exe)], check=True, env=env)
print('PASS: BC1 transparency, BC2/BC3 four-color mode, 567 BC1-5 extent cases (ASan/UBSan)')
