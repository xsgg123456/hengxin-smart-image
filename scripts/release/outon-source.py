"""Prepare an immutable complete package; make only provenance paths portable."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import sys


def portable(files):
    result = dict(files)
    manifest = json.loads(files['assets/brand/manifest.json'])
    for font in manifest['fonts'].values():
        assert hashlib.sha256(files[font['path']]).hexdigest() == font['sha256'], 'Font checksum drift'
        font['sources'] = [font['path'] for _ in font['sources']]
    for logo in manifest['logos'].values():
        assert hashlib.sha256(files[logo['path']]).hexdigest() == logo['sha256'], 'Logo checksum drift'
        logo['source'] = logo['path']
    reference = json.loads(files['assets/brand/font-reference.json'])
    for item in reference['sources']:
        path = 'assets/brand/fonts/' + PureWindowsPath(item['source']).name
        assert hashlib.sha256(files[path]).hexdigest() == item['sha256'], 'Reference font drift'
        item['source'] = path
    for name, value in [('assets/brand/manifest.json', manifest),
                        ('assets/brand/font-reference.json', reference)]:
        result[name] = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    return result


def build(repo, source, output):
    sys.path.insert(0, str(repo / 'hengxin-smart-image/backend'))
    from app.overseas.management.installed_tree import tree
    package, original = tree(source)
    files = portable(package.files)
    root = output / 'source' / package.name
    root.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    installed, entries = tree(root)
    changes = sorted(n for n in files if files[n] != package.files[n])
    assert set(changes) == {'assets/brand/manifest.json', 'assets/brand/font-reference.json'}
    assert tree(source)[0].checksum == package.checksum, 'Original source changed'
    evidence = dict(name=package.name, checksum=installed.checksum, entries=entries,
                    originalChecksum=package.checksum, originalEntries=original, adaptedFiles=changes)
    spec = importlib.util.spec_from_file_location('pack', Path(__file__).with_name('package-text.py'))
    pack = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pack)
    for name, data in files.items():
        if Path(name).suffix.lower() in ('.md', '.py', '.json', '.txt', '.yaml', '.yml'):
            pack.common.privacy_check(name, data)
    payload = {'skill-source/' + package.name + '/' + n: v for n, v in files.items()}
    payload['source-manifest.json'] = (json.dumps(evidence, ensure_ascii=False, indent=2) + '\n').encode()
    raw = pack.archive_bytes(payload)
    (output / 'skill-source.tar.gz').write_bytes(raw)
    (repo / 'docs/OUTON-SOURCE-MANIFEST-20261102.json').write_bytes(payload['source-manifest.json'])
    return dict(files=len(files), bytes=sum(map(len, files.values())), checksum=installed.checksum,
                originalChecksum=package.checksum, adaptedFiles=changes,
                archiveSha256=hashlib.sha256(raw).hexdigest(), archiveBytes=len(raw), privacy='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[2], args.source.resolve(), args.output.resolve())))
