"""Bind an independently executed GC receipt to exact on-disk and history evidence."""
import hashlib
import json
from pathlib import Path
import re
import stat

r = None
ROOT = Path('/var/lib/hengxin-overseas/local-skills')
UUID = r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'


def tree_hash(tree):
    return hashlib.sha256(json.dumps(tree, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def history_preserved(before, after):
    r.require(before['tables'] == after['tables'], 'Historical conversation records changed during GC')
    old, new = before['files'], after['files']
    r.require(set(old) <= set(new), 'Historical file/directory disappeared during GC')
    added = set(new) - set(old)
    for name in added:
        row = new[name]
        kind = row[0]
        owner = re.fullmatch(r'(?:studio/)?'+UUID, name)
        history = re.fullmatch(r'(?:studio/)?'+UUID+r'/skill-history(?:/[a-f0-9]{64}(?:/[^/]+(?:/.*)?)?)?', name)
        lock = re.fullmatch(r'(?:studio/)?'+UUID+r'/\.context-prepare\.lock', name)
        r.require(kind in (stat.S_IFDIR, stat.S_IFREG), 'Unexpected history file type')
        r.require((history is not None) or (lock is not None and kind == stat.S_IFREG and row[1] == 0) or
                  ((owner is not None or name == 'studio') and kind == stat.S_IFDIR),
                  'GC added content outside owned Skill history: '+name)
    for name, prior in old.items():
        current = new[name]
        if prior[0] == stat.S_IFDIR and any(n.startswith(name+'/') for n in added):
            r.require(prior[:1]+prior[3:] == current[:1]+current[3:], 'Existing history directory identity changed')
        else:
            r.require(prior == current, 'Existing historical file metadata changed: '+name)


def proof(work, data):
    path = work/'maintenance-proof.json'
    marker = json.loads((work/'MAINTENANCE_ACCEPTED').read_text())
    r.require(marker == {'manifest': data['manifest'], 'sha256': r.digest(path)}, 'Maintenance proof drift')
    saved = json.loads(path.read_text())
    r.require(saved['manifest'] == data['manifest'] and saved['beforeSkillTreeSha256'] == tree_hash(data['protected']['skills']),
              'Maintenance baseline drift')
    return saved


def expected_skills(work, data):
    return proof(work, data)['afterSkillTree'] if (work/'MAINTENANCE_ACCEPTED').exists() else data['protected']['skills']


def verify_history(work, data):
    preserve = r.helper('skill-reuse-preserve')
    if not (work/'MAINTENANCE_ACCEPTED').exists():
        preserve.verify(work, data)
        return
    saved = proof(work, data)
    r.require(preserve.snapshot(data) == saved['historyAfter'], 'History changed after accepted maintenance')


def begin(work, data):
    r.require(not (work/'MAINTENANCE_ACCEPTED').exists(), 'Maintenance already accepted')
    r.helper('skill-reuse-gate').require_closed(work, data)
    node = json.loads((work/'gate.json').read_text())['node']
    marker = work/'MAINTENANCE_STARTED'
    if marker.exists():
        saved = json.loads(marker.read_text())
        r.require(saved['manifest'] == data['manifest'] and saved['node'] == node, 'Maintenance identity drift')
    else:
        paused = r.sql(r.DB, 'SELECT paused FROM overseas_execution_gate WHERE id=1')
        r.require(paused in ('t', 'f'), 'Execution gate missing')
        # Fixed first: an interrupted GC must not roll back to schema-1 readers.
        r.private(marker, {'manifest': data['manifest'], 'gateWasPaused': paused == 't', 'node': node})
    if not r.worker('status', node)['paused']:
        r.require(r.worker('pause')['node'] == node, 'Worker identity drift')
    r.worker('paused', node)
    r.sql(r.DB, "BEGIN; SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='10s'; "
        "SELECT id FROM overseas_execution_gate WHERE id=1 FOR UPDATE; "
        "UPDATE overseas_execution_gate SET paused=true WHERE id=1 AND NOT EXISTS "
        "(SELECT 1 FROM overseas_jobs WHERE status NOT IN ('succeeded','failed','cancelled') "
        "OR (process_id IS NOT NULL AND NOT process_exited)); COMMIT;")
    r.require(r.sql(r.DB, 'SELECT paused FROM overseas_execution_gate WHERE id=1') == 't', 'Execution gate pause failed')
    return 'MAINTENANCE_READY_CONSUMER_AND_DATABASE_GATE_PAUSED_NO_GC_PERFORMED'


def accept(work, data, receipt_path):
    r.require((work/'MAINTENANCE_STARTED').exists() and not (work/'MAINTENANCE_ACCEPTED').exists(),
              'Maintenance start missing or receipt already accepted')
    r.helper('skill-reuse-gate').require_closed(work, data)
    r.worker('paused', json.loads((work/'gate.json').read_text())['node'])
    r.require(r.sql(r.DB, 'SELECT paused FROM overseas_execution_gate WHERE id=1') == 't', 'Maintenance DB gate reopened')
    receipt = json.loads(receipt_path.read_text())
    r.require(receipt['manifest'] == data['manifest'] and
              receipt['beforeSkillTreeSha256'] == tree_hash(data['protected']['skills']), 'GC receipt baseline differs')
    result = receipt['result']
    r.require(result['dryRun'] is False and result['cleanupComplete'] is True and
              re.fullmatch('[a-f0-9]{64}', result['release']), 'GC incomplete or dry-run only')
    for key in ('centralBytes', 'afterBytes', 'historyBytes', 'reclaimedBytes', 'libraryBytes', 'libraryAfterBytes'):
        r.require(type(result[key]) is int and result[key] >= 0, 'Invalid GC byte accounting')
    r.require(result['reclaimedBytes'] == max(0, result['centralBytes']-result['afterBytes']-result['historyBytes']),
              'GC net reclaimed accounting differs')
    r.require(not any(path.is_symlink() for path in ROOT.rglob('*')), 'Linked post-GC Skill tree')
    actual = r.b.tree(ROOT)
    r.require(actual == receipt['afterSkillTree'], 'GC actual Skill tree differs from expected receipt')
    r.require(json.loads((ROOT/'current.json').read_text())['release'] == result['release'], 'GC current release differs')
    r.require(not (ROOT/'.pending.json').exists(), 'Unfinished publication transaction')
    current = json.loads((ROOT/'releases'/result['release']/'manifest.json').read_text())
    current_hash = hashlib.sha256(json.dumps(current, sort_keys=True, ensure_ascii=False,
        separators=(',', ':')).encode()).hexdigest()
    r.require(current['schema'] == 2 and current_hash == result['release'], 'GC schema-2 index integrity differs')
    old_release = receipt['beforeRelease']
    r.require(isinstance(old_release, str) and re.fullmatch('[a-f0-9]{64}', old_release) and
              old_release == data['currentRelease'], 'GC old release differs from prepared current pointer')
    old_name = 'releases/'+old_release+'/manifest.json'
    r.require(data['protected']['skills'].get(old_name) == r.digest(ROOT/old_name), 'Original release index changed')
    previous = json.loads((ROOT/old_name).read_text())
    r.require(previous['items'] == current['items'] and len(current['items']) == result['skills'],
              'GC changed current catalog contents')
    preserve = r.helper('skill-reuse-preserve')
    before = json.loads((work/'conversation-before.json').read_text())
    r.require(json.loads((work/'CONVERSATION_BASELINE').read_text()) ==
              {'manifest': data['manifest'], 'sha256': r.digest(work/'conversation-before.json')}, 'History baseline drift')
    after = preserve.snapshot(data)
    history_preserved(before, after)
    saved = dict(receipt, historyAfter=after)
    r.private(work/'maintenance-proof.json', saved)
    r.private(work/'MAINTENANCE_ACCEPTED', {'manifest': data['manifest'], 'sha256': r.digest(work/'maintenance-proof.json')})
    return 'MAINTENANCE_RECEIPT_BOUND_EXACT_TREE_AND_HISTORY_PRESERVATION_VERIFIED'


def resume(work, data):
    if not (work/'MAINTENANCE_STARTED').exists():
        return
    proof(work, data)
    marker = json.loads((work/'MAINTENANCE_STARTED').read_text())
    r.require(marker['manifest'] == data['manifest'], 'Maintenance marker drift')
    started = work/'MAINTENANCE_RESUME_STARTED'
    if not started.exists():
        r.require(r.sql(r.DB, 'SELECT paused FROM overseas_execution_gate WHERE id=1') == 't', 'Maintenance gate changed')
        r.private(started, {'manifest': data['manifest']})
    r.require(json.loads(started.read_text()) == {'manifest': data['manifest']}, 'Maintenance resume proof drift')
    value = 'true' if marker['gateWasPaused'] else 'false'
    r.sql(r.DB, 'UPDATE overseas_execution_gate SET paused='+value+' WHERE id=1')
    r.require(r.sql(r.DB, 'SELECT paused FROM overseas_execution_gate WHERE id=1') == ('t' if marker['gateWasPaused'] else 'f'),
              'Execution gate restoration failed')
    r.worker('resume', marker['node'])
