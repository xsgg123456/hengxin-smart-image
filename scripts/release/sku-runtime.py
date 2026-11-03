"""Pinned overseas SKU draft release; preserve Skill and workflow configuration."""
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
VERSION, OLD_REVISION, REVISION = '0.2.60', 'overseas_0025', 'overseas_0026'
BASE_IMAGE = 'sha256:ad35f03ca9dbd3fa09d6932e5aa19ae60250d1e449cc57da265eab411fcb33c1'
FILES = {'app/overseas/'+name+'.py' for name in (
    'db', 'main', 'tasks/schemas', 'tasks/service', 'materials/files', 'materials/router',
    'materials/schemas', 'materials/service')} | {
    'app/overseas/drafts/'+name+'.py' for name in (
        '__init__', 'models', 'schemas', 'service', 'source', 'selection', 'hooks',
        'router', 'transfer', 'queue', 'worker', 'http_logging')} | {
    'pyproject.toml', 'uv.lock', 'migrations/overseas/env.py', 'migrations/overseas/versions/0026_requirement_drafts.py'}
# Native retains its old task/material API dependencies and only advances the schema marker.
NATIVE_FILES = {'app/overseas/db.py'}
UNITS = ('hengxin-overseas-worker.service', 'hengxin-overseas-outbox.service')
TESTS = tuple('test_overseas_'+name+'.py' for name in (
    'drafts', 'draft_worker', 'draft_postgres', 'draft_migration', 'sku_source', 'multiple_materials', 'materials', 'tasks', 'tasks_postgres',
    'requirements', 'requirements_postgres', 'requirement_language', 'requirement_language_migration',
    'database', 'pictures', 'pictures_postgres', 'workflow_grant', 'workflow_grant_studio'))
HELPERS = ('account-runtime', 'account-worker', 'image-cache-runtime', 'skill-platform-baseline',
           'skill-platform-runtime', 'skill-platform-worker', 'sku-runtime', 'sku-deploy',
           'sku-database', 'sku-native', 'sku-frontend', 'sku-environment')
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
    require(re.fullmatch(r'sku-[a-z0-9-]+', manifest['release']), 'Unsafe release tag')
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


NEW_TABLES = {'overseas_requirement_drafts', 'overseas_draft_materials', 'overseas_draft_imports'}
TABLE_FILTER = 'table_name NOT IN (' + ','.join("'"+n+"'" for n in sorted(NEW_TABLES)) + ')'


def columns(database):
    column_hash = sql(database, "SELECT md5(coalesce(string_agg(to_jsonb(c)::text,'' ORDER BY table_name,ordinal_position),'')) "
               "FROM information_schema.columns c WHERE table_schema='public' AND " + TABLE_FILTER)
    return hashlib.sha256(json.dumps([column_hash, schema_extra(database, new=False)], sort_keys=True).encode()).hexdigest()


def normalized_constraint(definition):
    """Canonicalize only pg_restore's varchar-literal-array to text[] cast rewrite.

    PostgreSQL may distribute the array cast over its literal elements when it
    reparses a dumped CHECK. Keep the complete CHECK shape, column, literals,
    element order and constraint flags; unknown expressions remain byte-exact.
    """
    identifier = r'(?:[a-z_][a-z0-9_]*|"(?:[^"]|"")+")'
    match = re.fullmatch(
        r'CHECK \(\(\((' + identifier + r')\)::text = ANY \(\(ARRAY\[(.*)\]'
        r'\)::text\[\]\)\)\)((?: NO INHERIT)?(?: NOT VALID)?)', definition)
    if not match:
        return definition
    # SQL quotes may contain commas/parentheses and escaped single quotes. Do
    # not touch backslash strings, expressions, typmods, or other cast types.
    literal = r"'(?:[^'\\]|'')*'::character varying"
    values = match[2]
    if not re.fullmatch(literal + r'(?:, ' + literal + r')*', values):
        return definition
    elements = re.findall(literal, values)
    return ('CHECK (((' + match[1] + ')::text = ANY (ARRAY[' +
            ', '.join('(' + item + ')::text' for item in elements) + '])))' + match[3])


def schema_extra(database, new=True):
    predicate = ('NOT ('+TABLE_FILTER+')') if new else TABLE_FILTER
    indexes = sql(database, "SELECT coalesce(json_agg(json_build_array(tablename,indexname,indexdef) "
        "ORDER BY tablename,indexname),'[]') FROM pg_indexes WHERE schemaname='public' AND " +
        predicate.replace('table_name', 'tablename'))
    constraints = sql(database, "SELECT coalesce(json_agg(json_build_array(t.relname,c.conname,"
        "pg_get_constraintdef(c.oid)) ORDER BY t.relname,c.conname),'[]') FROM pg_constraint c "
        "JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace "
        "WHERE n.nspname='public' AND " + predicate.replace('table_name', 't.relname'))
    return {'indexes': json.loads(indexes), 'constraints': [
        [table, name, normalized_constraint(definition)]
        for table, name, definition in json.loads(constraints)]}


def verify_new_tables(database, before=False):
    names = set(sql(database, "SELECT tablename FROM pg_tables WHERE schemaname='public'").splitlines())
    require(names & NEW_TABLES == (set() if before else NEW_TABLES), 'Unexpected draft tables')
    if not before:
        for name in sorted(NEW_TABLES):
            require(sql(database, 'SELECT count(*) FROM "'+name+'"') == '0', 'New draft table is not empty')


def migration_fingerprints(database):
    # Exclude only newly introduced tables and the Alembic marker; keep every old value.
    return {name:rows for name,rows in fingerprints(database).items()
            if name not in NEW_TABLES | {'overseas_alembic_version'}}


def draft_schema(database):
    return {'columns': json.loads(sql(database,
        "SELECT coalesce(json_agg(to_jsonb(c) ORDER BY table_name,ordinal_position),'[]') "
        "FROM information_schema.columns c WHERE table_schema='public' AND NOT ("+TABLE_FILTER+")")),
        **schema_extra(database)}


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
