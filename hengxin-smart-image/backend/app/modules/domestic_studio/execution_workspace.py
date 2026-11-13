"""Prepare a single private conversation using the existing Studio filesystem."""
import json
import re
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select

from app.execution.output_collector import snapshot_outputs
from app.execution.workspace import prepare_workspace
from app.models import Job
from app.overseas.studio import context_workspace
from app.overseas.execution.materials import write_input
from app.overseas.studio.image_edits import prompt_edits
from app.overseas.studio.native_images import snapshot as native_snapshot
from .conversation_models import Conversation
from .models import SkillExecutionReference
from .skill_material import prepare as prepare_skill
from .skill_references import JOB_KIND, explicit_no_skill
from .turn_models import Picture, Turn


def prepare(factory, job_id, settings, catalog, store):
    with factory() as session:
        job = session.get(Job, job_id)
        turn = session.scalar(select(Turn).where(Turn.job_id == job_id))
        channel = session.get(Conversation, turn.conversation_id) if turn else None
        pin = session.get(SkillExecutionReference, job_id)
        if not job or job.kind != JOB_KIND or not turn or not channel or turn.actor_id != channel.owner_id:
            raise ValueError('Domestic Studio ownership or Skill reference missing')
        payload = turn.snapshot
        skill = payload.get('skill')
        no_skill = pin is None and explicit_no_skill(job, turn, channel)
        if not no_skill and (not pin or not isinstance(skill, dict)
                or payload.get('skillSelection') not in (None, 'explicit') or pin.name != skill.get('name')
                or pin.release != skill.get('installedRelease') or pin.checksum != skill.get('checksum')
                or payload.get('turnId') != str(turn.id) or payload.get('conversationId') != str(channel.id)):
            raise ValueError('Domestic Studio snapshot identity mismatch')
        prior = list(session.scalars(select(Turn).where(Turn.conversation_id == channel.id,
            Turn.id != turn.id, Turn.dispatched.is_(True)).order_by(Turn.created_at, Turn.id)))
        previous = channel.session_id
        if previous is not None and not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', previous):
            raise ValueError('Invalid original session identity')
        if prior and not previous:
            raise ValueError('Original session identity missing')
        history = [dict(turn_id=str(row.id), inputs=row.snapshot['inputs']) for row in prior]
        delivered = {(row.source_path.removeprefix('sandbox:'), row.checksum)
            for row in session.scalars(select(Picture).join(Turn, Picture.turn_id == Turn.id)
                .where(Turn.conversation_id == channel.id)) if row.source_path}
        conversation_id, turn_id = channel.id, turn.id
    workspace = prepare_workspace(Path(settings.codex_execution_root) / 'domestic-studio',
        conversation_id, turn_id, settings.codex_auth_file, copy_auth=False)
    home = workspace.home / '.codex'
    if (home / 'sessions').is_symlink():
        raise ValueError('Invalid session directory')
    if previous and not any((home / 'sessions').rglob(f'*{previous}*')):
        raise ValueError('Original session files missing')
    workspace.previous_session = previous
    workspace.baseline = snapshot_outputs(home, previous) if previous else {}
    workspace.input_paths = context_workspace.prepare(workspace, history, payload['inputs'],
        lambda data: store.open(SimpleNamespace(**data)))
    workspace.native_cursor = native_snapshot(workspace.home, previous)
    workspace.delivered_images = delivered
    write_input(payload, workspace)
    workspace.use_skill = not no_skill
    if workspace.use_skill:
        prepare_skill(skill, workspace, catalog)
    return workspace, payload


def prompt(workspace, payload):
    parts = ['$' + workspace.skill_name] if workspace.use_skill else []
    if not workspace.use_skill and workspace.previous_session:
        parts.append('本轮未选择 Skill。沿用当前会话与图片上下文，仅处理本轮请求，不主动重启历史 Skill 流程。')
    if payload['text']:
        parts.append(payload['text'])
    edits = prompt_edits(payload, workspace.input_paths)
    if edits:
        parts.append(edits)
    if workspace.input_paths:
        parts.append('附件文件：' + json.dumps(workspace.input_paths, ensure_ascii=False))
    return '\n\n'.join(parts)
