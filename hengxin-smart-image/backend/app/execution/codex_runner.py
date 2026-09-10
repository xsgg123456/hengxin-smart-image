"""Real CLI orchestration. All publication remains behind the Phase8 fence."""
import json
import subprocess
from pathlib import Path
from uuid import UUID, uuid4
from sqlalchemy import select
from app.core.config import get_settings
from app.db.session import session_factory
from app.models import utcnow
from app.modules.tasks.attempts import ExecutionAttempt, ExecutionSession, ExecutionUsage
from app.modules.tasks.claims import claim, end, locked_execution, mark_uncertain, valid
from app.modules.tasks.results import publish_results
from app.modules.revisions.service import safe_initial_retry
from app.modules.files.service import save_upload
from app.resource_models import UserRecord
from app.storage.minio_store import get_store
from app.worker.leases import heartbeat
from .events import parse_events
from .output_collector import collect_outputs, snapshot_outputs
from .provenance import snapshot_provenance, verify_provenance
from .materials import prepare_materials
from .process import execute
from .workspace import prepare_workspace, sandbox_command, prompt_for


def should_stop(factory, job_id, token):
    with factory() as session:
        task, round, job = locked_execution(session, job_id)
        return not job or not valid(task, round, job, token)


def register_process(factory, attempt_id, pid, boot, birth):
    with factory.begin() as session:
        row = session.get(ExecutionAttempt, attempt_id)
        row.process_id, row.boot_id, row.process_start = pid, boot, birth
        row.status = 'running'


def record_completion(factory, attempt_id, summary, receipt):
    with factory.begin() as session:
        attempt = session.get(ExecutionAttempt, attempt_id)
        attempt.status, attempt.finished_at = 'finished', utcnow()
        attempt.exit_code = receipt['exit_code']
        attempt.error = receipt['reason'] or summary.error
        identity = session.get(ExecutionSession, attempt.task_id)
        if summary.session_id:
            if identity.session_id and identity.session_id != summary.session_id:
                raise ValueError('CLI 未续接原会话')
            identity.session_id, identity.status = summary.session_id, 'ready'
        session.merge(ExecutionUsage(attempt_id=attempt.id, data=summary.usage))


def fail_stopped(factory, job_id, token, error):
    with factory.begin() as session:
        task, round, job = locked_execution(session, job_id)
        if job and job.claim_token == token:
            if job.status not in ('running', 'collecting', 'cancelling'):
                return  # reconciliation must explicitly resolve expired ownership
            cancelled = task.deleted_at or round.cancel_requested
            end(session, round, job, 'cancelled' if cancelled else 'failed',
                '任务已取消' if cancelled else error)


def run_generation(job_id, factory=None, store=None):
    settings = get_settings()
    if not settings.enable_codex_executor:
        return
    factory, store = factory or session_factory(), store or get_store()
    token = claim(factory, job_id)
    if not token:
        return
    attempt_id, completed, spawning = None, False, False
    try:
        with heartbeat(factory, job_id, token):
            version = subprocess.run([settings.codex_binary, '--version'], capture_output=True,
                                     text=True, timeout=10)
            if version.returncode or version.stdout.strip() != f'codex-cli {settings.codex_version}':
                raise ValueError('CLI 版本与已验证版本不一致')
            with factory.begin() as session:
                task, round, job = locked_execution(session, job_id)
                if not valid(task, round, job, token):
                    if job and job.claim_token == token and (task.deleted_at or round.cancel_requested):
                        end(session, round, job, 'cancelled', '启动前已取消')
                    return
                workspace = prepare_workspace(settings.codex_execution_root, task.id, round.id,
                                              settings.codex_auth_file)
                identity = session.get(ExecutionSession, task.id)
                previous = identity.session_id if identity else None
                if identity and not previous and not safe_initial_retry(session, task.id):
                    raise ValueError('原会话不可恢复，禁止创建替代会话')
                if not identity:
                    session.add(ExecutionSession(task_id=task.id))
                # Record intent before spawn: a crash here must never cause blind replay.
                attempt_id = uuid4()
                session.add(ExecutionAttempt(id=attempt_id, round_id=round.id, task_id=task.id,
                    operator_id=round.operator_id, claim_token=token, node=settings.worker_node_name,
                    workspace=str(workspace.control), cli_version=settings.codex_version))
                note, timeout = round.note, round.execution_config['timeoutSeconds']
                session.expunge(task)
                session.expunge(round)
            # Downloads and CLI execution never hold the task row lock.
            with factory() as session:
                manifest = prepare_materials(session, store, task, round, workspace)
            home = workspace.home / '.codex'
            if (home / 'sessions').is_symlink():
                raise ValueError('会话材料目录不允许符号链接')
            if previous and not any((home / 'sessions').rglob(f'*{previous}*')):
                raise ValueError('原会话材料缺失，禁止创建替代会话')
            baseline = snapshot_outputs(home, previous) if previous else {}
            (workspace.control / 'baseline.json').write_text(json.dumps(baseline))
            provenance = snapshot_provenance(home)
            (workspace.control / 'provenance.json').write_text(json.dumps(provenance))
            observed = [previous]
            def monitor():
                if observed[0] is None and (workspace.control / 'events.jsonl').exists():
                    initial = parse_events(workspace.control / 'events.jsonl')
                    if initial.session_id:
                        # Persist as soon as CLI announces it, not only after completion.
                        with factory.begin() as session:
                            identity = session.get(ExecutionSession, task.id)
                            identity.session_id = initial.session_id
                        observed[0] = initial.session_id
                return should_stop(factory, job_id, token)
            args = ['exec', '--sandbox', 'workspace-write']
            if previous:
                args += ['resume', '--skip-git-repo-check', '--json', previous, '-']
            else:
                args += ['--skip-git-repo-check', '--json', '-']
            command = sandbox_command(workspace, settings.codex_binary, args, settings.codex_bwrap_binary)
            spawning = True
            receipt = execute(command,
                prompt_for(manifest, note), workspace.control, timeout,
                monitor,
                lambda pid, boot, birth: register_process(factory, attempt_id, pid, boot, birth))
            completed = True
            summary = parse_events(workspace.control / 'events.jsonl', previous)
            record_completion(factory, attempt_id, summary, receipt)
            if receipt['reason'] or summary.error or not summary.turn_completed or receipt['exit_code']:
                fail_stopped(factory, job_id, token, 'CLI 执行未完成，请检查执行记录')
                return
            if should_stop(factory, job_id, token):
                fail_stopped(factory, job_id, token, '执行权已失效')
                return
            images = collect_outputs(home, summary.session_id, baseline, len(manifest['targets']),
                manifest_path=workspace.work / 'manifest.json' if (workspace.work / 'manifest.json').exists() else None,
                allow_partial=True)
            successful = [image for image in images if image is not None]
            if successful:
                verify_provenance(home, summary.session_id, provenance, successful)
            outputs = []
            for image in images:
                if image is None:
                    outputs.append(None)
                    continue
                with factory() as session:
                    user = session.get(UserRecord, round.operator_id)
                    outputs.append(save_upload(session, store, user, image).id)
            if not publish_results(factory, job_id, token, outputs):
                fail_stopped(factory, job_id, token, '执行权已失效，未发布结果')
    except Exception:
        if completed or not spawning:
            fail_stopped(factory, job_id, token, '执行结果校验或存储失败，未发布图片')
            if attempt_id and not spawning:
                with factory.begin() as session:
                    row = session.get(ExecutionAttempt, attempt_id)
                    row.status, row.finished_at = 'finished', utcnow()
                    row.error = '启动前校验失败，未调用模型'
        else:
            with factory.begin() as session:
                task, round, job = locked_execution(session, job_id)
                if job and job.claim_token == token and job.status not in ('succeeded', 'partial', 'cancelled', 'failed'):
                    mark_uncertain(round, job)
                    if attempt_id:
                        session.get(ExecutionAttempt, attempt_id).status = 'uncertain'
