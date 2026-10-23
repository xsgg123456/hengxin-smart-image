"""Run inside the deployed API. Read-only unless explicitly writing the grant audit."""
import json
import sys
from uuid import UUID

from sqlalchemy import func, select, text
import app.overseas.main
from app.db.session import session_factory
from app.overseas.auth.models import Member, MemberRole
from app.overseas.auth.router import describe
from app.overseas.auth.dependencies import member_roles
from app.overseas.permissions import CAPABILITIES, capabilities, can_access_task, principal_for
from app.overseas.management.skills import can_toggle
from app.overseas.management.models import InstalledSkillAvailability
from app.overseas.members.models import MemberAudit
from app.overseas.members.service import lock_permissions
from app.overseas.tasks.models import Task
from app.overseas.execution.models import Job, ExecutionGate


def inspect(actor_id, target_id, verify=False, audit=False):
    assert actor_id != target_id
    with session_factory()() as s:
        if audit:
            assert verify
            lock_permissions(s)
        else:
            s.execute(text('SET TRANSACTION READ ONLY'))
        actor, target = s.get(Member, actor_id), s.get(Member, target_id)
        assert actor is not None and target is not None
        assert member_roles(s, actor) == ['super_admin']
        assert member_roles(s, target) == ['design_manager']
        before, after = describe(s, actor).model_dump(), describe(s, target).model_dump()
        result = {'actorRole': before['roles'], 'targetRole': after['roles'],
                  'actorCapabilities': before['capabilities'], 'targetCapabilities': after['capabilities'],
                  'equal': before['capabilities'] == after['capabilities'],
                  'actorToggle': can_toggle(actor), 'targetToggle': can_toggle(target)}
        members = []
        for m in s.scalars(select(Member).order_by(Member.id)):
            roles = list(s.scalars(select(MemberRole.role).where(MemberRole.user_id == m.id)))
            members.append([str(m.id), m.status, m.directory_state, roles, m.version])
        result['members'] = members
        result['skills'] = [[m.id, m.enabled, m.version] for m in s.scalars(
            select(InstalledSkillAvailability).order_by(InstalledSkillAvailability.id))]
        tasks = s.scalars(select(Task)).all()
        result['taskCount'] = len(tasks)
        result['migration'] = s.scalar(text('SELECT version_num FROM overseas_alembic_version'))
        result['paused'] = s.get(ExecutionGate, 1).paused
        result['activeJobs'] = s.scalar(select(func.count()).select_from(Job).where(
            Job.status.in_(('queued', 'running', 'collecting', 'cancelling', 'uncertain'))))
        if verify:
            assert result['equal'] and set(after['capabilities']) == set(CAPABILITIES)
            assert result['actorToggle'] and result['targetToggle']
            a, t = principal_for(s, actor), principal_for(s, target)
            for task in tasks:
                for permission in CAPABILITIES:
                    assert can_access_task(a, task.created_by, task.designer_id, permission)
                    assert can_access_task(t, task.created_by, task.designer_id, permission)
            for member in s.scalars(select(Member).where(Member.id.notin_([actor_id, target_id]))):
                if member.status == 'active' and member.directory_state == 'enrolled':
                    assert describe(s, member).capabilities == capabilities(member_roles(s, member))
            result['allTaskActionsVerified'] = len(tasks) * len(CAPABILITIES)
        if audit:
            action = 'full_access_grant'
            exists = s.scalar(select(MemberAudit).where(MemberAudit.member_id == target_id,
                              MemberAudit.actor_id == actor_id, MemberAudit.action == action))
            assert exists is None, 'Existing grant audit requires inspection'
            s.add(MemberAudit(member_id=target_id, actor_id=actor_id, action=action,
                  before={'roles': after['roles'], 'capabilities': capabilities(after['roles']), 'fullAccess': False},
                  after={'roles': after['roles'], 'capabilities': after['capabilities'], 'fullAccess': True,
                         'skillToggle': True, 'source': 'explicit_account_configuration'}))
            s.commit()
        return result


if __name__ == '__main__':
    print(json.dumps(inspect(UUID(sys.argv[1]), UUID(sys.argv[2]),
                             sys.argv[3] == '1', sys.argv[4] == '1'), ensure_ascii=False))
