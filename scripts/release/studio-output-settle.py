"""Explicit, once-only incident settlement inside the inherited closed drain phase."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from uuid import UUID

REQUEST = 'studio-output-settle-request.private.json'
PIN = 'STUDIO_OUTPUT_SETTLE_REQUEST.sha256'
JOB = '5a190d2a-d2f5-4b20-b72f-2808a5483a1d'
EVENTS_SHA256 = 'e31cbb8d2749dcef06c2100c3b5059d02c6d6fe9df808cb472f7b66181989006'


def request(work):
    path = work / REQUEST
    assert path.resolve() == path.absolute(), 'Settlement request contains symlinks'
    metadata = path.stat()
    assert stat.S_ISREG(metadata.st_mode) and metadata.st_size <= 4096, 'Invalid settlement request'
    if os.name == 'posix':
        for item in (metadata, work.stat()):
            assert item.st_uid == os.geteuid() and not stat.S_IMODE(item.st_mode) & 0o077, 'Settlement evidence must be owner-only'
    raw = path.read_bytes()
    body = json.loads(raw)
    assert set(body) == {'actor_id', 'job_id', 'events_sha256'}, 'Unexpected settlement fields'
    assert str(UUID(body['actor_id'])) == body['actor_id'] and UUID(body['actor_id']).int, 'Invalid actor'
    assert body['job_id'] == JOB, 'Only the approved incident job is eligible'
    assert re.fullmatch('[0-9a-f]{64}', body['events_sha256']), 'Invalid event digest'
    assert body['events_sha256'] == EVENTS_SHA256, 'Only the approved incident events are eligible'
    return body, sha256(raw).hexdigest()


def pin(work, m):
    _, digest = request(work)
    helpers = m.module('studio-delivery-release-repair')
    if (work / PIN).exists():
        assert (work / PIN).read_text() == digest, 'Settlement request changed after preparation'
    else:
        helpers.durable(work, PIN, digest, m)


def run(work, target, m, d, u):
    body, digest = request(work)
    assert (work / PIN).read_text() == digest, 'Settlement request changed after preparation'
    assert (work / 'PREPARED').is_file() and (work / 'DEPLOY_STARTED').is_file(), 'Prepared deployment required'
    assert (work / 'PHASE').read_text() == 'drain', 'Settlement requires closed pre-drain phase'
    assert not (work / 'STUDIO_OUTPUT_SETTLE_STARTED').exists(), 'Settlement attempt requires inspected recovery, not replay'
    d.closed()
    assert not m.live(u.API)['State']['Running'], 'API must be stopped before settlement'
    helpers = m.module('studio-delivery-release-repair')
    context = helpers.worker_context(target, m, u)
    code = Path(__file__).with_name('studio-output-settle-runtime.py').read_text(encoding='utf-8')

    def call(action, **extra):
        d.closed()
        with (work / ('studio-output-settle-' + action + '.private.log')).open('w', encoding='utf-8') as log:
            os.chmod(log.name, 0o600)
            result = subprocess.run([str(target / '.venv/bin/python'), '-B', '-c', code],
                input=json.dumps(dict(request=body, action=action, **extra)), stdout=subprocess.PIPE,
                stderr=log, text=True, timeout=120, check=False, **context)
        helpers.durable(work, 'studio-output-settle-' + action + '.private.json', result.stdout, m)
        assert result.returncode == 0, 'Settlement failed; inspect private evidence and keep admission closed'
        return json.loads(result.stdout)

    baseline = call('inspect')
    assert type(baseline['paused']) is bool, 'Unknown original gate state'
    helpers.durable(work, 'STUDIO_OUTPUT_SETTLE_BASELINE.private.json',
                    dict(requestSha256=digest, target=str(target), baseline=baseline), m)
    helpers.durable(work, 'STUDIO_OUTPUT_SETTLE_STARTED',
        'Once-only approved job settlement; failure keeps admission closed. No model, collection or database restore.', m)
    assert call('pause', original_paused=baseline['paused']) == {'paused': True}, 'Execution gate did not pause'
    result = call('settle')
    assert result['status'] == 'succeeded' and result['executionCount'] == 1 and result['deliveryStatus'] is None
    helpers.durable(work, 'STUDIO_OUTPUT_SETTLE_VERIFIED.private.json', result, m)
    assert call('restore', original_paused=baseline['paused']) == baseline
