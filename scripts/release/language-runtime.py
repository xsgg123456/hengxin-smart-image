"""Pinned overseas language release; preserve Skill and workflow configuration."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True

def helper(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = helper('skill-platform-runtime')
a, b = base.a, base.b
run, require, digest, private = a.run, a.require, a.digest, a.private
API, PG, DB = base.API, base.PG, base.DB
VERSION, OLD_REVISION, REVISION = '0.2.59', 'overseas_0024', 'overseas_0025'
BASE_IMAGE = 'sha256:992bd43568641daaad9bae2bcb49e8d401925e75583633c4f81b58195784d871'
FILES = {'app/overseas/'+name+'.py' for name in (
    'db', 'tasks/models', 'tasks/schemas', 'tasks/requirements', 'tasks/queries', 'tasks/service',
    'archives/models', 'archives/snapshot', 'archives/service')} | {
    'migrations/overseas/versions/0025_requirement_language.py'}
# Native never imports the API-only archive service; retain its older delivery dependencies.
NATIVE_FILES = {name for name in FILES if name.startswith('app/')} - {'app/overseas/archives/service.py'}
UNITS = ('hengxin-overseas-worker.service', 'hengxin-overseas-outbox.service')
TESTS = tuple('test_overseas_'+name+'.py' for name in (
    'requirement_language', 'requirement_language_migration', 'tasks', 'tasks_postgres',
    'requirements', 'requirements_postgres', 'market_optional', 'pictures', 'pictures_postgres',
    'archive_deletion', 'archive_deletion_postgres', 'archive_assignment', 'archive_assignment_postgres',
    'archive_audit', 'archive_cover', 'workflow_grant', 'workflow_grant_studio'))
HELPERS = ('account-runtime', 'account-worker', 'image-cache-runtime', 'skill-platform-baseline',
           'skill-platform-runtime', 'skill-platform-worker', 'language-runtime', 'language-deploy',
           'language-database', 'language-native', 'language-frontend')
base.FILES = b.FILES = FILES
inspect, hashes, unchanged, sql = base.inspect, base.hashes, base.unchanged, base.sql


def worker(mode, node='-', timeout=40):
    state = a.worker('overseas')
    raw = (Path('/proc')/str(state['pid'])/'environ').read_bytes()
    env = dict(x.decode().split('=',1) for x in raw.split(b'\0') if x)
    env['PYTHONPATH'] = state['cwd']
    return json.loads(run(state['cwd']+'/.venv/bin/python','-B',str(Path(__file__).with_name('skill-platform-worker.py')),
        mode,str(state['pid']),node,cwd=state['cwd'],env=env,timeout=timeout))


def native_baselines(native):
    require(isinstance(native, dict) and set(native) == {'units'} and
            isinstance(native['units'], dict) and set(native['units']) == set(UNITS),
            'Unexpected native baseline units')
    for unit in UNITS:
        saved = native['units'][unit]
        require(isinstance(saved, dict) and set(saved) == {'files'} and
                isinstance(saved['files'], dict) and set(saved['files']) == NATIVE_FILES,
                'Unexpected native baseline scope')
        require(all(value is None or isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value)
                    for value in saved['files'].values()), 'Invalid native baseline checksum')
    return native


def verify_package(source):
    manifest = json.loads((source/'release.json').read_text())
    require(manifest['version'] == VERSION and set(manifest['api']['files']) == FILES,
            'Unexpected release scope')
    require(manifest['api']['image'] == BASE_IMAGE, 'Unexpected API baseline')
    require(re.fullmatch('[a-f0-9]{40}', manifest.get('commit', '')) and
            re.fullmatch('[a-f0-9]{64}', manifest.get('candidateId', '')), 'Missing reviewed commit identity')
    native_baselines(manifest.get('native'))
    require(re.fullmatch(r'language-[a-z0-9-]+', manifest['release']), 'Unsafe release tag')
    required = {'api/'+name for name in FILES} | {'tests/'+name for name in ('conftest.py', *TESTS)} | {
        'frontend/package.json', 'frontend/dist/index.html'} | {'scripts/release/'+n+'.py' for n in HELPERS}
    require(required <= set(manifest['files']), 'Incomplete release package')
    for name, expected in manifest['files'].items():
        path = source/name
        require(path.resolve().is_relative_to(source.resolve()) and
                not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe package path')
        require(digest(path) == expected, 'Package checksum mismatch: '+name)
    paths = list(source.rglob('*'))
    require(not any(p.is_symlink() for p in paths), 'Linked package entry')
    actual = {p.relative_to(source).as_posix() for p in paths if p.is_file()}
    require(actual == set(manifest['files']) | {'release.json'}, 'Unmanifested package content')
    require({n for n in manifest['files'] if n.startswith('api/')} == {'api/'+n for n in FILES},
            'Unexpected API content')
    require({n for n in manifest['files'] if n.startswith('scripts/')} ==
            {'scripts/release/'+n+'.py' for n in HELPERS}, 'Unexpected release helper scope')
    for name, patch in manifest['api']['files'].items():
        require((patch['baseline'] is None or re.fullmatch('[a-f0-9]{64}', patch['baseline'])) and
                patch['sha256'] == manifest['files']['api/'+name], 'Patch checksum mismatch')
    require(json.loads((source/'frontend/package.json').read_text())['version'] == VERSION,
            'Frontend version mismatch')
    return manifest


def fingerprints(database):
    result = {}
    names = sql(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
    for name in names:
        require(re.fullmatch('[a-z][a-z0-9_]*', name), 'Invalid table')
        result[name] = json.loads(sql(database,
            f"SELECT coalesce(json_agg(md5(to_jsonb(t)::text) ORDER BY md5(to_jsonb(t)::text)), '[]') FROM \"{name}\" t"))
    return result


NEW_COLUMNS = {('overseas_tasks', 'language'): 2,
               ('overseas_archives', 'task_name'): 80, ('overseas_archives', 'language'): 2}
COLUMN_FILTER = "((table_name='overseas_tasks' AND column_name='language') OR " \
    "(table_name='overseas_archives' AND column_name IN ('task_name','language')))"


def columns(database):
    return sql(database, "SELECT md5(coalesce(string_agg(to_jsonb(c)::text,'' ORDER BY table_name,ordinal_position),'')) "
               "FROM information_schema.columns c WHERE table_schema='public' AND NOT " + COLUMN_FILTER)


def verify_new_columns(database, before=False):
    rows = json.loads(sql(database,
        "SELECT coalesce(json_agg(json_build_array(table_name,column_name,data_type,character_maximum_length,"
        "is_nullable,column_default)), '[]') FROM information_schema.columns WHERE table_schema='public' AND " + COLUMN_FILTER))
    expected = set() if before else {(table, name, 'character varying', length, 'YES', None)
                                     for (table, name), length in NEW_COLUMNS.items()}
    require({tuple(row) for row in rows} == expected, 'Unexpected new language columns')


def migration_fingerprints(database):
    """Exclude exactly the new columns; all old row data must remain identical."""
    result = {}
    names = sql(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
    for name in names:
        require(re.fullmatch('[a-z][a-z0-9_]*', name), 'Invalid table')
        if name == 'overseas_alembic_version':
            continue
        row = "to_jsonb(t)"
        if name == 'overseas_tasks':
            row += "-'language'"
        elif name == 'overseas_archives':
            row += "-'task_name'-'language'"
        result[name] = json.loads(sql(database,
            f"SELECT coalesce(json_agg(md5(({row})::text) ORDER BY md5(({row})::text)), '[]') FROM \"{name}\" t"))
    return result


def language_snapshots(database, before=False):
    """Bind each archive's expected values to its actual task, including absent links."""
    query = ("SELECT coalesce(json_object_agg(a.id::text,json_build_array(t.name,NULL)), '{}') "
             "FROM overseas_archives a LEFT JOIN overseas_tasks t ON t.id=a.task_id") if before else (
             "SELECT coalesce(json_object_agg(id::text,json_build_array(task_name,language)), '{}') FROM overseas_archives")
    return json.loads(sql(database, query))


def verify_languages(database, expected):
    require(sql(database, 'SELECT count(*) FROM overseas_tasks WHERE language IS NOT NULL') == '0',
            'Historical task language must remain unknown')
    require(language_snapshots(database) == expected, 'Archive backfill differs from actual task source')


def environment_hash(items):
    """Store only a checksum; preserve business configuration without exposing secrets."""
    settings = sorted(item for item in items if item.startswith(('OVERSEAS_', 'HX_BUSINESS_CONTEXT=')))
    return hashlib.sha256(json.dumps(settings).encode()).hexdigest()


def native_environment(unit):
    require(unit in UNITS, 'Unexpected native unit')
    pid = int(run('systemctl','show',unit,'-p','MainPID','--value'))
    require(pid > 0, 'Native environment requires running service')
    raw = (Path('/proc')/str(pid)/'environ').read_bytes()
    return environment_hash(item.decode() for item in raw.split(b'\0') if item)


def worker_probe(domain, mode, work, timeout=150):
    """Use the retained probe with bytecode disabled, keeping package bytes immutable."""
    require(domain == 'overseas', 'Only overseas worker may be probed')
    state = a.worker(domain)
    raw = (Path('/proc')/str(state['pid'])/'environ').read_bytes()
    env = dict(item.decode().split('=',1) for item in raw.split(b'\0') if item)
    env['PYTHONPATH'] = state['cwd']
    return json.loads(run(state['cwd']+'/.venv/bin/python', '-B',
        str(Path(__file__).with_name('account-worker.py')), domain, mode, str(state['pid']), str(work),
        cwd=state['cwd'], env=env, timeout=timeout))
