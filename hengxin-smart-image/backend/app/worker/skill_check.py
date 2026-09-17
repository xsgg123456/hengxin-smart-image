"""Lease-fenced deployment inspection; successful checks never enable a version."""
from uuid import UUID

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import session_factory
from app.execution.local_skill_probe import probe_tree
from app.models import Job, utcnow
from app.modules.skills.local_tree import inspect_tree
from app.modules.skills.models import SkillVersionRecord
from app.worker.leases import claim, finish_job, heartbeat, lease_active


def validate_local(record, expected=None):
    checksum = record.checksum if expected is None else expected
    if expected is not None and (not expected or record.checksum != expected):
        raise ValueError('Skill 与任务冻结版本不一致')
    arguments = (get_settings().local_skill_root, record.skill.name,
                 record.skill.mode, record.version)
    tree = inspect_tree(*arguments, checksum)
    probe_tree(tree)
    # Publication might have been replaced while the probe was running.
    inspect_tree(*arguments, tree.checksum)
    return tree


def run_check(job_id, factory=None):
    factory = factory or session_factory()
    token = claim(factory, job_id)
    if token is None:
        return
    tree, error = None, None
    with heartbeat(factory, job_id, token):
        try:
            with factory() as session:
                job = session.get(Job, UUID(str(job_id)))
                record = session.get(SkillVersionRecord, UUID(job.value))
                if not record or record.source_type != 'local' or record.current_job_id != job.id:
                    raise ValueError('检查请求已失效')
                tree = validate_local(record)
        except ValueError as problem:
            error = str(problem)
        except Exception:
            error = 'Skill 检查失败，请检查发布目录及 Worker 隔离环境后重试'
        with factory.begin() as session:
            job = session.scalar(select(Job).where(Job.id == UUID(str(job_id))).with_for_update())
            if job.claim_token != token or job.status != 'running' or not lease_active(job):
                return
            record = session.scalar(select(SkillVersionRecord).where(
                SkillVersionRecord.id == UUID(job.value)).with_for_update(of=SkillVersionRecord))
            if record and record.current_job_id == job.id:
                if tree and record.checksum and record.checksum != tree.checksum:
                    error = 'Skill 内容已变化，请恢复原内容或登记新版本'
                record.status, record.error = ('invalid' if error else 'verified'), error
                record.node = get_settings().worker_node_name
                if not error:
                    record.checksum = record.checksum or tree.checksum
                    record.installed_path, record.installed_at = str(tree.path), utcnow()
            finish_job(session, job, 'failed' if error else 'succeeded', error)
