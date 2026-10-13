"""Read-only classification; eligibility is never an approval to delete."""
from datetime import datetime, timezone

from sqlalchemy import and_, func, select

from member_catalog import Catalog, source_fingerprint, transaction
from member_codec import SafetyError, column_value, digest, encode, safe_rows


def now():
    return datetime.now(timezone.utc).isoformat()


def member_snapshot(catalog, row):
    identities = []
    if catalog.identities is not None:
        table = catalog.identities
        identities = [dict(item) for item in catalog.connection.execute(
            select(table).where(table.c.user_id == row['id']).order_by(table.c.id)).mappings()]
    return {'member': dict(row), 'identities': identities}


def identity_summary(catalog, snapshot):
    rows = snapshot['identities'] if catalog.identities is not None else [snapshot['member']]
    return sorted([{'provider': item.get('provider', 'dingtalk'), 'corpId': item['corp_id'],
                    'providerUserId': item['provider_user_id']} for item in rows],
                  key=lambda item: (item['provider'], item['corpId'], item['providerUserId']))


def application_evidence(catalog, identities):
    table = catalog.application
    if table is None:
        return []
    output = []
    for identity in identities:
        if identity['provider'] != 'dingtalk':
            continue
        predicate = and_(table.c.corp_id == identity['corpId'],
                         table.c.provider_user_id == identity['providerUserId'])
        columns = [table.c[name] for name in ('id', 'status', 'version', 'created_at', 'updated_at') if name in table.c]
        output.extend(encode([dict(row) for row in catalog.connection.execute(select(*columns).where(predicate)).mappings()]))
    return output


def inspect_member(catalog, row):
    snapshot = member_snapshot(catalog, row)
    identities = identity_summary(catalog, snapshot)
    refs = catalog.references(catalog.member_key, row, identity_leaf=True)
    for identity in snapshot['identities']:
        refs.extend(catalog.references(catalog.identity_key, identity))
    roles = list(catalog.connection.scalars(select(catalog.roles.c.role).where(catalog.roles.c.user_id == row['id'])))
    if row.get('role'):
        roles.append(row['role'])
    roles = sorted(set(roles))
    sessions = catalog.connection.scalar(select(func.count()).select_from(catalog.sessions).where(
        catalog.sessions.c.user_id == row['id']))
    applications = application_evidence(catalog, identities)
    reasons = []
    if row['status'] != 'pending' or row.get('directory_state') != 'legacy_unconfirmed':
        reasons.append('not_legacy_pending')
    if roles:
        reasons.append('authorization_exists')
    if sessions:
        reasons.append('session_history_exists')
    if applications:
        reasons.append('application_history_exists')
    if any(not ref['allowedIdentityLeaf'] for ref in refs):
        reasons.append('references_exist')
    if not identities or any(not item['corpId'] or not item['providerUserId'] or item['provider'] != 'dingtalk' for item in identities):
        reasons.append('identity_unconfirmed')
    if catalog.application is None or 'directory_state' not in row:
        reasons.append('isolation_migration_required')
    try:
        safe_rows([snapshot['member'], *snapshot['identities']])
    except SafetyError:
        reasons.append('unsafe_recovery_schema')
    expected = {'status': row['status'], 'directoryState': row.get('directory_state'),
                'version': row.get('version'), 'identities': identities, 'snapshotSha256': digest(snapshot)}
    evidence = 'authorization_or_business_history' if roles or sessions or any(
        not ref['allowedIdentityLeaf'] for ref in refs) else 'explicit_application' if applications else 'source_unconfirmed'
    return {'id': str(row['id']), 'name': row.get('name'), 'createdAt': encode(row.get('created_at')),
            'expected': expected, 'roles': roles, 'sessionCount': sessions, 'applications': applications,
            'references': refs, 'classification': evidence, 'cleanupEligible': not reasons,
            'skipReasons': reasons}, snapshot


def audit(engine, business, schema=None):
    with transaction(engine) as connection:
        catalog = Catalog(connection, business, schema)
        members = [inspect_member(catalog, row)[0] for row in connection.execute(
            select(catalog.member).order_by(catalog.member.c.id)).mappings()]
        application_total = connection.scalar(select(func.count()).select_from(catalog.application)) if catalog.application is not None else None
        return {'formatVersion': 1, 'operation': 'audit', 'business': business,
                'schema': catalog.schema, 'createdAt': now(),
                'sourceFingerprint': source_fingerprint(engine, business, catalog.schema),
                'referenceInventory': catalog.inventory(), 'members': members,
                'counts': {'total': len(members), 'cleanupCandidates': sum(item['cleanupEligible'] for item in members),
                           'applications': application_total,
                           'enrolled': sum(item['expected']['directoryState'] == 'enrolled' for item in members),
                           'legacy': sum(item['expected']['directoryState'] == 'legacy_unconfirmed' for item in members)}}


def get_member(catalog, member_id):
    return catalog.connection.execute(select(catalog.member).where(
        catalog.member.c.id == column_value(catalog.member.c.id, member_id))).mappings().first()
