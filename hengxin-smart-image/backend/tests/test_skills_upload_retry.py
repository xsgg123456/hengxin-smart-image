from uuid import UUID

import pytest
from files_helpers import files_env
from test_skills import skills_env, upload
from test_skills_packages import archive
from app.modules.skills.models import SkillVersionRecord


@pytest.mark.parametrize('written_before_error', [False, True])
def test_storage_failure_can_reupload_identical_package_only(skills_env, monkeypatch, written_before_error):
    client, factory, store, _ = skills_env
    attempts = []

    def put(record, data):
        attempts.append(record.object_key)
        if len(attempts) == 1:
            if written_before_error:
                store.objects[record.object_key] = data
            raise OSError('storage disconnected')
        store.objects[record.object_key] = data

    monkeypatch.setattr(store, 'put', put)
    data = archive()
    assert upload(client, data=data).status_code == 503
    failed = client.get('/api/v1/management/skills').json()[0]
    assert client.post(f"/api/v1/management/skills/{failed['id']}/install").status_code == 409
    assert upload(client, data=data + b'changed').status_code == 409
    recovered = upload(client, data=data)
    assert recovered.status_code == 201, recovered.text
    assert recovered.json()['id'] == failed['id']
    assert recovered.json()['status'] == 'uploaded'
    assert attempts[0] == attempts[1]
    with factory() as session:
        record = session.get(SkillVersionRecord, UUID(failed['id']))
        assert store.objects[record.object_key] == data
    assert upload(client, data=data).status_code == 409
    assert client.post(f"/api/v1/management/skills/{failed['id']}/install").status_code == 200
