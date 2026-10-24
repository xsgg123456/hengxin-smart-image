"""Offline deployment guards and isolated real-backend incident settlement."""
import copy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from uuid import UUID

import pytest

BACKEND = Path(__file__).resolve().parents[2] / 'hengxin-smart-image/backend'
sys.path[:0] = [str(BACKEND), str(BACKEND / 'tests')]
from studio_delivery_helpers import DeliveryCase, studio, materials, overseas
from app.overseas.execution.models import ExecutionGate, Job, JobOutbox
from app.overseas.studio.models import Turn, ConversationDeletion
from app.overseas.tasks.models import TaskDeletion
from app.overseas.management.models import Audit
from sqlalchemy import select


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def save(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body if isinstance(body, str) else json.dumps(body), encoding='utf-8')


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('ENABLE_DEV_IDENTITY', 'false')


def test_release_wires_current_baseline_additive_migration_and_inherited_checks():
    r = load('studio-output-deploy')
    assert (r.d.BASE_VERSION, r.d.TARGET_VERSION) == ('0.2.51', '0.2.52')
    assert (r.d.DOMESTIC_MIGRATION, r.d.TARGET_MIGRATION) == ('0032', 'overseas_0022')
    assert r.a.BASE_RELEASE == 'overseas-20261024-59ceb83'
    assert r.u.DROP > 'zzzzzzzzzzz-studio-delivery-reliability-20261024.conf'
    assert r.EXPECTED_COMPOSE_TAIL[0] == r.s.GRANT_OVERLAY
    assert r.previous.EXPECTED_COMPOSE_TAIL == r.EXPECTED_COMPOSE_TAIL[-2:]
    assert r.d.before_switch is r.before_switch and r.d.prepare is r.prepare
    assert r.d.drain_and_stop is r.drain_and_stop
    assert r.d.installed is r.previous.installed and r.d.deploy is r.previous.deploy
    assert r.d.wait_empty is r.s.wait_empty and r.u.backup is r.a.a.backup
    assert r.d.installed_schemas is r.installed_schemas
    assert {'tests/test_studio_open_outputs.py', 'tests/test_overseas_studio_file_recovery.py'} <= set(r.previous.TESTS)
    assert 'Never downgrade or restore production' in r.d.MIGRATION_RECOVERY


def test_package_keeps_clean_source_review_and_private_fixture_exclusion():
    p = load('package-studio-output')
    assert p.p.VERSION == '0.2.52' and p.p.OVERSEAS_MIGRATION == 'overseas_0022'
    assert 'package-studio-output.py' in p.p.PACKAGING_HELPERS
    assert all(p.selected(name) == name and name in p.p.REQUIRED for name in p.HELPERS)
    assert p.selected('hengxin-smart-image/backend/app/overseas/studio/recovery_files.py') == 'backend/app/overseas/studio/recovery_files.py'
    for name in ('output/incident/events.jsonl', 'scripts/release/studio-output-settle-request.private.json',
                 'hengxin-smart-image/backend/.env', 'hengxin-smart-image/backend/tests/private-rollout.jsonl'):
        assert p.selected(name) is None
    with pytest.raises(ValueError, match='Commit all'):
        p.p.require_clean_tracked(lambda *_: b' M AGENTS.md')


def test_prepare_refuses_unpinned_incident_or_grant_chain_drift(monkeypatch, tmp_path):
    r = load('studio-output-deploy')
    monkeypatch.setattr(r.m, 'live', lambda _: {'Config': {'Labels': {
        'com.docker.compose.project.config_files': ','.join(r.EXPECTED_COMPOSE_TAIL[1:])}}})
    monkeypatch.setattr(r, '_preflight', lambda: pytest.fail('Must reject missing grant first'))
    with pytest.raises(AssertionError, match='Compose chain drift'):
        r.preflight()
    save(tmp_path / r.settle.REQUEST, {'job_id': r.settle.JOB, 'actor_id': str(UUID(int=1)), 'events_sha256': '0' * 64})
    monkeypatch.setattr(r, '_prepare', lambda *a: pytest.fail('Must reject incident evidence first'))
    with pytest.raises(AssertionError, match='approved incident events'):
        r.prepare(tmp_path, tmp_path / 'src', {}, 'image')


def test_migration_requires_restored_backup_and_drain(tmp_path):
    r = load('studio-output-deploy')
    with pytest.raises(AssertionError, match='backup missing'):
        r.before_switch(tmp_path, tmp_path / 'src', 'image', {}, tmp_path / 'backup')
    save(tmp_path / 'backup/COMPLETE', 'verified')
    with pytest.raises(AssertionError, match='not drained'):
        r.before_switch(tmp_path, tmp_path / 'src', 'image', {}, tmp_path / 'backup')


@pytest.mark.parametrize('drift', ['none', 'row', 'column', 'table', 'nonempty'])
def test_additive_schema_preserves_every_old_field_and_row(monkeypatch, drift):
    r = load('studio-output-data')
    names, fields = ['overseas_tasks'], [{'table_name': 'overseas_tasks', 'column_name': 'id'}]
    monkeypatch.setattr(r.base, 'tables', lambda _: names)
    monkeypatch.setattr(r.base, 'columns', lambda _: fields)
    monkeypatch.setattr(r.base, 'original_rows', lambda _: {'overseas_tasks': 'unchanged'})
    baseline = r.before(lambda _: '0')
    names = names + [r.TABLE]
    fields = fields + [{'table_name': r.TABLE, 'column_name': 'id'}]
    if drift == 'row':
        monkeypatch.setattr(r.base, 'original_rows', lambda _: {'overseas_tasks': 'changed'})
    elif drift == 'column':
        fields[0] = {**fields[0], 'column_name': 'changed'}
    elif drift == 'table':
        names.append('unexpected')
    if drift == 'none':
        r.verify(lambda _: '0', baseline)
    else:
        with pytest.raises(AssertionError):
            r.verify(lambda _: '1' if drift == 'nonempty' else '0', baseline)


def test_settlement_only_runs_after_closed_api_then_inherited_drain(monkeypatch, tmp_path):
    r = load('studio-output-deploy')
    events = []
    save(tmp_path / r.settle.REQUEST, '{}')
    monkeypatch.setattr(r.settle, 'run', lambda *a: events.append('settle'))
    monkeypatch.setattr(r, '_drain_and_stop', lambda *a: events.append('drain'))
    r.drain_and_stop(tmp_path)
    assert events == ['settle', 'drain']


@pytest.mark.parametrize('phase', ['unprepared', 'before-drain', 'replay'])
def test_settlement_driver_refuses_wrong_phase_before_any_process_call(monkeypatch, tmp_path, phase):
    r = load('studio-output-deploy')
    body = dict(job_id=r.settle.JOB, actor_id=str(UUID(int=1)), events_sha256=r.settle.EVENTS_SHA256)
    monkeypatch.setattr(r.settle, 'request', lambda _: (body, 'digest'))
    save(tmp_path / r.settle.PIN, 'digest')
    if phase != 'unprepared':
        save(tmp_path / 'PREPARED', 'image')
        save(tmp_path / 'DEPLOY_STARTED', 'release')
        save(tmp_path / 'PHASE', 'drain' if phase == 'replay' else 'close-intake')
    if phase == 'replay': save(tmp_path / 'STUDIO_OUTPUT_SETTLE_STARTED', 'already tried')
    monkeypatch.setattr(r.d, 'closed', lambda: pytest.fail('Must reject before any service probe'))
    with pytest.raises(AssertionError):
        r.settle.run(tmp_path, Path('/old/backend'), r.m, r.d, r.u)


def test_installed_regressions_use_actual_readonly_installation(monkeypatch, tmp_path):
    r = load('studio-output-deploy')
    save(tmp_path / 'src/release.json', '{}')
    monkeypatch.setattr(r.m, 'private', save)
    calls = []
    monkeypatch.setattr(r.previous.subprocess, 'run', lambda args, **kw: calls.append((args, kw)))
    r.s.native_install_test(tmp_path, tmp_path / 'src', {'files': {}}, 'image', Path('/installed/backend'))
    args, options = calls[0]
    for name in ('test_studio_open_outputs.py', 'test_overseas_studio_file_recovery.py', 'test_studio_output_lifecycle.py'):
        assert 'tests/' + name in args
    assert '--network' in args and 'none' in args and 'PYTHONPATH=/installed' in args
    assert 'type=bind,src=' + str(Path('/installed/backend')) + ',dst=/installed,readonly' in args
    assert '--env-file' not in args and options['check']


@pytest.fixture
def incident(studio, monkeypatch, tmp_path):
    from app.execution import process
    from app.overseas.execution import runner
    r = load('studio-output-settle-runtime')
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)
    case.run()
    monkeypatch.setattr(process, 'same_process', lambda *_: False)
    monkeypatch.setattr(r, 'JOB', str(case.job_id))
    digest = sha256((case.workspace.control / 'events.jsonl').read_bytes()).hexdigest()
    monkeypatch.setattr(r, 'EVENTS_SHA256', digest)
    with case.factory.begin() as session:
        job = session.get(Job, case.job_id)
        job.status, job.completed_at = 'uncertain', None
        job.result = {**job.result, 'deliveryStatus': {'state': 'capturing', 'saved': 1, 'expected': 2}}
        session.get(JobOutbox, job.id).completed_at = None
        session.get(ExecutionGate, 1).paused = False
    monkeypatch.setattr(runner, 'execute', lambda *_: pytest.fail('Settlement must never invoke a model'))
    case.runtime = r
    case.request = dict(actor_id=str(case.actor), job_id=str(case.job_id), events_sha256=digest)
    return case


def invoke(case, action, **kwargs):
    return case.runtime.execute(dict(request=case.request, action=action, **kwargs), case.factory)


def gate(case):
    with case.factory() as session:
        return session.get(ExecutionGate, 1).paused


def test_settle_preserves_outputs_and_reply_closes_outbox_once(incident):
    c = incident
    files = {p: p.read_bytes() for p in c.workspace.control.rglob('*') if p.is_file()}
    stored, job = copy.deepcopy(c.store.data), c.job()
    assert invoke(c, 'inspect') == {'paused': False}
    invoke(c, 'pause', original_paused=False)
    after = invoke(c, 'settle')
    assert after['status'] == 'succeeded' and after['executionCount'] == 1 and after['deliveryStatus'] is None
    assert c.job().result['reply'] == job.result['reply'] and c.job().claim_token == job.claim_token
    assert c.job().result['sessionId'] == job.result['sessionId']
    assert c.job().started_at == job.started_at and c.store.data == stored
    assert c.current()['deliveryError'] == c.runtime.NOTICE and c.view()['activeTurnId'] is None
    assert files == {p: p.read_bytes() for p in c.workspace.control.rglob('*') if p.is_file()}
    with c.factory() as session:
        assert session.get(JobOutbox, c.job_id).completed_at is not None
        assert len(list(session.scalars(select(Audit).where(Audit.action == c.runtime.ACTION)))) == 1
    with pytest.raises(AssertionError, match='uncertain invocation'):
        invoke(c, 'settle')
    assert gate(c)
    assert invoke(c, 'restore', original_paused=False) == {'paused': False}


@pytest.mark.parametrize('drift', ['job', 'events', 'bytes', 'count', 'cancel', 'worker', 'process', 'group',
    'exit', 'reply', 'task_deletion', 'conversation_deletion', 'unpaused', 'not_exited', 'missing_process', 'incomplete'])
def test_settlement_refuses_unsafe_or_unrelated_execution(incident, monkeypatch, drift):
    from app.execution import process
    from app.overseas.tasks import cleanup_process
    c = incident
    invoke(c, 'pause', original_paused=False)
    if drift == 'job':
        c.request['job_id'] = str(UUID(int=2))
    elif drift == 'events':
        c.request['events_sha256'] = '0' * 64
    elif drift == 'bytes':
        (c.workspace.control / 'events.jsonl').write_text('changed')
    elif drift == 'process':
        monkeypatch.setattr(process, 'same_process', lambda *_: True)
    elif drift == 'group':
        monkeypatch.setattr(cleanup_process, 'group_alive', lambda *_: True)
    elif drift == 'exit':
        save(c.workspace.control / 'delivery-exit.json', {'exit_code': 1})
    elif drift == 'incomplete':
        monkeypatch.setattr(c.runtime, 'EVENTS_SHA256', sha256(b'{}').hexdigest())
        c.request['events_sha256'] = c.runtime.EVENTS_SHA256
        (c.workspace.control / 'events.jsonl').write_bytes(b'{}')
    with c.factory.begin() as session:
        job = session.get(Job, c.job_id)
        turn = session.get(Turn, UUID(c.turn['id']))
        if drift == 'count': job.execution_count = 2
        if drift == 'cancel': job.cancel_requested = True
        if drift == 'worker': job.worker_node = 'foreign-worker'
        if drift == 'not_exited': job.process_exited = False
        if drift == 'missing_process': job.process_started = None
        if drift == 'reply': turn.reply = 'different'
        if drift == 'unpaused': session.get(ExecutionGate, 1).paused = False
        if drift == 'task_deletion': session.add(TaskDeletion(task_id=job.task_id, actor_id=c.actor))
        if drift == 'conversation_deletion':
            session.add(ConversationDeletion(conversation_id=turn.conversation_id, task_id=job.task_id, actor_id=c.actor))
    stored = copy.deepcopy(c.store.data)
    with pytest.raises((AssertionError, ValueError)):
        invoke(c, 'settle')
    assert c.job().status == 'uncertain' and c.store.data == stored
    with c.factory() as session:
        assert not list(session.scalars(select(Audit).where(Audit.action == c.runtime.ACTION)))
