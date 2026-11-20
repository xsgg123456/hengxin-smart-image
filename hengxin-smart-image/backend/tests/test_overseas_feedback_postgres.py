from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import subprocess
import sys

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.overseas.auth.models import Member, MemberRole
from app.overseas.db import SCHEMA_REVISION
from app.overseas.feedback import service
from app.overseas.feedback.models import Feedback, FeedbackGrant
from app.overseas.feedback.schemas import CreateFeedback, UpdateFeedback
from test_overseas_database import BACKEND, disposable_databases, migrate, migration_environment, snapshot


@pytest.mark.integration
def test_feedback_additive_migration_and_concurrent_edit(disposable_databases):
    url, domestic = disposable_databases
    env = migration_environment(url)
    old = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
                          'upgrade', 'overseas_0026'], cwd=BACKEND, env=env, text=True, capture_output=True)
    assert old.returncode == 0, old.stderr
    engine = create_engine(url)
    factory = sessionmaker(engine, expire_on_commit=False)
    actor = uuid4()
    try:
        with factory.begin() as session:
            session.add(Member(id=actor, corp_id='fixture', provider_user_id='manager', name='经理', status='active'))
            session.flush()
            session.add(MemberRole(user_id=actor, role='design_manager'))
        before, other = snapshot(url), snapshot(domestic)
        for _ in range(2):
            upgraded = migrate(env)
            assert upgraded.returncode == 0, upgraded.stderr
        after = snapshot(url)
        assert set(after[0]) - set(before[0]) == {'overseas_feedback', 'overseas_feedback_grants'}
        assert all(before[1][key] == after[1][key] for key in before[0] if key != 'overseas_alembic_version')
        assert after[1]['overseas_alembic_version'] == [(SCHEMA_REVISION,)]
        assert snapshot(domestic) == other
        assert len(inspect(engine).get_indexes('overseas_feedback')) == 2
        with factory.begin() as session:
            session.add(FeedbackGrant(id=actor))
        with factory() as session:
            sku = '、'.join(f'{n:02}' + '灯' * 78 for n in range(100))
            row = service.create(session, actor, CreateFeedback(question='需要协助', source='工作台', sku=sku), None)
            assert session.get(Feedback, row['id']).sku == sku
        race = Barrier(2)

        def change(reply):
            with factory() as session:
                manager = session.get(Member, actor)
                race.wait(timeout=10)
                try:
                    return service.change(session, manager, row['id'], UpdateFeedback(
                        version=1, status='resolved', public_reply=reply))['public_reply']
                except HTTPException as exc:
                    return exc.status_code

        with ThreadPoolExecutor(2) as pool:
            outcomes = list(pool.map(change, ['已完成 A', '已完成 B']))
        assert outcomes.count(409) == 1
        with factory() as session:
            saved = session.get(Feedback, row['id'])
            assert saved.version == 2 and saved.status == 'resolved' and saved.public_reply in outcomes
    finally:
        engine.dispose()
