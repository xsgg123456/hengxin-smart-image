"""All tests create independent temporary databases; never import app settings."""
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Column, DateTime, ForeignKey, Integer, MetaData, String, Table, Uuid, insert

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from member_catalog import BUSINESSES, engine_for


@pytest.fixture(autouse=True)
def cleanup_isolated_artifacts(tmp_path, tmp_path_factory):
    yield
    target = tmp_path.resolve()
    boundary = tmp_path_factory.getbasetemp().resolve()
    if target != boundary and target.is_relative_to(boundary) and target.exists():
        shutil.rmtree(target)


def schema_tables(engine, business):
    metadata = MetaData()
    member, roles, sessions, applications = BUSINESSES[business]
    columns = [Column('id', Uuid, primary_key=True), Column('name', String), Column('status', String),
               Column('directory_state', String), Column('created_at', DateTime(timezone=True)),
               Column('updated_at', DateTime(timezone=True))]
    if business == 'overseas':
        columns += [Column('corp_id', String), Column('provider_user_id', String), Column('union_id', String),
                    Column('department', String), Column('version', Integer)]
    else:
        columns += [Column('role', String), Column('identity_source', String)]
    tables = {'member': Table(member, metadata, *columns)}
    tables['roles'] = Table(roles, metadata, Column('id', Uuid, primary_key=True),
        Column('user_id', Uuid, ForeignKey(member + '.id', ondelete='CASCADE')), Column('role', String))
    tables['sessions'] = Table(sessions, metadata, Column('id', Uuid, primary_key=True),
        Column('user_id', Uuid, ForeignKey(member + '.id', ondelete='CASCADE')), Column('token_hash', String),
        Column('identity_session_id', String), Column('revoked_at', DateTime))
    tables['applications'] = Table(applications, metadata, Column('id', Uuid, primary_key=True),
        Column('corp_id', String), Column('provider_user_id', String), Column('status', String),
        Column('version', Integer))
    if business == 'domestic':
        tables['identities'] = Table('user_identities', metadata, Column('id', Uuid, primary_key=True),
            Column('user_id', Uuid, ForeignKey(member + '.id', ondelete='CASCADE')), Column('provider', String),
            Column('corp_id', String), Column('provider_user_id', String), Column('union_id', String),
            Column('department', String), Column('created_at', DateTime(timezone=True)))
    tables['history'] = Table(('overseas_' if business == 'overseas' else '') + 'unexpected_history', metadata,
        Column('id', Uuid, primary_key=True), Column('recipient', Uuid, ForeignKey(member + '.id', ondelete='CASCADE')))
    tables['archives'] = Table(('overseas_' if business == 'overseas' else '') + 'archives', metadata,
        Column('id', Uuid, primary_key=True), Column('created_by', Uuid), Column('designer_id', Uuid))
    metadata.create_all(engine)
    return tables


def seed(engine, tables, business, **overrides):
    identifier = uuid4()
    timestamp = datetime.now(timezone.utc)
    values = dict(id=identifier, name='同名员工', status='pending', directory_state='legacy_unconfirmed',
                  created_at=timestamp, updated_at=timestamp)
    if business == 'overseas':
        values.update(corp_id='corp', provider_user_id=str(identifier), version=1,
                      union_id='union', department='测试')
    else:
        values.update(role=None, identity_source='dingtalk')
    values.update(overrides)
    with engine.begin() as connection:
        connection.execute(insert(tables['member']).values(**values))
        if business == 'domestic':
            connection.execute(insert(tables['identities']).values(id=uuid4(), user_id=identifier,
                provider='dingtalk', corp_id='corp', provider_user_id=str(identifier), union_id='union',
                department='测试', created_at=timestamp))
    return identifier


@pytest.fixture(params=['domestic', 'overseas'])
def database(tmp_path, request):
    engine = engine_for('sqlite:///' + (tmp_path / 'isolated.sqlite').as_posix())
    tables = schema_tables(engine, request.param)
    try:
        yield engine, request.param, tables
    finally:
        engine.dispose()
