"""Retire domestic roles from a reviewed full identity snapshot; dry-run by default.

Run with DATABASE_URL set explicitly and --backend-root pointing to the deployed
backend. First export --snapshot-output FILE --actor-id UUID, review every member
and set the one explicitly authorized target's toRole to super_admin. Then run
--manifest FILE (dry-run), followed by --manifest FILE --apply. No schema changes.
"""
import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from uuid import UUID


ACTION = 'retire_design_manager'


def export_snapshot(session, *, lock=False):
    from sqlalchemy import select
    from app.modules.auth.models import RoleAssignmentRecord, UserIdentityRecord
    from app.resource_models import UserRecord

    def rows(model):
        statement = select(model).order_by(model.id).execution_options(populate_existing=True)
        return session.scalars(statement.with_for_update() if lock else statement).all()
    users, identities, assignments = (rows(model) for model in
                                     (UserRecord, UserIdentityRecord, RoleAssignmentRecord))
    return [dict(id=str(user.id), name=user.name, role=user.role, status=user.status,
                 directoryState=user.directory_state, identitySource=user.identity_source,
                 identities=[dict(id=str(i.id), provider=i.provider, corpId=i.corp_id,
                     providerUserId=i.provider_user_id, unionId=i.union_id, department=i.department)
                     for i in identities if i.user_id == user.id],
                 assignment=next((dict(id=str(a.id), role=a.role,
                     assignedBy=str(a.assigned_by) if a.assigned_by else None)
                     for a in assignments if a.user_id == user.id), None)) for user in users]


def _validated(manifest):
    if set(manifest) != {'actorId', 'expectedMembers', 'changes'}:
        raise ValueError('Manifest requires actorId, expectedMembers and changes only')
    UUID(manifest['actorId'])
    expected, changes = manifest['expectedMembers'], manifest['changes']
    if not expected or not changes:
        raise ValueError('Complete member snapshot and explicit changes are required')
    members = {row['id']: row for row in expected}
    targets = {row['id']: row for row in changes}
    if len(members) != len(expected) or len(targets) != len(changes):
        raise ValueError('Duplicate member or target ID')
    if set(targets) != {row['id'] for row in expected if row['role'] == 'design_manager'}:
        raise ValueError('Changes must include exactly all historical design managers')
    if sum(row['toRole'] == 'super_admin' for row in changes) > 1:
        raise ValueError('At most one explicit super administrator exception is allowed')
    for identifier, change in targets.items():
        UUID(identifier)
        row = members[identifier]
        if (set(change) != {'id', 'name', 'fromRole', 'toRole'}
                or change['name'] != row['name'] or change['fromRole'] != 'design_manager'
                or change['toRole'] not in ('designer', 'super_admin')
                or row['directoryState'] != 'enrolled' or row['identitySource'] != 'dingtalk'
                or len(row['identities']) != 1 or row['identities'][0]['provider'] != 'dingtalk'
                or not row['identities'][0]['corpId'] or not row['identities'][0]['providerUserId']
                or sum(item['name'] == row['name'] for item in expected) != 1
                or (row['assignment'] and row['assignment']['role'] != row['role'])):
            raise ValueError('Target name, identity, original role or assignment does not match')
        if change['toRole'] == 'super_admin' and row['status'] != 'active':
            raise ValueError('Super administrator exception must already be active')
    actor = members.get(manifest['actorId'])
    if not actor or (actor['role'], actor['status'], actor['directoryState']) != (
            'super_admin', 'active', 'enrolled'):
        raise ValueError('Actor must be an existing active domestic super administrator')
    return members, targets


def apply_retirement(session, manifest, *, apply=False):
    """Caller owns the transaction. Audit and changes must commit or roll back together."""
    from sqlalchemy import select
    from app.modules.auth.application_models import MemberAudit
    from app.modules.auth.member_policy import lock_permissions, require_admin
    from app.modules.auth.models import RoleAssignmentRecord
    from app.resource_models import UserRecord

    expected, targets = _validated(manifest)
    digest = sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False,
                               separators=(',', ':')).encode()).hexdigest()
    actor_id = UUID(manifest['actorId'])
    lock_permissions(session)
    require_admin(session, actor_id)
    current = {row['id']: row for row in export_snapshot(session, lock=True)}
    audits = session.scalars(select(MemberAudit).where(MemberAudit.action == ACTION)).all()
    previous = [a for a in audits if a.after.get('manifestSha256') == digest]
    if previous:
        if (len(previous) != len(targets) or {str(a.member_id) for a in previous} != set(targets)
                or any(a.actor_id != actor_id or a.before != expected[str(a.member_id)]
                       for a in previous)):
            raise ValueError('Incomplete or conflicting retirement audit')
        completed = deepcopy(expected)
        for audit in previous:
            completed[str(audit.member_id)] = {k: v for k, v in audit.after.items()
                                               if k != 'manifestSha256'}
        if current != completed:
            raise ValueError('Member snapshot changed after the audited retirement')
        return dict(state='already_applied', manifestSha256=digest,
                    changed=[], roles=dict(Counter(row['role'] for row in current.values())))
    if current != expected:
        raise ValueError('Current full member/identity/assignment snapshot differs from manifest')
    projected = deepcopy(expected)
    for identifier, change in targets.items():
        projected[identifier]['role'] = change['toRole']
    receipt = dict(state='applied' if apply else 'dry_run', manifestSha256=digest,
                   changed=list(targets.values()),
                   rolesBefore=dict(Counter(row['role'] for row in expected.values())),
                   rolesAfter=dict(Counter(row['role'] for row in projected.values())))
    if not apply:
        return receipt
    for identifier, change in targets.items():
        member = session.get(UserRecord, UUID(identifier))
        member.role = change['toRole']
        assignment = session.scalar(select(RoleAssignmentRecord).where(
            RoleAssignmentRecord.user_id == member.id))
        if assignment is None:
            assignment = RoleAssignmentRecord(user_id=member.id)
            session.add(assignment)
        assignment.role, assignment.assigned_by = member.role, actor_id
    session.flush()
    after = {row['id']: row for row in export_snapshot(session, lock=True)}
    for identifier in targets:
        session.add(MemberAudit(member_id=UUID(identifier), actor_id=actor_id, action=ACTION,
            before=expected[identifier], after={**after[identifier], 'manifestSha256': digest}))
    session.flush()
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-root', type=Path, required=True)
    parser.add_argument('--database-url-env', default='DATABASE_URL')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--snapshot-output', type=Path)
    source.add_argument('--manifest', type=Path)
    parser.add_argument('--actor-id')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.snapshot_output and (not args.actor_id or args.apply):
        parser.error('Snapshot export requires --actor-id and cannot use --apply')
    url = os.environ.get(args.database_url_env)
    if not url:
        parser.error('Explicit database URL environment variable is required')
    sys.path.insert(0, str(args.backend_root.resolve(strict=True)))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.modules.auth.member_policy import require_admin

    engine = create_engine(url)
    try:
        if engine.dialect.name != 'postgresql':
            raise ValueError('CLI requires PostgreSQL for transactional permission locking')
        connection = engine.execution_options(isolation_level='REPEATABLE READ',
            postgresql_readonly=True) if args.snapshot_output else engine
        with Session(connection) as session, session.begin():
            if args.snapshot_output:
                require_admin(session, UUID(args.actor_id))
                members = export_snapshot(session)
                manifest = dict(actorId=args.actor_id, expectedMembers=members,
                    changes=[dict(id=row['id'], name=row['name'], fromRole='design_manager',
                                  toRole='designer') for row in members if row['role'] == 'design_manager'])
                with args.snapshot_output.open('x', encoding='utf-8') as output:
                    json.dump(manifest, output, ensure_ascii=False, indent=2)
                print(json.dumps({'state': 'snapshot_exported', 'members': len(members)}))
            else:
                manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
                receipt = apply_retirement(session, manifest, apply=args.apply)
        # Report success only after the database commit completes.
        if args.manifest:
            print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
