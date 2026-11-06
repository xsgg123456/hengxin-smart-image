"""One-shot authorized old Skill duplicates only; no model, API writes or service restart."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
from uuid import UUID

spec = importlib.util.spec_from_file_location('history_files',Path(__file__).with_name('skill-history-files.py'))
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)


def runtime():
    from app.core.config import get_settings
    from app.overseas.db import require_overseas_context, session_factory
    require_overseas_context()
    root = f.safe(Path(get_settings().codex_execution_root)/'studio')
    f.require(str(root) == '/var/lib/hengxin-overseas/execution/studio', 'Wrong production scope')
    return root, session_factory()


def records(session, conversation):
    from sqlalchemy import text
    # All selected values stay server-side; only a digest is saved in receipts.
    queries = [
        ('overseas_studio_conversations','id=:c'),
        ('overseas_studio_turns','conversation_id=:c'),
        ('overseas_studio_uploads','conversation_id=:c'),
        ('overseas_studio_transcript','turn_id IN (SELECT id FROM overseas_studio_turns WHERE conversation_id=:c)'),
        ('overseas_studio_pictures','turn_id IN (SELECT id FROM overseas_studio_turns WHERE conversation_id=:c)'),
        ('overseas_studio_output_files','turn_id IN (SELECT id FROM overseas_studio_turns WHERE conversation_id=:c)'),
        ('overseas_jobs','id IN (SELECT job_id FROM overseas_studio_turns WHERE conversation_id=:c)')]
    result = {}
    for table,where in queries:
        result[table] = session.scalar(text('SELECT count(*)::text || \':\' || md5(coalesce('
            'string_agg(md5(to_jsonb(t)::text),\'\' ORDER BY md5(to_jsonb(t)::text)),\'\')) FROM '+table+' t WHERE '+where),
            {'c':UUID(conversation)})
    return json.dumps(result,sort_keys=True)


def busy_query():
    from sqlalchemy import select, or_
    from app.overseas.execution.models import Job, TERMINAL
    return select(Job.task_id).where(or_(Job.status.not_in(TERMINAL),
        Job.process_id.is_not(None) & Job.process_exited.is_(False)))


def plan(root, factory, work):
    from sqlalchemy import select
    from app.overseas.studio.models import Turn
    from app.overseas.execution.models import Job
    from app.overseas.management.installed_catalog import frozen_package
    f.require(not (work/'plan.json').exists(), 'Plan already exists')
    with factory() as session:
        owned = {(str(t.conversation_id),str(t.id)):(str(t.task_id),j.payload)
                 for t,j in session.execute(select(Turn,Job).join(Job,Turn.job_id==Job.id))}
        busy = {str(v) for v in session.scalars(busy_query())}
    groups, packages, errors, source_cache = {}, 0, {}, {}
    for package in sorted(root.glob('*/rounds/*/skills/*')):
        relative = package.relative_to(root).as_posix()
        conversation,_,turn,_,name = Path(relative).parts
        try:
            f.target(root,relative)
            task,payload = owned[(conversation,turn)]
            if task in busy:
                raise ValueError('task_busy')
            raw = f.read(package.parents[1]/'input.json')
            f.require(raw == f.read(root/conversation/'control'/turn/'input.json'), 'Input copies differ')
            f.require(json.loads(raw) == payload, 'Input differs from frozen database payload')
            skill = payload['skill']
            f.require(skill['name'] == name and skill.get('installedRelease'), 'Unproven Skill source')
            frozen_key = (name,skill['installedRelease'],skill['checksum'])
            if frozen_key not in source_cache:
                original = frozen_package(skill)
                source_cache[frozen_key] = {p:(len(v),f.digest(v)) for p,v in original.files.items()}
            entries,allocated = f.inventory(package)
            actual = {p:(v[4],v[5]) for p,v in entries.items() if v[0]=='file'}
            f.require(actual == source_cache[frozen_key], 'Historical package differs from frozen source')
            key = f.digest(json.dumps([conversation,name,entries],sort_keys=True).encode())
            group = groups.setdefault(key,dict(key=key,conversation=conversation,task=task,
                entries=entries,keep=relative,drop=[],allocated=0,inputs={}))
            group['inputs'][relative] = f.digest(raw)
            if relative != group['keep']:
                group['drop'].append(relative)
                group['allocated'] += allocated
            packages += 1
        except (OSError,ValueError,KeyError,TypeError) as error:
            errors[conversation] = type(error).__name__+':'+str(error)[:80]
    selected = [g for g in groups.values() if g['drop'] and g['conversation'] not in errors]
    result = dict(version=1,root=str(root),groups=selected,excluded=errors,scanned=packages,
        scripts={p.name:f.file_hash(p) for p in (Path(__file__),Path(__file__).with_name('skill-history-files.py'))})
    f.require(selected, 'No eligible duplicate groups')
    f.save(work/'plan.json',result)
    f.backup(root,result,work/'backup.tar.gz')
    f.verify_backup(result,work/'backup.tar.gz')
    summary = dict(groups=len(selected),conversations=len({g['conversation'] for g in selected}),
        duplicatePackages=sum(len(g['drop']) for g in selected),allocated=sum(g['allocated'] for g in selected),
        excluded=len(errors),backupSha256=f.file_hash(work/'backup.tar.gz'),planSha256=f.file_hash(work/'plan.json'))
    f.save(work/'prepared.json',summary)
    return summary


def apply(root, factory, work, acknowledged, plan_hash):
    from sqlalchemy import select
    from app.overseas.studio.models import Conversation, ConversationDeletion
    from app.overseas.tasks.models import Task, TaskDeletion
    prepared = json.loads(f.read(work/'prepared.json'))
    f.require(plan_hash == prepared['planSha256'] == f.file_hash(work/'plan.json'), 'Plan acknowledgement differs')
    f.require(acknowledged == prepared['backupSha256'] == f.file_hash(work/'backup.tar.gz'), 'External backup acknowledgement differs')
    data = json.loads(f.read(work/'plan.json'))
    f.require(data['root'] == str(root), 'Root drift')
    f.require(all(f.file_hash(Path(__file__).with_name(n)) == h for n,h in data['scripts'].items()), 'Script drift')
    f.verify_backup(data,work/'backup.tar.gz')
    result = dict(cleaned=[],skipped={},allocated=0)
    for conversation in sorted({g['conversation'] for g in data['groups']}):
        groups = [g for g in data['groups'] if g['conversation']==conversation]
        task_id = UUID(groups[0]['task'])
        with factory.begin() as session:
            # Same lock order as production submission/deletion; no global worker lock.
            task = session.scalar(select(Task).where(Task.id==task_id).with_for_update(skip_locked=True))
            if task is None:
                result['skipped'][conversation] = 'task_locked_or_missing'; continue
            channel = session.get(Conversation,UUID(conversation))
            if (not channel or channel.task_id != task_id or session.get(TaskDeletion,task_id)
                    or session.get(ConversationDeletion,UUID(conversation))):
                result['skipped'][conversation] = 'busy_or_deleting'; continue
            from app.overseas.execution.models import Job
            if session.scalar(busy_query().where(Job.task_id==task_id).limit(1)):
                result['skipped'][conversation] = 'task_busy'; continue
            lock = f.safe(root/conversation/'.context-prepare.lock')
            f.require(lock.is_file() and lock.stat().st_nlink==1, 'Missing context lock')
            fd = os.open(lock,os.O_RDONLY|os.O_NOFOLLOW|os.O_NOATIME)
            try:
                try:
                    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:
                    result['skipped'][conversation] = 'context_locked'; continue
                for group in groups:
                    for relative,checksum in group['inputs'].items():
                        source = f.target(root,relative).parents[1]/'input.json'
                        f.require(f.digest(f.read(source)) == checksum, 'Frozen input drift')
                count = f.move_checked(root,work,conversation,groups,lambda:records(session,conversation))
                receipt = dict(conversation=conversation,removed=len([n for g in groups for n in g['drop']]),
                    allocated=sum(g['allocated'] for g in groups),preservedEntries=count)
                f.save(work/('completed-'+conversation+'.json'),receipt)
                result['cleaned'].append(receipt)
                result['allocated'] += receipt['allocated']
                print(json.dumps(receipt),flush=True)
            finally:
                os.close(fd)
    f.save(work/'result.json',result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('plan','apply'))
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--backup-sha')
    parser.add_argument('--plan-sha')
    args = parser.parse_args()
    f.require(os.geteuid()==0 and not __import__('sys').flags.optimize, 'Root non-optimized runtime required')
    os.umask(0o077)
    work = f.safe(args.work)
    f.require(work.parent==Path('/opt') and work.name.startswith('hengxin-skill-cleanup-'), 'Wrong work directory')
    if args.action=='plan': work.mkdir(mode=0o700,exist_ok=False)
    root,factory = runtime()
    with (work/'operation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        print(json.dumps(plan(root,factory,work) if args.action=='plan' else
            apply(root,factory,work,args.backup_sha,args.plan_sha)),flush=True)


if __name__=='__main__':
    main()
