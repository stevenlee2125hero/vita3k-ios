#!/usr/bin/env python3
"""Exercise the production ZIP/VPK inspector, extractor and commit on disk."""
from pathlib import Path
import os
import struct
import subprocess
import tempfile
import zipfile

root = Path(__file__).resolve().parents[2]
os.environ['ASAN_OPTIONS'] = 'detect_leaks=0'

def sfo():
    values = {'TITLE_ID': 'PCSE01171', 'TITLE': 'Undertale import fixture',
              'CATEGORY': 'gd', 'APP_VER': '01.00'}
    keys, data, entries = b'', b'', b''
    for key, value in values.items():
        encoded = value.encode() + b'\0'
        entries += struct.pack('<HHIII', len(keys), 0x204, len(encoded), len(encoded), len(data))
        keys += key.encode() + b'\0'
        data += encoded
    start = 20 + len(entries)
    return struct.pack('<IIIII', 0x46535000, 0x101, start, start + len(keys), len(values)) + entries + keys + data

with tempfile.TemporaryDirectory() as directory:
    work = Path(directory)
    (work / 'util').mkdir()
    (work / 'util/log.h').write_text('#pragma once\n#define LOG_WARN(...) ((void)0)\n#define LOG_ERROR(...) ((void)0)\n')
    (work / 'main.cpp').write_text('''
#include <packages/archive.h>
#include <iostream>
int main(int argc,char**argv) {
 if(argc!=3)return 2;
 auto r=packages::install_archive_transactionally(argv[1],argv[2]);
 std::cout<<r.detail<<"\\n";
 return r.success?0:1;
}
''')
    subprocess.run(['gcc', '-c', str(root/'external/miniz/miniz.c'), '-o', str(work/'miniz.o')], check=True)
    subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++23', '-O1',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-no-pie',
                    '-I'+str(work), '-I'+str(root/'vita3k/packages/include'),
                    '-I'+str(root/'external/miniz'), str(work/'main.cpp'),
                    str(root/'vita3k/packages/src/archive.cpp'),
                    str(root/'vita3k/packages/src/sfo.cpp'), str(work/'miniz.o'),
                    '-o', str(work/'install')], check=True)
    for index, prefix in enumerate(['', './', '././wrapper/', 'wrapper/app/PCSE01171/',
                                    'wrapper\\app\\PCSE01171\\']):
        archive, destination = work/f'valid{index}.zip', work/f'vfs{index}'
        sep = '\\' if '\\' in prefix else '/'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
            if prefix.startswith('./'): z.writestr('./', b'')
            z.writestr(prefix+'sce_sys'+sep+'param.sfo', sfo())
            z.writestr(prefix+'eboot.bin', b'ELF fixture')
            z.writestr(prefix+'assets'+sep+'中文.dat', b'asset bytes')
        subprocess.run([str(work/'install'), str(archive), str(destination)], check=True)
        title = destination/'ux0/app/PCSE01171'
        assert (title/'eboot.bin').read_bytes() == b'ELF fixture'
        assert (title/'assets/中文.dat').read_bytes() == b'asset bytes'
        assert not list((destination/'.install-staging').iterdir())
        # Reinstall must replace transactionally rather than leave stale files.
        (title/'obsolete').write_bytes(b'old')
        subprocess.run([str(work/'install'), str(archive), str(destination)], check=True)
        assert not (title/'obsolete').exists()
    for index, unsafe in enumerate(['../escape', './..\\escape', '/absolute',
                                     'C:\\escape', './sce_sys/param.sfo']):
        archive, destination = work/f'invalid{index}.zip', work/f'rejected{index}'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('sce_sys/param.sfo', sfo())
            z.writestr('eboot.bin', b'fixture')
            z.writestr(unsafe, sfo() if index == 4 else b'unsafe')
        assert subprocess.run([str(work/'install'), str(archive), str(destination)]).returncode == 1
        assert not destination.exists(), 'Rejected archives must not alter installed data'
print('PASS: production import/extract/reinstall, Unix/Windows wrapper paths, UTF-8 assets, traversal and duplicate rejection')
