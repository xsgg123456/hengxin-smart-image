from fastapi import HTTPException
from sqlalchemy import delete, select
from app.overseas.execution.queue import lock_gate
from app.overseas.tasks.creative_tools import TOOL_KEYS
from app.overseas.tasks.service import lock_actor
from .installed_catalog import identity
from .models import Audit, InstalledSkillAvailability, ToolSkillBinding
from .skills import list_skills


def catalog(session, actor):
    bindings = {key: [] for key in TOOL_KEYS}
    for row in session.scalars(select(ToolSkillBinding).order_by(ToolSkillBinding.skill_name)):
        bindings[row.tool_key].append(identity(row.skill_name))
    return {'items': list_skills(session, actor)['items'], 'bindings': bindings}


def replace(session, actor, tool_key, body):
    actor = lock_actor(session, actor, 'skills.manage')
    if tool_key not in TOOL_KEYS:
        raise HTTPException(404, '创作工具不存在')
    # Order binding edits with Skill installation, removal, switches and job admission.
    lock_gate(session)
    current = catalog(session, actor)
    before = set(current['bindings'][tool_key])
    desired = {str(value) for value in body.skillIds}
    installed = {item['id']: item['name'] for item in current['items']}
    if desired - installed.keys():
        raise HTTPException(422, '所选 Skill 已移出安装目录，请刷新后重选')
    if before == desired:
        session.commit()
        return current
    if before != {str(value) for value in body.expectedSkillIds}:
        raise HTTPException(409, '此工作台绑定已变化，请刷新后重新选择')
    session.execute(delete(ToolSkillBinding).where(ToolSkillBinding.tool_key == tool_key))
    for skill_id in sorted(desired):
        name = installed[skill_id]
        if session.get(InstalledSkillAvailability, name) is None:
            session.add(InstalledSkillAvailability(id=name))
            session.flush()
        session.add(ToolSkillBinding(tool_key=tool_key, skill_name=name))
    session.add(Audit(actor_id=actor.id, action='skill.tool_bindings', target=tool_key,
                      before={'skillIds': sorted(before)}, after={'skillIds': sorted(desired)}))
    session.commit()
    current['bindings'][tool_key] = sorted(desired, key=installed.__getitem__)
    return current
