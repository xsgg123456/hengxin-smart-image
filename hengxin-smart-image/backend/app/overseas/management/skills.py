from fastapi import HTTPException
from sqlalchemy import select
from app.db.timestamps import utcnow
from app.overseas.execution.queue import lock_gate
from app.overseas.tasks.service import lock_actor
from .models import Audit, Skill, SkillVersion
from .schemas import validate_files


def describe(session, skill):
    versions = session.scalars(select(SkillVersion).where(SkillVersion.skill_id == skill.id)
                              .order_by(SkillVersion.version.desc()))
    return {'id': str(skill.id), 'name': skill.name, 'stage': skill.stage, 'enabled': skill.enabled,
        'version': skill.version, 'currentVersion': skill.current_version,
        'versions': [{'version': v.version, 'files': v.files, 'assetNames': sorted((v.assets or {}).keys()), 'createdAt': v.created_at} for v in versions]}


def list_skills(session):
    return {'items': [describe(session, s) for s in session.scalars(select(Skill).order_by(Skill.name))]}


def mutate(session, actor, body, identity=None, publish=False):
    actor = lock_actor(session, actor, 'skills.manage')
    lock_gate(session)
    before = {}
    if identity is None:
        if session.scalar(select(Skill.id).where(Skill.name == body.name)):
            raise HTTPException(409, 'Skill 名称已存在')
        skill = Skill(name=body.name, stage=body.stage)
        session.add(skill)
        session.flush()
        action = 'skill.create'
    else:
        skill = session.scalar(select(Skill).where(Skill.id == identity)
                               .execution_options(populate_existing=True))
        if skill is None:
            raise HTTPException(404, 'Skill 不存在')
        if skill.version != body.version:
            raise HTTPException(409, 'Skill 已被修改，请刷新后重试')
        before = {'version': skill.version, 'currentVersion': skill.current_version, 'enabled': skill.enabled}
        skill.version += 1
        skill.updated_at = utcnow()
        if publish:
            skill.current_version += 1
        else:
            skill.enabled = body.enabled
        action = 'skill.publish' if publish else 'skill.update'
    if identity is None or publish:
        previous_assets = {}
        if publish:
            previous_version = session.scalar(select(SkillVersion).where(
                SkillVersion.skill_id == skill.id, SkillVersion.version == skill.current_version - 1))
            previous_assets = previous_version.assets if previous_version else {}
        assets = getattr(body, 'assets', previous_assets) or {}
        try:
            if set(body.files) & set(assets):
                raise ValueError('duplicate resource')
            validate_files({**body.files, **{path: 'resource' for path in assets}})
        except ValueError:
            raise HTTPException(422, 'Skill文字与资源文件路径冲突或无效') from None
        session.add(SkillVersion(skill_id=skill.id, version=skill.current_version, files=body.files, assets=assets))
    session.add(Audit(actor_id=actor.id, action=action, target=str(skill.id), before=before,
        after={'version': skill.version, 'currentVersion': skill.current_version, 'enabled': skill.enabled}))
    session.flush()
    result = describe(session, skill)
    session.commit()
    return result
