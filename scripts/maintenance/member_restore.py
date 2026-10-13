"""Restore reviewed legacy shells only; never restore sessions or overwrite rows."""
from sqlalchemy import and_, insert, select
from sqlalchemy.exc import DBAPIError

from member_audit import get_member, identity_summary, member_snapshot, now
from member_catalog import source_fingerprint, transaction
from member_codec import SafetyError, decode, digest, safe_rows
from member_reconcile import locked_catalog, validate_approval


def validate_bundle(bundle, business):
    if not isinstance(bundle, dict) or bundle.get('operation') != 'restore_legacy_member' or bundle.get('business') != business:
        raise SafetyError('invalid_recovery_bundle')
    content = {key: value for key, value in bundle.items() if key != 'sha256'}
    if digest(content) != bundle.get('sha256'):
        raise SafetyError('recovery_integrity_failure')
    validate_approval({**bundle, 'members': [bundle['approved']]}, business)
    snapshot = decode(bundle['snapshot'])
    if set(snapshot) != {'member', 'identities'} or not isinstance(snapshot['identities'], list):
        raise SafetyError('invalid_recovery_snapshot')
    safe_rows([snapshot['member'], *snapshot['identities']])
    row = snapshot['member']
    if row.get('status') != 'pending' or row.get('directory_state') != 'legacy_unconfirmed' or row.get('role'):
        raise SafetyError('restore_must_remain_unprivileged_legacy')
    if str(row.get('id')) != bundle['approved']['id'] or digest(snapshot) != bundle['approved']['expected']['snapshotSha256']:
        raise SafetyError('recovery_snapshot_mismatch')
    return snapshot


def restore(engine, business, bundle, *, schema=None, apply=False):
    snapshot = validate_bundle(bundle, business)
    member_id = bundle['approved']['id']
    result = {'formatVersion': 1, 'business': business, 'operation': 'restore',
              'id': member_id, 'apply': apply, 'createdAt': now(),
              'reviewedBy': bundle['reviewedBy'], 'reason': bundle['reason']}
    try:
        with transaction(engine, writable=apply) as connection:
            catalog = locked_catalog(connection, business, schema, apply)
            if (catalog.schema != bundle['schema'] or
                    source_fingerprint(engine, business, catalog.schema) != bundle['sourceFingerprint']):
                raise SafetyError('source_fingerprint_mismatch')
            if set(snapshot['member']) != set(catalog.member.c.keys()):
                raise SafetyError('recovery_schema_mismatch')
            if catalog.identities is None and snapshot['identities']:
                raise SafetyError('unexpected_identity_rows')
            if catalog.identities is not None:
                for identity in snapshot['identities']:
                    if set(identity) != set(catalog.identities.c.keys()) or identity['user_id'] != snapshot['member']['id']:
                        raise SafetyError('recovery_identity_mismatch')
            if identity_summary(catalog, snapshot) != bundle['approved']['expected']['identities']:
                raise SafetyError('recovery_identity_mismatch')
            existing = get_member(catalog, member_id)
            if existing is not None:
                outcome = 'already_restored' if digest(member_snapshot(catalog, existing)) == digest(snapshot) else 'skipped_existing_changed'
                return {**result, 'outcome': outcome}
            table = catalog.identities if catalog.identities is not None else catalog.member
            for identity in bundle['approved']['expected']['identities']:
                predicate = and_(table.c.corp_id == identity['corpId'], table.c.provider_user_id == identity['providerUserId'])
                if catalog.identities is not None:
                    predicate = and_(predicate, table.c.provider == identity['provider'])
                if connection.execute(select(table.c.id).where(predicate)).first():
                    return {**result, 'outcome': 'skipped_identity_reused'}
            if apply:
                connection.execute(insert(catalog.member).values(**snapshot['member']))
                for identity in snapshot['identities']:
                    connection.execute(insert(catalog.identities).values(**identity))
            result['outcome'] = 'restored' if apply else 'would_restore'
    except DBAPIError:
        result['outcome'] = 'skipped_database_conflict_or_lock_timeout'
    return result
