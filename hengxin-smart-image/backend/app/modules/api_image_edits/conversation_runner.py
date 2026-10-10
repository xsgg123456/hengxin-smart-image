"""One invocation per persisted turn. No automatic model retry or replacement session."""
import subprocess
from pathlib import Path
from uuid import UUID
from sqlalchemy import or_, select
from app.core.config import get_settings
from app.db.session import session_factory
from app.execution.events import parse_events
from app.execution.final_delivery import collect_final_outputs
from app.execution.delivery_markdown import delivery_links
from app.execution.output_collector import snapshot_outputs
from app.execution.process import execute
from app.execution.workspace import prepare_workspace, sandbox_command
from app.modules.files.validation import DECODE_SLOTS, MAX_UPLOAD_BYTES
from app.modules.files.variants import register
from app.capacity.admission import covered, published
from app.storage.minio_store import get_store
from app.worker.leases import heartbeat
from .conversation_models import ConversationTurn
from .conversation_runtime import Monitor, claim, finish, locked, valid
from .dimensions import normalize_result
from .files import find_file, new_record, read_bytes
from .execution_policy import CLI_MODEL, CLI_REASONING_EFFORT, CLI_USES_SKILLS


class ConversationFailure(Exception):
    """Only platform-authored diagnostics may be shown to the user."""


def prepare_inputs(factory, store, turn, workspace):
    directory = workspace.work / 'inputs'
    directory.mkdir(exist_ok=True)
    paths = []
    for index, value in enumerate(turn.snapshot['fileIds'], 1):
        with factory() as session:
            record = find_file(session, UUID(value))
            session.expunge(record)
        extension = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}[record.content_type]
        path = directory / (str(index) + extension)
        with path.open('xb') as output:
            output.write(read_bytes(store, record))
        paths.append('/work/inputs/' + path.name)
    # Fixed v2 prompt remains byte-for-byte at the front; only binding and delivery are appended.
    return turn.prompt + '\n\n本轮输入按上述图1/图2/图3/可选图4顺序：\n' + '\n'.join(paths) + (
        '\n本轮仅修改图1，图2为最初原图，图3为素材，图4（若有）为标注。'
        '\n如果需要澄清可直接文字回复；交付图片时将唯一最终图片保存到本轮 /work，'
        '最终回复用 Markdown 图片链接明确交付该文件。不要交付输入图片或历史轮次文件。')


def completion_allowed(session, task, conversation, turn, job, token):
    """Called only after execute has returned or before it was ever dispatched."""
    if valid(task, turn, job, token):
        return True
    if job.claim_token == token:
        if turn.status == 'running':
            finish(session, conversation, turn, job,
                   'cancelled' if turn.cancel_requested or task.deleted_at else (
                       'uncertain' if turn.snapshot.get('executionDispatched') else 'failed'))
        published(session, turn.id)
    return False


def complete(factory, store, job_id, token, image=None, error=None, status='waiting_user'):
    record = None
    if image is not None:
        with factory.begin() as session:
            task, item, channel, turn, job = locked(session, job_id)
            if not completion_allowed(session, task, channel, turn, job, token):
                return
            source = find_file(session, item.source_id)
            width, height, owner = source.width, source.height, turn.operator_id
        with DECODE_SLOTS:
            image = normalize_result(image, width, height, MAX_UPLOAD_BYTES)
        record = new_record(owner, image)
        with factory.begin() as session:
            session.add(record)
        store.put(record, image.data)
    with factory.begin() as session:
        task, _, conversation, turn, job = locked(session, job_id)
        if not completion_allowed(session, task, conversation, turn, job, token):
            return
        for value in turn.snapshot['fileIds']:
            find_file(session, UUID(value), lock=True)
        if record:
            record = session.merge(record)
            record.status = 'ready'
            register(session, record, 'api-image-edits')
            turn.candidate_id = record.id
            status = 'candidate'
        finish(session, conversation, turn, job, status, error)
        published(session, turn.id)


def run_turn(job_id, factory=None, store=None):
    settings = get_settings()
    factory = factory or session_factory()
    from .conversation_stop import stop_uncertain
    if stop_uncertain(factory, job_id):
        return
    if not settings.enable_codex_executor:
        return
    store = store or get_store()
    token = claim(factory, job_id)
    if not token:
        return
    spawned = completed = False
    try:
        with heartbeat(factory, job_id, token):
            version = subprocess.run([settings.codex_binary, '--version'], capture_output=True,
                                     text=True, timeout=10)
            if version.returncode or version.stdout.strip() != f'codex-cli {settings.codex_version}':
                raise ValueError('CLI version mismatch')
            with factory.begin() as session:
                task, _, conversation, turn, job = locked(session, job_id)
                if not valid(task, turn, job, token):
                    finish(session, conversation, turn, job, 'cancelled')
                    published(session, turn.id)
                    return
                previous = conversation.session_id
                earlier = session.scalar(select(ConversationTurn.id).where(
                    ConversationTurn.conversation_id == conversation.id,
                    ConversationTurn.id != turn.id, or_(
                        ConversationTurn.snapshot['executionDispatched'].as_boolean().is_(True),
                        ConversationTurn.process_identity.is_not(None))).limit(1))
                if earlier and not previous:
                    raise ConversationFailure('原会话编号缺失，无法继续；禁止创建替代会话')
                conversation_id, turn_id = conversation.id, turn.id
                session.expunge(turn)
            workspace = prepare_workspace(Path(settings.codex_execution_root) / 'api-edits',
                conversation_id, turn_id, settings.codex_auth_file)
            workspace.use_skill = CLI_USES_SKILLS
            home = workspace.home / '.codex'
            if (home / 'sessions').is_symlink():
                raise ValueError('Invalid session directory')
            if previous and not any((home / 'sessions').rglob(f'*{previous}*')):
                raise ConversationFailure('原会话文件缺失，无法继续；请管理员恢复会话材料')
            prompt = prepare_inputs(factory, store, turn, workspace)
            with factory.begin() as session:
                _, _, _, current, _ = locked(session, job_id)
                current.snapshot = {**current.snapshot, 'executionPrompt': prompt}
            baseline = snapshot_outputs(home, previous) if previous else {}
            monitor = Monitor(factory, job_id, token, workspace.control / 'events.jsonl', previous)
            def started(pid, boot, birth):
                with factory.begin() as session:
                    task, _, _, current, _ = locked(session, job_id)
                    current.process_identity = {'pid': pid, 'boot': boot, 'birth': birth,
                                                'node': settings.worker_node_name}
                    from app.modules.management.api_stats.facts import record_turn
                    record_turn(session, task, current, spawned=True)
            args = ['exec', '--sandbox', 'workspace-write']
            args += (['resume', '--skip-git-repo-check', '--json', previous] if previous
                     else ['--skip-git-repo-check', '--json'])
            args += ['--model', CLI_MODEL, '-c', f'model_reasoning_effort="{CLI_REASONING_EFFORT}"', '-']
            command = sandbox_command(workspace, settings.codex_binary, args, settings.codex_bwrap_binary)
            with factory() as session:
                if not covered(session, turn_id, 'cli', turn_id, 20 * 1024 * 1024):
                    raise RuntimeError('Capacity missing')
            if monitor():
                complete(factory, store, job_id, token, status='cancelled')
                return
            # A claimed turn can fail preflight without ever starting a CLI session.
            # Persist the dispatch fence BEFORE execute: a crash around spawn is ambiguous.
            with factory.begin() as session:
                task, _, channel, current, job = locked(session, job_id)
                if not valid(task, current, job, token):
                    if job.claim_token == token and current.status == 'running':
                        finish(session, channel, current, job,
                               'cancelled' if current.cancel_requested or task.deleted_at else 'failed',
                               '启动前任务状态已变化，本轮未调用 CLI')
                        published(session, current.id)
                    return
                current.snapshot = {**current.snapshot, 'executionDispatched': True}
            spawned = True
            receipt = execute(command, prompt, workspace.control, turn.snapshot['timeoutSeconds'], monitor, started)
            completed = True
            monitor.last_poll = 0
            if monitor():
                complete(factory, store, job_id, token, status='cancelled')
                return
            summary = parse_events(workspace.control / 'events.jsonl', previous)
            if receipt.get('reason') or receipt.get('exit_code') != 0:
                complete(factory, store, job_id, token, status='failed', error='执行停止或超时，请检查本轮结果')
                return
            if summary.error or not summary.session_id or not summary.turn_completed or not summary.final_text:
                complete(factory, store, job_id, token, status='failed', error='本轮执行或最终回复不完整')
                return
            links = delivery_links(summary.final_text)
            if not links:
                complete(factory, store, job_id, token)
                return
            images = collect_final_outputs(workspace.work, home, workspace.control / 'events.jsonl',
                                           summary.session_id, baseline, 1)
            complete(factory, store, job_id, token, image=images[0])
    except Exception as error:
        with factory.begin() as session:
            task, _, conversation, turn, job = locked(session, job_id)
            if job and job.claim_token == token:
                if turn.status == 'running':
                    status = 'uncertain' if spawned and not completed else (
                        'cancelled' if turn.cancel_requested or task.deleted_at else 'failed')
                    finish(session, conversation, turn, job, status,
                           '执行状态待核实，禁止自动重试' if status == 'uncertain' else (
                               str(error) if isinstance(error, ConversationFailure)
                               else '会话或图片校验失败，请检查执行环境'))
                if not spawned or completed:
                    published(session, turn.id)
