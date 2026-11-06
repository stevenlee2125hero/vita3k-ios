import hashlib, json, os, pathlib, plistlib, struct, subprocess, sys, zipfile
SOURCE = '340f29f1bf2d8a591676f294fd0d3436ede2a99b'
COMMIT = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
IPA = pathlib.Path('artifacts/Vita3K-VitaEmu-340f29f1-unsigned.ipa')
if sys.argv[1] == 'prepare':
    apps = [p for p in pathlib.Path('build-ios-upstream').rglob('Vita3K-iOS.app') if '-iphoneos' in str(p)]
    assert len(apps) == 1, apps
    app = apps[0]
    info = plistlib.loads((app/'Info.plist').read_bytes())
    assert info['CFBundleIdentifier'] == 'com.stevenlee.vitaemu.ios'
    info['CFBundleDisplayName'] = 'Tsubomi VitaEmu'
    (app/'Info.plist').write_bytes(plistlib.dumps(info))
    (app/'VitaEmu-Provenance.json').write_text(json.dumps({'upstream': 'Vita-emu/Vita3K-iOS-', 'upstream_commit': SOURCE, 'build_commit': COMMIT, 'gameplay': 'unverified'}, indent=2))
elif sys.argv[1] == 'verify':
    with zipfile.ZipFile(IPA) as z:
        assert z.testzip() is None
        base = 'Payload/Vita3K-iOS.app/'
        info = plistlib.loads(z.read(base+'Info.plist'))
        assert info['CFBundleIdentifier'] == 'com.stevenlee.vitaemu.ios'
        assert info['CFBundleDisplayName'] == 'Tsubomi VitaEmu'
        p = json.loads(z.read(base+'VitaEmu-Provenance.json'))
        assert p['upstream_commit'] == SOURCE and p['build_commit'] == COMMIT
        assert COMMIT == os.environ.get('GITHUB_SHA', COMMIT)
        binary = z.read(base+'Vita3K-iOS')
        assert len(binary) > 20*1024*1024
        magic,cpu,_,kind,count,size,_,_ = struct.unpack_from('<8I', binary)
        assert (magic,cpu,kind) == (0xfeedfacf,0x100000c,2)
        pos=32; platform=None
        for _ in range(count):
            command,length=struct.unpack_from('<2I',binary,pos)
            assert length>=8 and pos+length<=32+size
            assert command!=0x1d
            if command==0x32: platform=struct.unpack_from('<I',binary,pos+8)[0]
            pos+=length
        assert platform==2
        assert not any('/_CodeSignature/' in n or n.endswith('embedded.mobileprovision') for n in z.namelist())
        shaders=0
        for source in pathlib.Path('vita3k/shaders-builtin').rglob('*.spv'):
            assert z.read(base+source.relative_to('vita3k').as_posix())==source.read_bytes()
            shaders+=1
        assert shaders>0
        p.update({'ipa_sha256':hashlib.sha256(IPA.read_bytes()).hexdigest(),'ipa_bytes':IPA.stat().st_size,'executable_bytes':len(binary),'minimum_ios':info['MinimumOSVersion'],'verified_spirv':shaders})
    pathlib.Path('artifacts/Vita3K-VitaEmu-verification.json').write_text(json.dumps(p,indent=2))
    print(json.dumps(p,indent=2))
else:
    raise SystemExit('Expected prepare or verify')
