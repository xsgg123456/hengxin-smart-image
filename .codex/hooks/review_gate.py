"""Review protocol; callers must fail closed when these functions raise."""
from pathlib import Path

from review_files import changes, git_snapshot, identity, snapshot
from review_store import package, read, report, require, transaction


def reference(state):
    approved = state['approved']
    return approved['snapshot'] if approved else state['baseline']


def status(state, current):
    previous = reference(state)
    return {'currentId': identity(current),
            'reviewedId': state['approved']['snapshot']['id'] if state['approved'] else None,
            'changedFiles': changes(previous['files'], current),
            'approved': state['approved'] is not None and previous['files'] == current}


def run(root, action, data):
    root = Path(root).resolve()
    require(isinstance(data, dict), '审查命令参数必须是 JSON 对象')
    if action == 'review-status':
        return status(read(root), snapshot(root))
    # Recovery can replace an expired report, but must never bypass state schema
    # checks or erase the old approval before a new candidate is approved.
    with transaction(root, verify_report=action not in {'review-prepare', 'review-approve'},
                     verify_final_report=action != 'review-prepare') as state:
        current = snapshot(root)
        if action == 'review-prepare':
            state['candidate'] = package(current)
            return {'candidateId': state['candidate']['id']}
        if action == 'review-approve':
            candidate = state['candidate']
            require(candidate is not None and data.get('candidateId') == candidate['id'],
                    '候选编号不匹配，请先执行 review-prepare')
            require(current == candidate['files'],
                    '审查期间文件已变化：' + ', '.join(changes(candidate['files'], current)) + '；重新执行 review-prepare 和审查')
            require(data.get('stage1') == data.get('stage2') == 'PASS', '两阶段审查均须 PASS')
            credential = report(root, data.get('report'))
            state['approved'] = {'snapshot': package(current), 'report': credential,
                                 'stage1': 'PASS', 'stage2': 'PASS'}
            state['checkpoint'] = None
            return {'approved': True, 'reviewedId': identity(current)}
        if action == 'review-checkpoint':
            reason = data.get('reason')
            require(isinstance(reason, str) and bool(reason.strip()), 'checkpoint 必须说明暂停原因')
            state['checkpoint'] = {'id': identity(current), 'reason': reason.strip(), 'used': False}
            return {'checkpointId': identity(current), 'reason': reason.strip()}
        raise ValueError('未知审查动作：' + action)


def stop(root):
    root = Path(root).resolve()
    with transaction(root) as state:
        current = snapshot(root)
        checkpoint = state['checkpoint']
        if checkpoint is not None:
            if checkpoint['id'] != identity(current):
                state['checkpoint'] = None
            elif not checkpoint['used']:
                checkpoint['used'] = True
                return None
        changed = changes(reference(state)['files'], current)
        if changed:
            return {'decision': 'block', 'reason': '当前快照尚未通过审查，变化文件：' + ', '.join(changed)
                    + '。执行 review-prepare，派发 code-reviewer 两阶段审查后 review-approve；中途暂停用 review-checkpoint 并说明原因。'}
    return None


def check_commit(root):
    root = Path(root).resolve()
    with transaction(root) as state:
        staged = git_snapshot(root, 'index')
        changed = changes(git_snapshot(root, 'HEAD'), staged)
        if not changed:
            return None
        approved = state['approved']
        if approved is None:
            return '提交被阻止：暂存区尚未审查：' + ', '.join(changed) + '。请执行 review-prepare 和两阶段审查，再 review-approve。'
        files = approved['snapshot']['files']
        mismatches = [name for name in changed if staged.get(name) != files.get(name)]
        if mismatches:
            return '提交被阻止：暂存版本与已批准快照不同：' + ', '.join(mismatches) + '。请核对 git add 内容并重新审查。'
    return None
