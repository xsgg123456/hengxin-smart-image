"""Exact five-member workflow binding; independent API/native environment installation."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from uuid import UUID

spec = importlib.util.spec_from_file_location('outon_runtime', Path(__file__).with_name('outon-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
KEY = 'OVERSEAS_WORKFLOW_COLLABORATOR_MEMBER_IDS'
ENV_FILE = Path('/etc/hengxin-overseas/workflow-collaborators.env')
DROP_NAME = 'zzzzzzzzzzzzzz-workflow-collaborators.conf'


def safe(path):
    r.require(not any(p.is_symlink() for p in (path, *path.parents)), 'Linked workflow configuration')
    return path


def binding(work):
    path = safe(work/'workflow-collaborators.private.json')
    rows = json.loads(path.read_text(encoding='utf-8-sig'))['members']
    r.require(isinstance(rows, list) and len(rows) == 5, 'Exactly five workflow members required')
    ids = []
    for row in rows:
        value = row['id']
        r.require(isinstance(value, str) and str(UUID(value)) == value, 'Invalid workflow member UUID')
        r.require((row['status'], row['directoryState'], row['role']) == ('active','enrolled','designer'),
                  'Workflow binding must contain active enrolled designers')
        ids.append(value)
    r.require(len(set(ids)) == 5, 'Duplicate workflow member')
    return sorted(ids)


def encoded(ids):
    return json.dumps(ids, separators=(',', ':'))


def environment(pid):
    raw = (Path('/proc')/str(pid)/'environ').read_bytes()
    return dict(part.decode().split('=', 1) for part in raw.split(b'\0') if part)


def protected_environment(env):
    # systemd invocation identifiers legitimately change at restart. Business settings do not.
    values = {k:v for k,v in env.items() if k != KEY and k.startswith(('OVERSEAS_', 'HX_'))}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def existing_grant(env, ids):
    values = json.loads(env.get(KEY) or '[]')
    r.require(isinstance(values, list) and (not values or sorted(values) == ids),
              'Existing workflow grants require explicit review')


def probe(ids):
    # Evaluate the actual baseline application policy, including independent full-access grants.
    code = '''import json,sys
import app.overseas.main
from uuid import UUID
from sqlalchemy import text
from app.db.session import session_factory
from app.overseas.auth.models import Member
from app.overseas.permissions import principal_for
with session_factory()() as session:
 session.execute(text('SET TRANSACTION READ ONLY'))
 result=[]
 for value in json.loads(sys.argv[1]):
  member=session.get(Member,UUID(value))
  if member is None: raise RuntimeError('Workflow member missing')
  result.append({'id':value,'status':member.status,'directoryState':member.directory_state,
                 'roles':sorted(principal_for(session,member).roles)})
 print(json.dumps(result))
'''
    rows = json.loads(r.run('docker','exec',r.API,'python','-B','-c',code,encoded(ids)))
    r.require(rows == [dict(id=value, status='active', directoryState='enrolled', roles=['designer'])
                       for value in ids], 'Workflow members must remain effective active enrolled designers')


def native_files(ids):
    result = {str(ENV_FILE):KEY+"='"+encoded(ids)+"'\n"}
    for unit in r.UNITS:
        path = Path('/etc/systemd/system')/(unit+'.d')/DROP_NAME
        result[str(path)] = '[Service]\nEnvironmentFile='+str(ENV_FILE)+'\n'
    return result


def native_inventory(unit):
    paths = set()
    for key in ('FragmentPath', 'DropInPaths', 'EnvironmentFiles'):
        paths.update(p for p in r.run('systemctl','show',unit,'-p',key,'--value').split() if p.startswith('/'))
    return paths


def prepare(work, data, live):
    ids = binding(work)
    probe(ids)
    existing_grant(dict(item.split('=',1) for item in live['Config']['Env']), ids)
    files = native_files(ids)
    for name in files:
        r.require(not safe(Path(name)).exists(), 'Workflow native configuration already exists; inspect explicitly')
    environments = {}
    for unit in r.UNITS:
        env = environment(data['protected']['units'][unit]['pid'])
        existing_grant(env, ids)
        environments[unit] = protected_environment(env)
    return dict(memberIds=ids, bindingHash=r.digest(work/'workflow-collaborators.private.json'),
                files={name:hashlib.sha256(value.encode()).hexdigest() for name,value in files.items()},
                nativeEnvironment=environments)


def overlay(before, image, workflow):
    ids = workflow['memberIds']
    existing_grant(before['services']['api'].get('environment', {}), ids)
    return {'services':{'api':{'image':image, 'environment':{KEY:encoded(ids)}}}}


def check_overlay(before, after, image, workflow):
    expected = copy.deepcopy(before)
    expected['services']['api']['image'] = image
    expected['services']['api'].setdefault('environment', {})[KEY] = encoded(workflow['memberIds'])
    r.require(expected == after, 'API overlay changes unrelated settings')


def guard(work, data):
    workflow = data['workflow']
    r.require(r.digest(work/'workflow-collaborators.private.json') == workflow['bindingHash']
              and binding(work) == workflow['memberIds'], 'Workflow binding drift')
    expected = native_files(workflow['memberIds'])
    r.require({n:hashlib.sha256(v.encode()).hexdigest() for n,v in expected.items()} == workflow['files'],
              'Workflow configuration evidence drift')
    started = (work/'WORKFLOW_NATIVE_STARTED').exists()
    installed = (work/'WORKFLOW_NATIVE_INSTALLED').exists()
    if started:
        r.require(json.loads((work/'WORKFLOW_NATIVE_STARTED').read_text()) ==
                  {'manifest':data['manifest'], 'files':workflow['files']}, 'Workflow installation marker drift')
    for name, digest in workflow['files'].items():
        path = safe(Path(name))
        if path.exists():
            r.require(started and r.digest(path) == digest and path.stat().st_uid == 0,
                      'Workflow native configuration drift')
            mode = 0o600 if path == ENV_FILE else 0o644
            r.require(path.stat().st_mode & 0o777 == mode, 'Workflow native configuration mode drift')
        else:
            r.require(not installed, 'Workflow native configuration missing')
    for unit in r.UNITS:
        original = set(data['protected']['units'][unit]['files'])
        drop = Path('/etc/systemd/system')/(unit+'.d')/DROP_NAME
        grant = {str(drop), str(ENV_FILE)} if drop.exists() else set()
        stop = r.helper('outon-native').drop_path(unit)
        allowed = original | grant | ({str(stop)} if stop.exists() else set())
        actual = native_inventory(unit)
        r.require(original <= actual <= allowed, 'Native configuration inventory drift')
        if installed:
            r.require({str(drop), str(ENV_FILE)} <= actual, 'Workflow configuration not loaded by systemd')
    if installed:
        r.require(json.loads((work/'WORKFLOW_NATIVE_INSTALLED').read_text()) ==
                  {'manifest':data['manifest'], 'files':workflow['files']}, 'Workflow installation proof drift')


def install(work, data):
    guard(work, data)
    r.require(not (work/'WORKFLOW_NATIVE_STARTED').exists(), 'Inspect partial workflow configuration; no blind retry')
    r.helper('outon-native').stopped()
    r.private(work/'WORKFLOW_NATIVE_STARTED', {'manifest':data['manifest'], 'files':data['workflow']['files']})
    for name, value in native_files(data['workflow']['memberIds']).items():
        path = safe(Path(name))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(value)
        path.chmod(0o600 if path == ENV_FILE else 0o644)
        r.require(r.digest(path) == data['workflow']['files'][name], 'Workflow installation checksum mismatch')
    r.run('systemctl','daemon-reload')
    r.private(work/'WORKFLOW_NATIVE_INSTALLED', {'manifest':data['manifest'], 'files':data['workflow']['files']})
    guard(work, data)


def verify_native(work, data):
    guard(work, data)
    r.require((work/'WORKFLOW_NATIVE_INSTALLED').exists(), 'Workflow native installation missing')
    native = r.helper('outon-native')
    for unit in r.UNITS:
        env = environment(native.pid(unit))
        r.require(env.get(KEY) == encoded(data['workflow']['memberIds']), 'Native workflow grant mismatch')
        r.require(protected_environment(env) == data['workflow']['nativeEnvironment'][unit],
                  'Unrelated native environment drift')


def verify_api(data, live):
    env = dict(item.split('=',1) for item in live['Config']['Env'])
    r.require(env.get(KEY) == encoded(data['workflow']['memberIds']), 'API workflow grant mismatch')
    probe(data['workflow']['memberIds'])
