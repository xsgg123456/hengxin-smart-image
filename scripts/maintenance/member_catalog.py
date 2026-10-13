"""Discover every incoming FK plus historical non-FK ownership columns."""
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import MetaData, Table, and_, create_engine, event, func, inspect, select, text

from member_codec import SafetyError, column_value, digest, encode


BUSINESSES = {
    'domestic': ('users', 'role_assignments', 'auth_sessions', 'domestic_membership_applications'),
    'overseas': ('overseas_members', 'overseas_member_roles', 'overseas_sessions',
                 'overseas_membership_applications'),
}
PERSON_COLUMNS = {'user_id', 'member_id', 'owner_id', 'operator_id', 'actor_id', 'created_by',
                  'designer_id', 'assigned_by', 'approved_by', 'reviewed_by', 'decided_by',
                  'before_designer_id', 'after_designer_id', 'deleted_by', 'resolved_by',
                  'revision_operator_id', 'request_operator_id'}


def source_fingerprint(engine, business, schema):
    url = engine.url
    database = url.database
    if engine.dialect.name == 'sqlite' and database and database != ':memory:':
        database = str(Path(database).resolve())
    return digest({'driver': url.drivername, 'host': url.host, 'port': url.port,
                   'database': database, 'business': business, 'schema': schema})


def engine_for(url):
    engine = create_engine(url, hide_parameters=True)
    if engine.dialect.name not in ('sqlite', 'postgresql'):
        engine.dispose()
        raise SafetyError('unsupported_database')
    if engine.dialect.name == 'sqlite':
        @event.listens_for(engine, 'connect')
        def foreign_keys(dbapi, _record):
            dbapi.execute('PRAGMA foreign_keys=ON')
            dbapi.execute('PRAGMA busy_timeout=5000')
    return engine


@contextmanager
def transaction(engine, writable=False):
    with engine.connect() as connection:
        previous_query_only = None
        try:
            if engine.dialect.name == 'sqlite':
                previous_query_only = connection.exec_driver_sql('PRAGMA query_only').scalar()
                connection.exec_driver_sql('PRAGMA query_only=' + ('OFF' if writable else 'ON'))
                connection.exec_driver_sql('BEGIN IMMEDIATE' if writable else 'BEGIN')
            elif writable:
                connection.execute(text("SET LOCAL lock_timeout = '5s'"))
                connection.execute(text('SET LOCAL row_security = off'))
            else:
                connection.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
                connection.execute(text('SET LOCAL row_security = off'))
            yield connection
            connection.commit() if writable else connection.rollback()
        except BaseException:
            connection.rollback()
            raise
        finally:
            if previous_query_only is not None:
                connection.rollback()
                connection.exec_driver_sql('PRAGMA query_only=' + ('ON' if previous_query_only else 'OFF'))


class Catalog:
    def __init__(self, connection, business, schema=None):
        if business not in BUSINESSES:
            raise SafetyError('business_required')
        self.connection, self.business = connection, business
        inspector = inspect(connection)
        self.schema = schema or inspector.default_schema_name
        if connection.dialect.name == 'postgresql':
            # pg_get_constraintdef omits schemas visible in search_path. Keeping only
            # pg_catalog forces every business FK target to be fully qualified.
            connection.execute(text('SET LOCAL search_path = pg_catalog'))
        schemas = inspector.get_schema_names()
        schemas = [name for name in schemas if not name.startswith('pg_') and name != 'information_schema']
        self.tables, self.edges = {}, []
        metadata = MetaData()
        for namespace in schemas:
            for name in inspector.get_table_names(schema=namespace):
                key = (namespace, name)
                self.tables[key] = Table(name, metadata, schema=namespace,
                                         autoload_with=connection, resolve_fks=False)
                for foreign_key in inspector.get_foreign_keys(name, schema=namespace):
                    target = (foreign_key['referred_schema'] or namespace, foreign_key['referred_table'])
                    self.edges.append((key, target, foreign_key['constrained_columns'],
                                       foreign_key['referred_columns'], 'foreign_key'))
        member, roles, sessions, application = BUSINESSES[business]
        self.member_key = (self.schema, member)
        self.identity_key = (self.schema, 'user_identities') if business == 'domestic' else None
        self.member = self.require(member, {'id', 'status'})
        if business == 'overseas':
            self.require(member, {'corp_id', 'provider_user_id'})
        self.roles = self.require(roles, {'user_id', 'role'})
        self.sessions = self.require(sessions, {'user_id'})
        self.identities = self.require('user_identities', {'id', 'user_id', 'provider', 'corp_id', 'provider_user_id'}) if self.identity_key else None
        self.application = self.tables.get((self.schema, application))
        if self.application is not None and not {'corp_id', 'provider_user_id'} <= set(self.application.c.keys()):
            raise SafetyError('unsupported_application_schema')
        for key, table in self.tables.items():
            # Detached archives deliberately retain member IDs without a foreign key.
            relevant = key[0] == self.schema and (key[1].startswith('overseas_') == (business == 'overseas'))
            if not relevant or key == self.member_key:
                continue
            for name in PERSON_COLUMNS.intersection(table.c.keys()):
                if not any(edge[0] == key and name in edge[2] for edge in self.edges):
                    self.edges.append((key, self.member_key, [name], ['id'], 'identity_column'))

    def require(self, name, columns):
        table = self.tables.get((self.schema, name))
        if table is None or not columns <= set(table.c.keys()):
            raise SafetyError('required_business_schema_missing')
        return table

    def related_keys(self):
        targets = {self.member_key, self.identity_key} - {None}
        keys = targets | {edge[0] for edge in self.edges if edge[1] in targets}
        if self.application is not None:
            keys.add((self.schema, self.application.name))
        return keys

    def lock(self):
        if self.connection.dialect.name == 'postgresql':
            formatter = self.connection.dialect.identifier_preparer
            names = ', '.join(formatter.format_table(self.tables[key]) for key in sorted(self.related_keys()))
            self.connection.exec_driver_sql(f'LOCK TABLE {names} IN SHARE ROW EXCLUSIVE MODE')

    def references(self, target, row, identity_leaf=False):
        output = []
        for source, parent, local, remote, kind in self.edges:
            if parent != target:
                continue
            table = self.tables[source]
            predicate = and_(*(table.c[left] == column_value(table.c[left], row[right])
                               for left, right in zip(local, remote)))
            count = self.connection.scalar(select(func.count()).select_from(table).where(predicate))
            if count:
                leaf = (identity_leaf and source == self.identity_key and local == ['user_id']
                        and remote == ['id'] and kind == 'foreign_key')
                summary = {'table': '.'.join(source), 'columns': local, 'count': count,
                           'kind': kind, 'allowedIdentityLeaf': leaf}
                if 'audit' in table.name:
                    names = ('id', 'member_id', 'actor_id', 'operator_id', 'action', 'version', 'created_at')
                    columns = [table.c[name] for name in names if name in table.c]
                    if columns:
                        summary['auditEntries'] = encode([dict(item) for item in self.connection.execute(
                            select(*columns).where(predicate)).mappings()])
                output.append(summary)
        return output

    def inventory(self):
        targets = {self.member_key, self.identity_key} - {None}
        return [{'table': '.'.join(source), 'columns': local, 'target': '.'.join(parent),
                 'targetColumns': remote, 'kind': kind}
                for source, parent, local, remote, kind in self.edges if parent in targets]
