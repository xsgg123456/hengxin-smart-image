"""Pure-file installed tests with no production environment or network, as service UID."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

r = None


def invoke(work,root,source,target,label,python,as_root=False):
    import importlib.util
    import pwd
    spec = importlib.util.spec_from_file_location('reuse_scope',Path(__file__).with_name('skill-reuse-runtime.py'))
    p = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p)
    scratch = target/(label+'-'+uuid4().hex)
    scratch.mkdir(mode=0o700)
    user = pwd.getpwnam('hengxin-overseas')
    os.chown(scratch,user.pw_uid,user.pw_gid)
    uid = 0 if as_root else user.pw_uid
    code = ('import pathlib,os,pytest; from app.overseas.execution import materials; '
        'assert os.getuid()=='+repr(uid)+'; '
        'assert pathlib.Path(materials.__file__).resolve()==pathlib.Path('+repr(str(root/'app/overseas/execution/materials.py'))+'); '
        'assert pathlib.Path(pytest.__file__).resolve().is_relative_to(pathlib.Path('+repr(str(target/'vendor'))+')); '
        'raise SystemExit(pytest.main(__import__("sys").argv[1:]))')
    command = ['unshare','--net',*([] if as_root else ['runuser','-u','hengxin-overseas','--']),'env','-i',
        'PATH=/usr/bin:/bin','HOME='+str(scratch),'PYTHONPATH='+str(root)+':'+str(target/'vendor'),
        'APP_ENV=test','PYTHONDONTWRITEBYTECODE=1','PYTEST_DISABLE_PLUGIN_AUTOLOAD=1',str(python),
        '-B','-c',code,'-q','-p','no:cacheprovider','--basetemp='+str(scratch/'tmp'),
        *[str(source/'tests'/name) for name in (('test_studio_skill_cache_linux.py',) if as_root else p.TESTS)]]
    result = subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=600)
    r.private(work/(label+'-tests.txt'),result.stdout+'\n'+result.stderr)
    r.require(result.returncode == 0 and 'passed' in result.stdout and
              not any(word in result.stdout for word in ('failed','skipped','xfailed','xpassed')),
              'Installed regression failed/incomplete; inspect private '+label+'-tests.txt')


def vendor(target,image):
    directory = target/'vendor'
    directory.mkdir(mode=0o755)
    directory.chmod(0o755)  # main uses umask 077; descendants do not fix the root.
    names = ('pytest','_pytest','pluggy','iniconfig','packaging','pygments')
    code = ('import importlib.util,json,pathlib; print(json.dumps({n:str(pathlib.Path('
        'importlib.util.find_spec(n).origin).parent) for n in '+repr(names)+'}))')
    paths = json.loads(r.run('docker','run','--rm','--network','none','--entrypoint','python',image,'-B','-c',code))
    container = r.run('docker','create','--network','none','--entrypoint','python',image,'-c','pass')
    try:
        for name,path in paths.items():
            r.require(name in names and Path(path).name == name, 'Unexpected pytest dependency path')
            r.run('docker','cp',container+':'+path,str(directory/name))
    finally:
        r.run('docker','rm','-v',container)
    for path in directory.rglob('*'):
        r.require(not path.is_symlink(), 'Linked pytest dependency')
        path.chmod(0o755 if path.is_dir() else 0o644)


def candidate(work,data,source):
    roots = r.helper('sku-native').baseline_roots(data)
    r.require(len(roots) == 1, 'Expected shared overseas source root')
    root = Path(next(iter(roots)))
    target = Path('/opt')/('hengxin-skill-reuse-test-'+data['manifest'][:16])
    r.require(not target.exists(), 'Test install already exists; retain evidence and use fresh preparation')
    target.mkdir(mode=0o755)
    target.chmod(0o755)  # Service UID must traverse this root under umask 077.
    # Copy source only. No config, credentials, sessions, databases or production .venv copying.
    r.require(not any(path.is_symlink() for path in (root/'app').rglob('*')), 'Linked production app source')
    shutil.copytree(root/'app',target/'app',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in r.NATIVE_FILES:
        shutil.copyfile(source/'native'/name,target/name)
    for path in target.rglob('*'):
        r.require(not path.is_symlink(), 'Linked candidate source')
        path.chmod(0o755 if path.is_dir() else 0o644)
    vendor(target,data['api']['image'])
    # Exact production interpreter/dependencies; pytest alone is isolated outside its venv.
    invoke(work,target,source,target,'candidate',root/'.venv/bin/python')
    invoke(work,target,source,target,'candidate-root',root/'.venv/bin/python',as_root=True)
    r.private(work/'INSTALL_TESTS_PASSED',dict(manifest=data['manifest'],root=str(target),
        source=r.b.tree(target/'app')))


def installed(work,data,source):
    proof = json.loads((work/'INSTALL_TESTS_PASSED').read_text())
    target = Path(proof['root'])
    roots = r.helper('sku-native').baseline_roots(data)
    for index,root in enumerate(roots):
        invoke(work,Path(root),source,target,'installed-'+str(index),Path(root)/'.venv/bin/python')
        invoke(work,Path(root),source,target,'installed-root-'+str(index),Path(root)/'.venv/bin/python',as_root=True)
    r.private(work/'INSTALLED_PATH_TESTS_PASSED',dict(manifest=data['manifest']))
