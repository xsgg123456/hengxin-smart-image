from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.modules.skills.models import ModuleSkillBinding, SkillRecord, SkillVersionRecord
from app.modules.templates.models import TemplateVersionRecord
from files_helpers import files_env
from test_templates import payload


def add_skill(factory, mode='wallpaper', status='available'):
    with factory.begin() as session:
        skill = SkillRecord(id=uuid4(), name='Skill-' + str(uuid4()), mode=mode, description='测试')
        session.add(skill)
        session.flush()
        version = SkillVersionRecord(id=uuid4(), skill_id=skill.id, version='1.0', status=status,
                                     checksum='a' * 64, bucket='test', object_key=str(uuid4()))
        session.add(version)
    return str(version.id)


def test_default_resolution_frozen_until_resave(files_env):
    client, factory, _, _ = files_env
    first_id, second_id = add_skill(factory), add_skill(factory)
    with factory.begin() as session:
        session.add(ModuleSkillBinding(mode='wallpaper', skill_version_id=UUID(first_id)))
    body = payload(client)
    original = client.post('/api/v1/templates', json=body).json()
    assert original['active'] and original['skillVersionId'] == first_id
    assert original['skillBinding'] == 'module_default'
    path = '/api/v1/templates/' + original['id']
    with factory.begin() as session:
        session.scalar(select(ModuleSkillBinding)).skill_version_id = UUID(second_id)
    assert client.get(path).json() == original
    updated = client.put(path, json={**body, 'expectedVersion': 1}).json()
    assert updated['skillVersionId'] == second_id and updated['version'] == 2
    assert client.get(path + '/versions').json() == [updated, original]
    with factory.begin() as session:
        session.get(SkillVersionRecord, UUID(second_id)).status = 'disabled'
    assert not client.get(path).json()['active']
    assert client.get('/api/v1/templates?activeOnly=true').json()['total'] == 0
    with factory() as session:
        versions = session.scalars(select(TemplateVersionRecord).order_by(TemplateVersionRecord.version)).all()
        assert all(version.enabled for version in versions)
        assert [str(version.skill_version_id) for version in versions] == [first_id, second_id]


@pytest.mark.parametrize('status', ['uploaded', 'installing', 'failed', 'disabled', 'available'])
def test_explicit_binding_preserved_without_fallback(files_env, status):
    client, factory, _, _ = files_env
    default_id, explicit_id = add_skill(factory), add_skill(factory, status=status)
    with factory.begin() as session:
        session.add(ModuleSkillBinding(mode='wallpaper', skill_version_id=UUID(default_id)))
    result = client.post('/api/v1/templates', json=payload(client, skillVersionId=explicit_id))
    assert result.status_code == 200, result.text
    template = result.json()
    assert template['skillVersionId'] == explicit_id
    assert template['skillBinding'] == 'specific'
    assert template['active'] == (status == 'available')


def test_invalid_binding_and_disabled_default(files_env):
    client, factory, _, _ = files_env
    wrong_id = add_skill(factory, mode='product')
    disabled_id = add_skill(factory, status='disabled')
    body = payload(client)
    for invalid_id in ['', 'bad', str(uuid4()), wrong_id]:
        assert client.post('/api/v1/templates', json={**body, 'skillVersionId': invalid_id}).status_code == 422
    with factory.begin() as session:
        session.add(ModuleSkillBinding(mode='wallpaper', skill_version_id=UUID(disabled_id)))
    result = client.post('/api/v1/templates', json=body).json()
    assert result['skillVersionId'] is None and not result['active']
    assert result['skillBinding'] == 'module_default'


def test_disabled_template_stays_disabled_with_available_skill(files_env):
    client, factory, _, _ = files_env
    body = payload(client, skillVersionId=add_skill(factory), active=False)
    result = client.post('/api/v1/templates', json=body).json()
    assert result['skillVersionId'] == body['skillVersionId'] and not result['active']
