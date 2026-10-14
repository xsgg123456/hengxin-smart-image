"""Real Codex sessions, isolated from domestic records and resumed without retries."""
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4
from sqlalchemy import select
from app.core.config import get_settings
from app.execution.workspace import prepare_workspace
from app.execution.output_collector import snapshot_outputs
from app.overseas.execution import claims
from app.storage.minio_store import get_store
from .models import Conversation, Turn, Picture
from .files import read
from . import transcript
from .delivery import collect_delivery


class StudioProtocol:
    def workspace(self, factory, job, token, settings):
        with factory() as session:
            turn = session.get(Turn, UUID(job.payload['turnId']))
            conversation = session.get(Conversation, turn.conversation_id)
            previous = conversation.session_id
            earlier = session.scalar(select(Turn.id).where(
                Turn.conversation_id == conversation.id, Turn.id != turn.id,
                Turn.dispatched.is_(True)).limit(1))
            if earlier and not previous:
                raise ValueError('Original session identity missing')
        workspace = prepare_workspace(Path(settings.codex_execution_root) / 'studio',
            conversation.id, turn.id, settings.codex_auth_file)
        home = workspace.home / '.codex'
        if (home / 'sessions').is_symlink():
            raise ValueError('Invalid sessions directory')
        if previous and not any((home / 'sessions').rglob(f'*{previous}*')):
            raise ValueError('Original session files missing')
        workspace.previous_session = previous
        workspace.baseline = snapshot_outputs(home, previous) if previous else {}
        return workspace

    def arguments(self, workspace):
        args = ['exec', '--model', 'gpt-6-astra', '-c', 'model_reasoning_effort="high"',
                '--sandbox', 'workspace-write']
        if workspace.previous_session:
            args += ['resume', '--skip-git-repo-check', '--json', workspace.previous_session]
        else:
            args += ['--skip-git-repo-check', '--json']
        return args + ['-']

    def prepare(self, job, workspace):
        directory = workspace.work / 'inputs'
        directory.mkdir(exist_ok=True)
        paths = []
        store = get_store()
        for index, data in enumerate(job.payload['inputs'], 1):
            source = SimpleNamespace(**data)
            suffix = Path(source.name).suffix.lower()
            path = directory / f'{index}{suffix}'
            with path.open('xb') as output:
                output.write(read(store, source))
            paths.append(dict(name=source.name, path='/work/inputs/' + path.name))
        skill = job.payload.get('skill')
        parts = []
        if not workspace.previous_session:
            parts.append('你是设计师的协作助手，按设计师的要求提供帮助。')
        parts.append(job.payload['text'])
        if paths:
            parts.append('附件文件：' + json.dumps(paths, ensure_ascii=False))
        if skill:
            parts.append('Skill文件：' + workspace.skill_path + '/SKILL.md')
        return '\n\n'.join(parts)

    def before_execute(self, factory, job, token):
        with factory.begin() as session:
            current = claims.locked_job(session, job.id)
            if not claims.valid(current, token):
                raise ValueError('Ownership lost before dispatch')
            turn = session.get(Turn, UUID(job.payload['turnId']))
            turn.dispatched = True

    def poll(self, factory, job, token, workspace):
        transcript.poll(factory, job, token, workspace)

    def final_poll(self, factory, job, token, workspace):
        transcript.poll(factory, job, token, workspace, final=True)

    def validate(self, job, workspace, summary):
        if not summary.final_text:
            raise ValueError('Missing final reply')
        try:
            images, warnings = collect_delivery(workspace, summary)
        except Exception:
            images, warnings = [], ['图片收取失败，请重试交付']
        outputs = []
        for target, image in images:
            try:
                identity = uuid4()
                from hashlib import sha256
                extension = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}[image.content_type]
                row = dict(id=str(identity), name=f'{identity}{extension}', bucket=get_settings().minio_bucket,
                    object_key=f'studio/pictures/{job.task_id}/{identity}', content_type=image.content_type,
                    size_bytes=len(image.data), checksum=sha256(image.data).hexdigest(),
                    width=image.width, height=image.height, source_path=target)
                from app.overseas.execution.objects import put
                put(get_store(), row, image.data)
                outputs.append(row)
            except Exception:
                warnings.append('一张正式交付图片保存失败')
        return dict(reply=summary.final_text, sessionId=summary.session_id, pictures=outputs,
                    deliveryError='；'.join(warnings) or None)

    def publish(self, session, job, result):
        turn = session.get(Turn, UUID(job.payload['turnId']))
        channel = session.get(Conversation, turn.conversation_id)
        if channel.session_id and channel.session_id != result['sessionId']:
            raise ValueError('Session mismatch')
        channel.session_id = result['sessionId']
        turn.reply = result['reply']
        turn.delivery_error = result.get('deliveryError')
        for data in result['pictures']:
            row = {**data, 'id': UUID(data['id'])}
            session.add(Picture(**row, task_id=job.task_id, turn_id=turn.id))


HANDLER = StudioProtocol()


def install():
    from app.overseas.execution.protocols import register
    register('studio', HANDLER)
