"""A complete offline package through the real installation and HTTP selection path."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4
from sqlalchemy.orm import sessionmaker

NAME = 'offline-integration-skill'
DISPLAY = '离线验收 Skill（非生产素材）'
RESOURCE = b'offline complete resource\x00\xff'


def publish(version):
    from app.overseas.management.skill_install import bundle, install
    base = Path('/tmp/skill-fixtures')
    package = base / 'source' / NAME
    (package / 'references').mkdir(parents=True, exist_ok=True)
    (package / 'assets').mkdir(exist_ok=True)
    (package / 'SKILL.md').write_text(f'---\nname: {NAME}\ndescription: 离线安装与完整资源验收\n---\n'
        '[参考](references/spec.md)\n[资源](assets/sample.bin)\n', encoding='utf-8')
    (package / 'references/spec.md').write_text(version, encoding='utf-8')
    (package / 'assets/sample.bin').write_bytes(RESOURCE)
    mapping = base / 'mapping.json'
    mapping.write_text(json.dumps([dict(name=NAME, source=NAME, displayName=DISPLAY)]), encoding='utf-8')
    result = bundle(base / 'source', mapping, base / 'bundles')
    assert result['packages'] == 1 and result['files'] == 3
    install(result['path'])
    return result


def prepare(h):
    os.environ.update(h.environment('overseas'))
    from app.core.config import get_settings
    get_settings.cache_clear()
    Path(get_settings().local_skill_root).mkdir(parents=True, exist_ok=True)
    publish('original-reference')


def run(h, admin, designer, base, task_id):
    from app.overseas.execution.models import Job
    from app.overseas.execution.materials import prepare as prepare_round
    management = h.expect(admin.get(base + '/management/skills'), 200).json()['items']
    assert len(management) == 1 and management[0]['displayName'] == DISPLAY
    assert set(management[0]) == {'id', 'name', 'displayName', 'description'}
    path = base + '/tasks/' + task_id + '/studio'
    assert h.expect(designer.get(path), 200).json()['skills'] == management
    h.expect(designer.get(base + '/management/skills'), 403)
    h.expect(admin.post(base + '/management/skills', json={}), 405)
    for suffix in ('/' + management[0]['id'], '/' + management[0]['id'] + '/versions'):
        assert admin.patch(base + '/management/skills' + suffix, json={}).status_code in (404, 405)
    result = h.expect(designer.post(path + '/turns', json={'text': '仅验证排队，不执行模型',
        'skillId': management[0]['id']}, headers={'Idempotency-Key': str(uuid4())}), 200).json()
    turn = result['turns'][-1]
    assert turn['skillName'] == DISPLAY and turn['status'] == 'queued'
    factory = sessionmaker(h.ENGINES['overseas'], expire_on_commit=False)
    with factory() as session:
        job = session.get(Job, UUID(turn['jobId']))
        old_release = job.payload['skill']['installedRelease']
        payload = job.payload
    assert publish('new-reference')['release'] != old_release
    work = Path('/tmp/frozen-skill-round')
    control = work.parent / 'frozen-skill-control'
    work.mkdir(exist_ok=True)
    control.mkdir(exist_ok=True)
    workspace = SimpleNamespace(work=work, control=control)
    prepare_round(SimpleNamespace(payload=payload), workspace)
    assert (workspace.local_skill / 'references/spec.md').read_text() == 'original-reference'
    assert (workspace.local_skill / 'assets/sample.bin').read_bytes() == RESOURCE
    h.expect(designer.post(path + '/turns/' + turn['id'] + '/cancel',
        json={'version': turn['jobVersion']}), 200)
    print('PASS installed catalog matches studio, web writes removed, complete frozen resources '
          'survive installation update; zero model calls', flush=True)
