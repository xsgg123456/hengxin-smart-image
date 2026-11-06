"""Network-isolated API/publisher and actual native UID installed regression."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

r = None


def invoke(work, root, source, target, label, python, as_root=False):
    import pwd
    manifest = r.verify_package(source)
    user = pwd.getpwnam('hengxin-overseas')
    uid, gid = (0, 0) if as_root else (user.pw_uid, user.pw_gid)
    scratch = target/(label+'-'+uuid4().hex)
    scratch.mkdir(mode=0o700)
    os.chown(scratch, uid, gid)
    # Compile every installed file as the real service user; selected tests import code.
    code = ('import pathlib,os,pytest; assert os.getuid()=='+repr(uid)+'; '
        'assert pathlib.Path(pytest.__file__).resolve().is_relative_to(pathlib.Path('+repr(str(target/'vendor'))+')); '
        '[(compile(pathlib.Path(p).read_bytes(),p,"exec")) for p in '+repr([str(root/n) for n in sorted(r.NATIVE_FILES)])+']; '
        'raise SystemExit(pytest.main(__import__("sys").argv[1:]))')
    tests = manifest['tests']['root' if as_root else 'native']
    command = ['unshare', '--net', *([] if as_root else ['runuser', '-u', 'hengxin-overseas', '--']),
        'env', '-i', 'PATH=/usr/bin:/bin', 'HOME='+str(scratch), 'PYTHONPATH='+str(root)+':'+str(target/'vendor'),
        'APP_ENV=test', 'PYTHONDONTWRITEBYTECODE=1', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1', str(python), '-B', '-c',
        code, '-q', '-p', 'no:cacheprovider', '--basetemp='+str(scratch/'tmp'),
        *[str(target/'tests'/name) for name in tests]]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=600)
    r.private(work/(label+'-tests.txt'), result.stdout+'\n'+result.stderr)
    r.require(result.returncode == 0 and 'passed' in result.stdout and
              not any(word in result.stdout for word in ('failed', 'skipped', 'xfailed', 'xpassed')),
              'Installed regression failed/incomplete: '+label)


def candidate(work, data, source):
    # SKU test runner starts a network-none disposable PostgreSQL and gives the
    # test image only that network namespace, no production mounts or environment.
    tester = r.helper('sku-deploy')
    tester.state = lambda *a, **k: (data, source)
    runner = tester.installed_pytest
    def as_user(command, image, user):
        index = command.index(image)
        return command[:index]+['--user', user]+command[index:]
    # This test exercises protected root publication; API deliberately runs as
    # UID 10001. It runs unfiltered in publisher and native-root suites below.
    tester.installed_pytest = lambda command, output: runner(
        as_user(command, data['image'], '10001:10001')+
        ['-k', 'not test_protected_object_publication_and_permission_tamper'], output)
    tester.test(work)
    (work/'installed-tests.txt').replace(work/'api-installed-tests.txt')
    publisher = dict(data, image=data['images']['publisher'])
    tester.state = lambda *a, **k: (publisher, source)
    tester.installed_pytest = lambda command, output: runner(
        as_user(command, publisher['image'], '0:0'), output)
    tester.test(work)
    (work/'installed-tests.txt').replace(work/'publisher-installed-tests.txt')
    roots = r.helper('sku-native').baseline_roots(data)
    r.require(len(roots) == 1, 'Expected shared overseas native source')
    root = Path(next(iter(roots)))
    target = Path('/opt')/('hengxin-skill-physical-test-'+data['manifest'][:16])
    r.require(not target.exists(), 'Candidate install already exists; retain evidence')
    target.mkdir(mode=0o755)
    target.chmod(0o755)
    r.require(not any(p.is_symlink() for p in (root/'app').rglob('*')), 'Linked native app source')
    shutil.copytree(root/'app', target/'app', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(source/'tests', target/'tests')
    for name in r.NATIVE_FILES:
        shutil.copyfile(source/'api'/name, target/name)
    for path in target.rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)
    r.helper('skill-reuse-test').vendor(target, data['image'])
    invoke(work, target, source, target, 'candidate', root/'.venv/bin/python')
    invoke(work, target, source, target, 'candidate-root', root/'.venv/bin/python', True)
    r.private(work/'INSTALL_TESTS_PASSED', dict(manifest=data['manifest'], images=data['images'],
        root=str(target), source=r.b.tree(target/'app')))


def installed(work, data, source):
    target = Path(json.loads((work/'INSTALL_TESTS_PASSED').read_text())['root'])
    for index, root in enumerate(r.helper('sku-native').baseline_roots(data)):
        invoke(work, Path(root), source, target, 'installed-'+str(index), Path(root)/'.venv/bin/python')
        invoke(work, Path(root), source, target, 'installed-root-'+str(index), Path(root)/'.venv/bin/python', True)
    r.private(work/'INSTALLED_PATH_TESTS_PASSED', {'manifest': data['manifest']})
