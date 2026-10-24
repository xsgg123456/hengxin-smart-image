"""Private, evidence-bound repair before the inherited release reopens intake.

Place delivery-repair-request.private.json in the root-only release work folder
before prepare. It contains actor_id, turn_id, expected_sha256 and exactly eight
expected_checksums entries. Never put this request in src or in the archive.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from uuid import UUID

REQUEST = 'delivery-repair-request.private.json'
PIN = 'DELIVERY_REPAIR_REQUEST.sha256'
RUNTIME = 'studio-delivery-repair-runtime.py'


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate repair request key')
        result[key] = value
    return result


def request(work):
    path = work / REQUEST
    assert path.resolve() == path.absolute(), 'Repair request path must not contain symlinks'
    metadata = path.stat()
    assert stat.S_ISREG(metadata.st_mode) and metadata.st_size <= 65536, 'Invalid repair request file'
    if os.name == 'posix':
        assert metadata.st_uid == os.geteuid() and not stat.S_IMODE(metadata.st_mode) & 0o077, 'Repair request must be owner-only'
        folder = work.stat()
        assert folder.st_uid == os.geteuid() and not stat.S_IMODE(folder.st_mode) & 0o077, 'Repair work directory must be owner-only'
    raw = path.read_bytes()
    body = json.loads(raw, object_pairs_hook=unique)
    assert isinstance(body, dict) and set(body) == {'actor_id', 'turn_id', 'expected_sha256', 'expected_checksums'}, 'Invalid repair request fields'
    for key in ('actor_id', 'turn_id'):
        assert isinstance(body[key], str) and str(UUID(body[key])) == body[key] and UUID(body[key]).int, 'Invalid repair identity'
    digest = lambda value: isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value)
    assert digest(body['expected_sha256']), 'Invalid event digest'
    expected = body['expected_checksums']
    assert isinstance(expected, dict) and len(expected) == 8, 'Exactly eight approved original images required'
    assert all(isinstance(key, str) and 0 < len(key) <= 4096 and not any(ord(c) < 32 for c in key)
               and digest(value) for key, value in expected.items()), 'Invalid original image evidence'
    return body, sha256(raw).hexdigest()


def durable(work, name, value, m):
    """Flush recovery evidence before any database gate mutation."""
    path = work / name
    assert not path.is_symlink(), 'Repair evidence must not be a symlink'
    m.private(path, value)
    with path.open('r+b') as stream:
        os.fsync(stream.fileno())
    if os.name == 'posix':
        descriptor = os.open(work, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def pin(work, m):
    _, digest = request(work)
    path = work / PIN
    if path.exists():
        assert path.read_text() == digest, 'Repair request changed after preparation'
    else:
        durable(work, PIN, digest, m)


def worker_context(target, m, u):
    import pwd
    pid = int(m.run('systemctl', 'show', u.UNITS[0], '-p', 'MainPID', '--value', capture=True, timeout=15))
    assert pid > 0 and Path(os.readlink(f'/proc/{pid}/cwd')) == target, 'Repair worker is not the installed target'
    assert m.run('systemctl', 'show', u.UNITS[0], '-p', 'WorkingDirectory', '--value', capture=True, timeout=15) == str(target)
    status = dict(line.split(':', 1) for line in Path(f'/proc/{pid}/status').read_text().splitlines() if ':' in line)
    account = pwd.getpwnam('hengxin-overseas')
    assert set(map(int, status['Uid'].split())) == {account.pw_uid} and account.pw_uid != 0, 'Repair worker user drift'
    groups = list(map(int, status['Groups'].split()))
    gids = set(map(int, status['Gid'].split()))
    assert len(gids) == 1, 'Repair worker group drift'
    env = dict(os.fsdecode(item).split('=', 1) for item in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0') if item)
    assert env.get('HX_BUSINESS_CONTEXT') == 'overseas', 'Repair context must be overseas'
    env.update(PYTHONPATH=str(target), PYTHONDONTWRITEBYTECODE='1', PYTHONOPTIMIZE='0')
    return dict(cwd=target, env=env, user=account.pw_uid, group=gids.pop(), extra_groups=groups, umask=0o077)


def invoke(work, target, context, packet, step, m):
    # Code is reviewed package content. Identities/evidence travel on stdin, not
    # the command line; secrets stay solely in the existing worker environment.
    code = Path(__file__).with_name(RUNTIME).read_text(encoding='utf-8')
    with (work / ('delivery-repair-' + step + '.private.log')).open('w', encoding='utf-8') as log:
        os.chmod(log.name, 0o600)
        result = subprocess.run([str(target / '.venv/bin/python'), '-B', '-c', code],
            input=json.dumps(packet), stdout=subprocess.PIPE, stderr=log, text=True,
            timeout=600, check=False, **context)
    durable(work, 'delivery-repair-' + step + '.private.json', result.stdout, m)
    assert result.returncode == 0, 'Delivery repair failed at ' + step + '; inspect private evidence; keep intake closed'
    return json.loads(result.stdout)


def run(work, target, receipt, m, d, u):
    body, digest = request(work)
    assert (work / PIN).read_text() == digest, 'Repair request changed after preparation'
    assert (work / 'INSTALLED_VERIFIED').is_file(), 'Installed verification required before repair'
    assert not (work / 'DELIVERY_REPAIR_STARTED').exists(), 'Repair attempt requires inspected recovery, not replay'
    d.closed()
    d.wait_empty(work, 'delivery-repair-idle')
    context = worker_context(target, m, u)
    packet = dict(request=body)
    call = lambda action, **extra: invoke(work, target, context, {**packet, 'action': action, **extra}, action, m)
    baseline = call('inspect')
    assert type(baseline['paused']) is bool, 'Unknown original gate state'
    durable(work, 'DELIVERY_REPAIR_BASELINE.private.json',
            dict(requestSha256=digest, installation=receipt, baseline=baseline), m)
    durable(work, 'DELIVERY_REPAIR_STARTED', 'Keep gate paused and edge closed on any failure; do not replay deploy or repair. '
            'Inspect baseline, step receipts and original delivery snapshots; no model rerun or database restore.', m)
    call('pause', original_paused=baseline['paused'])
    for step in ('dry-run', 'apply'):
        d.closed()
        report = call(step)
        assert report['checksums'] == body['expected_checksums'] and report['expected'] == 8, 'Repair selection mismatch'
        allowed = ('eligible', 'already_recovered') if step == 'dry-run' else ('succeeded', 'already_recovered')
        assert report['status'] in allowed, 'Delivery repair incomplete; keep gate paused'
    verified = call('verify')
    assert verified['execution'] == baseline['execution'], 'Repair changed execution facts'
    repeated = call('repeat')
    assert repeated['status'] == 'already_recovered' and repeated['saved'] == 8, 'Repeat repair was not idempotent'
    assert repeated['checksums'] == body['expected_checksums'], 'Repeat repair changed selection'
    after = call('verify-repeat')
    assert after == verified, 'Repeat repair changed durable rows or object bytes'
    d.wait_empty(work, 'delivery-repair-complete-idle')
    d.closed()
    durable(work, 'DELIVERY_REPAIR_VERIFIED.private.json',
            dict(requestSha256=digest, installation=receipt, verified=after), m)
    restored = call('restore', original_paused=baseline['paused'])
    assert restored == {'paused': baseline['paused']}, 'Original gate state was not restored'
    durable(work, 'DELIVERY_REPAIR_GATE_RESTORED', str(baseline['paused']), m)


def hold(work, target, m, u):
    """A later release failure must re-pause even after successful collection."""
    body, digest = request(work)
    assert (work / PIN).read_text() == digest, 'Repair request changed before failure hold'
    result = invoke(work, target, worker_context(target, m, u),
                    dict(request=body, action='hold'), 'failure-hold', m)
    assert result == {'paused': True}, 'Failure hold could not confirm paused gate'
    durable(work, 'DELIVERY_REPAIR_FAILURE_HELD', 'Gate paused; edge remains closed; inspect recovery evidence', m)
