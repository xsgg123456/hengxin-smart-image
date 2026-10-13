"""Approved-list cleanup, with durable recovery evidence and locked rechecks."""
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.exc import DBAPIError

from member_audit import get_member, inspect_member, now
from member_catalog import Catalog, source_fingerprint, transaction
from member_codec import SafetyError, digest, encode, safe_rows, write_json


def validate_approval(approval, business):
    if not isinstance(approval, dict) or approval.get('formatVersion') != 1 or approval.get('business') != business:
        raise SafetyError('invalid_approval_business_or_format')
    if not all(isinstance(approval.get(key), str) and approval[key].strip()
               for key in ('reviewedBy', 'reason', 'sourceFingerprint')):
        raise SafetyError('reviewer_reason_and_source_required')
    members = approval.get('members')
    if not isinstance(members, list) or not members:
        raise SafetyError('explicit_member_list_required')
    ids = []
    for item in members:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id']:
            raise SafetyError('invalid_approved_member')
        expected = item.get('expected')
        if not isinstance(expected, dict) or set(expected) != {'status', 'directoryState', 'version', 'identities', 'snapshotSha256'}:
            raise SafetyError('complete_expected_snapshot_required')
        if expected['status'] != 'pending' or expected['directoryState'] != 'legacy_unconfirmed':
            raise SafetyError('only_legacy_empty_members_allowed')
        if not isinstance(expected['identities'], list) or not expected['identities']:
            raise SafetyError('expected_identity_required')
        if not isinstance(expected['snapshotSha256'], str) or len(expected['snapshotSha256']) != 64:
            raise SafetyError('expected_snapshot_hash_required')
        ids.append(item['id'])
    if len(ids) != len(set(ids)):
        raise SafetyError('duplicate_approved_member')


def locked_catalog(connection, business, schema, apply):
    catalog = Catalog(connection, business, schema)
    if apply:
        catalog.lock()
        rechecked = Catalog(connection, business, schema)
        if rechecked.related_keys() != catalog.related_keys() or rechecked.inventory() != catalog.inventory():
            raise SafetyError('reference_schema_changed_retry_audit')
        catalog = rechecked
    return catalog


def prepare_recovery(folder, business, catalog, approval, item, snapshot, report):
    safe_rows([snapshot['member'], *snapshot['identities']])
    bundle = {'formatVersion': 1, 'operation': 'restore_legacy_member', 'phase': 'prepared',
              'business': business, 'schema': catalog.schema, 'createdAt': now(),
              'sourceFingerprint': approval['sourceFingerprint'], 'reviewedBy': approval['reviewedBy'],
              'reason': approval['reason'], 'approved': item, 'snapshot': encode(snapshot),
              'referenceCheck': report['references']}
    bundle['sha256'] = digest(bundle)
    path = Path(folder) / (uuid4().hex + '.prepared.json')
    write_json(path, bundle, exclusive=True)
    return path


def reconcile_one(engine, business, schema, approval, item, apply, recovery_dir):
    result = {'id': item['id']}
    with transaction(engine, writable=apply) as connection:
        catalog = locked_catalog(connection, business, schema, apply)
        if source_fingerprint(engine, business, catalog.schema) != approval['sourceFingerprint']:
            raise SafetyError('source_fingerprint_mismatch')
        row = get_member(catalog, item['id'])
        if row is None:
            return {**result, 'outcome': 'already_absent'}
        report, snapshot = inspect_member(catalog, row)
        if item['expected'] != report['expected']:
            return {**result, 'outcome': 'skipped', 'reasons': ['expected_snapshot_changed']}
        if not report['cleanupEligible']:
            return {**result, 'outcome': 'skipped', 'reasons': report['skipReasons'], 'references': report['references']}
        if not apply:
            return {**result, 'outcome': 'would_delete', 'references': report['references'],
                    'recoveryPreview': encode(snapshot)}
        path = prepare_recovery(recovery_dir, business, catalog, approval, item, snapshot, report)
        if catalog.identities is not None:
            connection.execute(delete(catalog.identities).where(catalog.identities.c.user_id == row['id']))
        deleted = connection.execute(delete(catalog.member).where(catalog.member.c.id == row['id']))
        if deleted.rowcount != 1:
            raise SafetyError('member_changed_during_cleanup')
        result.update(outcome='deleted', recoveryFile=str(path), deletedAt=now())
    # Deletion is committed. A prepared bundle remains sufficient if receipt I/O fails.
    try:
        write_json(path.with_suffix('.receipt.json'), result, exclusive=True)
    except OSError:
        result['receiptWarning'] = 'committed_receipt_write_failed_use_prepared_bundle'
    return result


def reconcile(engine, business, approval, *, schema=None, apply=False, recovery_dir=None):
    validate_approval(approval, business)
    if apply and recovery_dir is None:
        raise SafetyError('recovery_directory_required')
    results = []
    for item in approval['members']:
        try:
            results.append(reconcile_one(engine, business, schema, approval, item, apply, recovery_dir))
        except DBAPIError:
            results.append({'id': item['id'], 'outcome': 'skipped', 'reasons': ['database_conflict_or_lock_timeout']})
    return {'formatVersion': 1, 'business': business, 'operation': 'reconcile', 'apply': apply,
            'createdAt': now(), 'reviewedBy': approval['reviewedBy'], 'reason': approval['reason'], 'results': results}
