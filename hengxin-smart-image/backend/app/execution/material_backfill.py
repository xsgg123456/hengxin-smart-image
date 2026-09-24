"""Run as the native worker identity: python -m app.execution.material_backfill.

Reads historical runtime files and stores only business prompt evidence in the DB.
No model call, task submission, status mutation, or execution replay is performed.
"""
import argparse
from uuid import UUID
from sqlalchemy import select
from app.core.config import get_settings
from app.db.session import session_factory
from app.modules.tasks.attempts import ExecutionAttempt
from app.modules.tasks.models import TaskRecord
from .material_capture import freeze_calls
from .material_history import read_history


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-id', type=UUID)
    parser.add_argument('--round-id', type=UUID)
    parser.add_argument('--write', action='store_true', help='写入业务材料；默认仅检查')
    args = parser.parse_args(argv)
    factory = session_factory()
    written = failed = 0
    with factory() as session:
        query = select(ExecutionAttempt).join(TaskRecord,
            ExecutionAttempt.task_id == TaskRecord.id).where(TaskRecord.deleted_at.is_(None),
            ExecutionAttempt.status == 'finished')
        if args.task_id:
            query = query.where(ExecutionAttempt.task_id == args.task_id)
        if args.round_id:
            query = query.where(ExecutionAttempt.round_id == args.round_id)
        attempts = session.scalars(query).all()
        for attempt in attempts:
            data = read_history(get_settings().codex_execution_root, attempt.task_id,
                                attempt.round_id, attempt.started_at, attempt.finished_at)
            print(f'{attempt.round_id}: 系统提示词 {len(data["systemPrompts"])}，生图调用 {len(data["toolCalls"])}')
            for notice in data['notices']:
                print(notice)
            if args.write:
                if freeze_calls(factory, attempt.id):
                    written += 1
                else:
                    failed += 1
    print(f'已检查 {len(attempts)} 轮历史材料；' + (f'写入成功 {written}，失败 {failed}。' if args.write else '只读检查，未写入。'))
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
