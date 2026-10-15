"""Independent domestic release manifest; reuse the reviewed binary/privacy audit."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re

spec = importlib.util.spec_from_file_location('overseas_package', Path(__file__).with_name('package-overseas.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
APP, VERSION = p.APP, '0.2.37'
SCRIPTS = {'domestic-' + name + '.py' for name in ('deploy', 'runtime', 'gate', 'drain', 'backup', 'verify')}
HELPERS = {'package-' + name + '.py' for name in ('domestic', 'overseas', 'management', 'delivery')}
EXACT = {'infra/hengxin-domestic-deletions.service'}
REQUIRED = p.REQUIRED | EXACT | {'scripts/release/' + name for name in SCRIPTS} | {
    'backend/migrations/versions/0029_api_task_deletions.py',
    'backend/app/modules/api_image_edits/deletion_models.py', 'backend/app/retention/worker.py'}


def selected(path):
    if path in {'scripts/release/' + name for name in SCRIPTS}:
        return path
    if path in {APP + name for name in EXACT}:
        return path.removeprefix(APP)
    return p.selected(path)


def validate(files):
    if missing := REQUIRED - files.keys():
        raise ValueError('Missing required package files: ' + ', '.join(sorted(missing)))
    if json.loads(files['frontend/package.json'])['version'] != VERSION:
        raise ValueError('Frontend version must be ' + VERSION)
    index = files['frontend/dist/index.html'].decode('utf-8')
    if 'overseas-preview' in index or any(n.endswith(('overseas-preview.html', 'demo.html')) for n in files):
        raise ValueError('Preview frontend is not a production build')
    refs = re.findall(r'(?:src|href)=["\']/?(assets/[^"\'?#]+)', index)
    if not any(ref.endswith('.js') for ref in refs):
        raise ValueError('Production index must reference JavaScript')
    if any('frontend/dist/' + ref not in files for ref in refs):
        raise ValueError('Missing frontend entry asset')


def build(repo):
    git = lambda *args: p.m.common.git(repo, *args)
    p.require_clean_tracked(git)
    status = p.m.common.reviewed_status(repo)
    commit = git('rev-parse', 'HEAD').decode().strip()
    tracked = git('ls-files', '-z').decode().split('\0')
    if not {'scripts/release/' + name for name in HELPERS}.issubset(tracked):
        raise ValueError('Packaging helpers must be committed before use')
    files, exceptions = {}, {}
    for path in tracked:
        name = selected(path)
        if not name:
            continue
        local = repo / path
        p.no_symlink(local)
        raw = p.m.common.normalized(git('show', f'{commit}:{path}'))
        if raw != p.m.common.normalized(local.read_bytes()):
            raise ValueError('Working tree differs from commit: ' + path)
        if found := p.m.common.privacy_check(name, raw):
            exceptions[name] = found
        files[name] = raw
    files.update(p.collect_assets(repo / APP / 'frontend/dist'))
    validate(files)
    release = 'domestic-20261015-' + commit[:7]
    manifest = dict(release=release, commit=commit, candidateId=status['currentId'],
                    migration='0029', overseasMigration='overseas_0016', frontendVersion=VERSION,
                    files={n: hashlib.sha256(v).hexdigest() for n, v in sorted(files.items())})
    files['release.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    p.require_clean_tracked(git)
    if git('rev-parse', 'HEAD').decode().strip() != commit or p.m.common.reviewed_status(repo)['currentId'] != status['currentId']:
        raise ValueError('Source changed during packaging')
    raw = p.m.archive_bytes(files)
    p.verify_archive(raw, files)
    target = repo / 'output/release' / release
    target.mkdir(parents=True, exist_ok=False)
    archive = target / 'release.tar.gz'
    archive.write_bytes(raw)
    saved = archive.read_bytes()
    p.verify_archive(saved, files)
    audit = dict(release=release, files=len(files), bytes=len(saved), sha256=hashlib.sha256(saved).hexdigest(),
                 privacy='PASS', archiveVerified=True, syntheticFixtureExceptions=exceptions)
    (target / 'package-audit.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
    return audit


if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
