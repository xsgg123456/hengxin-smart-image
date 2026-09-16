from fastapi import HTTPException
from sqlalchemy import select

from app.contracts.management import SettingsInput
from app.modules.management.models import SettingsAuditRecord
from app.modules.management.settings import read_settings, save_settings
from test_tasks_concurrency import pg_tasks, compete


def test_two_connections_cannot_overwrite_same_settings_version(pg_tasks):
    factory, user, _, _ = pg_tasks
    with factory() as session:
        original = read_settings(session)
    original.pop('audit')
    original.pop('capacity')
    original.pop('timeoutCapacity')
    original['dingtalk'].pop('state')

    def save(index):
        with factory() as session:
            try:
                result = save_settings(session, user, SettingsInput(**{
                    **original, 'timeoutSeconds': 120 + index * 60}))
                return result['version']
            except HTTPException as error:
                session.rollback()
                return error.status_code

    assert sorted(compete(save)) == [2, 409]
    with factory() as session:
        audits = session.scalars(select(SettingsAuditRecord)).all()
        assert len(audits) == 1
        assert read_settings(session)['timeoutSeconds'] == audits[0].after['timeoutSeconds']
