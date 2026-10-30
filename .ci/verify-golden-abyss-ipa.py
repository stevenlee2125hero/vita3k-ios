"""Verify the complete v22-derived device package against this exact checkout."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import struct
import subprocess
import sys
import uuid
import zipfile


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify(path):
    root = Path(__file__).resolve().parent.parent
    commit = os.environ.get('GITHUB_SHA') or subprocess.check_output(
        ['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    with zipfile.ZipFile(path) as archive:
        require(archive.testzip() is None, 'IPA CRC failure')
        names = archive.namelist()
        plists = [n for n in names if n.endswith('.app/Info.plist')]
        require(len(plists) == 1, 'Expected one application')
        base = plists[0].rsplit('/', 1)[0]
        info = plistlib.loads(archive.read(plists[0]))
        expected = {
            'CFBundleIdentifier': 'org.vita3k.experimental.ios',
            'CFBundleExecutable': 'Vita3K-iOS',
            'CFBundleDisplayName': 'Tsubomi GA v24',
            'CFBundleShortVersionString': '0.47.24',
            'CFBundleVersion': '4724',
            'MinimumOSVersion': '26.0',
            'UIFileSharingEnabled': True,
        }
        for key, value in expected.items():
            require(info.get(key) == value, f'{key}: expected {value!r}')
        binary = archive.read(base + '/Vita3K-iOS')
        require(len(binary) > 20 * 1024 * 1024, 'Not a full-core executable')
        magic, cpu, _, filetype, count, commands_size, _, _ = struct.unpack_from('<8I', binary)
        require((magic, cpu, filetype) == (0xfeedfacf, 0x100000c, 2), 'Not an arm64 Mach-O executable')
        pos = 32
        platform = None
        ident = None
        for _ in range(count):
            command, length = struct.unpack_from('<2I', binary, pos)
            require(length >= 8 and pos + length <= 32 + commands_size, 'Invalid load command')
            require(command != 0x1d, 'Unsigned IPA unexpectedly contains LC_CODE_SIGNATURE')
            if command == 0x32:
                platform = struct.unpack_from('<I', binary, pos + 8)[0]
            if command == 0x1b:
                ident = str(uuid.UUID(bytes=binary[pos + 8:pos + 24]))
            pos += length
        require(platform == 2 and ident, 'Expected iPhoneOS device binary with UUID')
        require(not any('/_CodeSignature/' in n or n.endswith('embedded.mobileprovision') for n in names),
                'Expected unsigned bundle')
        provenance = archive.read(base + '/GoldenAbyss-Provenance.txt').decode('utf-8')
        for entry in (
            'BUILD_LABEL=GoldenAbyss-v24', 'PORT_COMMIT=' + commit,
            'V22_BUILD_SOURCE=2d7dd0c5c84bf2e8fff0cc3264560a8a395a773a',
            'ALU_UNIFORM_SOURCE=0db166640dd7bc90ae9e5433ffc440ce114afd05',
            'MOLTENVK=1.4.1', 'SHADER_CACHE=24',
        ):
            require(entry in provenance.splitlines(), 'Missing provenance: ' + entry)
        require(commit.encode() in binary and b'iOS compatibility v24:' in binary,
                'Executable lacks the matching source/version markers')
        sources = subprocess.check_output(
            ['git', '-C', str(root), 'ls-files', 'vita3k/shaders-builtin'], text=True).splitlines()
        checked = 0
        for source in sources:
            if not source.endswith(('.spv', '.vert', '.frag', '.comp')):
                continue
            canonical = subprocess.check_output(['git', '-C', str(root), 'show', 'HEAD:' + source])
            bundled = base + '/' + source.removeprefix('vita3k/')
            require(archive.read(bundled) == canonical, 'Shader byte mismatch: ' + source)
            checked += 1
        require(checked > 0, 'No builtin shaders checked')
    report = {
        'ipa': path.name, 'ipa_bytes': path.stat().st_size,
        'ipa_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'port_commit': commit, 'mach_uuid': ident, 'executable_bytes': len(binary),
        'verified_shader_files': checked, 'provenance': provenance,
        'device_gameplay': 'unverified',
    }
    path.with_suffix('.verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    verify(Path(sys.argv[1]))
