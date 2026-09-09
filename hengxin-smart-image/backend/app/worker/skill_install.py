import hashlib
import importlib.util
import os
import shutil
import tempfile
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import session_factory
from app.models import Job, utcnow
from app.modules.skills.models import SkillVersionRecord
from app.modules.skills.package_validator import MAX_ZIP, validate_package
from app.storage.minio_store import get_store
from app.worker.leases import claim, finish_job, heartbeat, lease_active


def check_dependencies(package):
    for executable in package.requires.get('executables', []):
        if not shutil.which(executable):
            raise ValueError(f'缺少 Worker 可执行依赖：{executable}')
    for module in package.requires.get('pythonModules', []):
        # Do not import package-provided modules or execute their parents.
        if '.' in module:
            raise ValueError('Python 依赖请声明顶层模块名')
        if importlib.util.find_spec(module) is None:
            raise ValueError(f'缺少 Worker Python 依赖：{module}')


def prepare(record, token, store):
    stream = store.open(record)
    try:
        data = stream.read(MAX_ZIP + 1)
    finally:
        stream.close()
        if hasattr(stream, 'release_conn'):
            stream.release_conn()
    if hashlib.sha256(data).hexdigest() != record.checksum:
        raise ValueError('Skill 包校验和不匹配')
    package = validate_package(data, record.skill.mode, record.version)
    check_dependencies(package)
    root = Path(get_settings().skill_install_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f'.{record.id}-{token}-', dir=root))
    try:
        for name, data in package.files.items():
            target = temporary / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if not os.access(target, os.R_OK):
                raise ValueError('Skill 文件不可读')
        # Immutable per-attempt publication; an abandoned owner never overwrites another.
        destination = root / f'{record.id}-{token}'
        temporary.rename(destination)
        return destination
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def run_install(job_id, factory=None, store=None):
    factory, store = factory or session_factory(), store or get_store()
    token = claim(factory, job_id)
    if token is None:
        return
    path, error = None, None
    with heartbeat(factory, job_id, token):
        try:
            with factory() as session:
                job = session.get(Job, UUID(str(job_id)))
                record = session.get(SkillVersionRecord, UUID(job.value))
                if not record or record.current_job_id != job.id:
                    raise ValueError('安装请求已失效')
                path = prepare(record, token, store)
        except ValueError as problem:
            error = str(problem)
        except Exception:
            error = 'Skill 安装失败，请检查存储、磁盘及 Worker 环境后重试'
        with factory.begin() as session:
            job = session.scalar(select(Job).where(Job.id == UUID(str(job_id))).with_for_update())
            if job.claim_token != token or job.status != 'running' or not lease_active(job):
                if path:
                    shutil.rmtree(path)
                return
            record = session.get(SkillVersionRecord, UUID(job.value))
            finish_job(session, job, 'failed' if error else 'succeeded', error)
            if record and record.current_job_id == job.id:
                record.status = 'failed' if error else 'available'
                record.error, record.node = error, get_settings().worker_node_name
                if not error:
                    record.installed_path, record.installed_at = str(path), utcnow()
