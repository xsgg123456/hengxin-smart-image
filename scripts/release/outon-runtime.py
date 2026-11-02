"""Pinned overseas designer release and independent Skill installation."""
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
VERSION, OLD_REVISION, REVISION = '0.2.58', 'overseas_0023', 'overseas_0024'
BASE_IMAGE = 'sha256:e4fa8e1f4644120c6de5f588ce5f52a1d2c53a78f7f2243102cfa13677045dd7'
FILES = {'app/overseas/'+name+'.py' for name in (
    'auth/models', 'auth/dependencies', 'auth/router', 'config', 'db', 'permissions', 'members/schemas', 'materials/service',
    'management/models', 'management/skills',
    'tasks/schemas', 'tasks/requirements', 'tasks/queries', 'tasks/service',
    'studio/recovery_router', 'studio/recovery_files', 'studio/queries', 'studio/message_metadata')} | {
    'migrations/overseas/versions/0024_designer_roles.py'}
NATIVE_FILES = {name for name in FILES if name.startswith('app/')}
UNITS = ('hengxin-overseas-worker.service', 'hengxin-overseas-outbox.service')
TESTS = tuple('test_overseas_'+name+'.py' for name in (
    'auth', 'permissions', 'single_role', 'designer_roles', 'designer_roles_migration',
    'tasks', 'tasks_postgres', 'requirements', 'requirements_postgres', 'market_optional',
    'members', 'members_postgres', 'materials', 'materials_faults', 'materials_postgres',
    'studio', 'studio_postgres', 'studio_execution', 'assignment', 'plans', 'pictures',
    'management', 'management_operators', 'management_freeze', 'skill_platforms', 'installed_skills',
    'workflow_grant', 'workflow_grant_studio', 'configuration', 'full_access_grant', 'studio_file_recovery')) + (
    'test_studio_message_metadata.py', 'test_studio_message_metadata_postgres.py',
    'test_studio_image_preview.py', 'test_studio_material_list.py',
    'test_studio_recovery_transport.py', 'test_studio_reopen.py')
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
    native_baselines(manifest.get('native'))
    require(re.fullmatch(r'outon-[a-z0-9-]+', manifest['release']), 'Unsafe release tag')
    required = {'api/'+name for name in FILES} | {'tests/'+name for name in ('conftest.py', *TESTS)} | {
        'frontend/package.json', 'frontend/dist/index.html', 'scripts/release/outon-workflow.py'}
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


def columns(database):
    return sql(database, "SELECT md5(coalesce(string_agg(to_jsonb(c)::text,'' ORDER BY table_name,ordinal_position),'')) "
               "FROM information_schema.columns c WHERE table_schema='public'")


def affected_members(database):
    return json.loads(sql(database, "SELECT coalesce(json_agg(user_id::text ORDER BY user_id),'[]') "
        "FROM overseas_member_roles WHERE role IN ('operator','operator_manager')"))


def migration_fingerprints(database, affected, before=False):
    """Ignore only changed timestamps; all IDs, other fields and unrelated rows stay exact."""
    require(all(re.fullmatch('[a-f0-9-]{36}', value) for value in affected), 'Invalid affected member')
    ids = ','.join("'"+value+"'::uuid" for value in affected) or 'NULL'
    result = {}
    names = sql(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
    for name in names:
        require(re.fullmatch('[a-z][a-z0-9_]*', name), 'Invalid table')
        if name == 'overseas_alembic_version':
            continue
        row = 'to_jsonb(t)'
        if name == 'overseas_member_roles':
            changed = "to_jsonb(t)-'updated_at'"
            if before:
                changed += " || jsonb_build_object('role',CASE role WHEN 'operator' THEN 'designer' WHEN " \
                    "'operator_manager' THEN 'design_manager' ELSE role END)"
            row = f'CASE WHEN user_id IN ({ids}) THEN {changed} ELSE to_jsonb(t) END'
        elif name == 'overseas_members':
            changed = "to_jsonb(t)-'updated_at'"
            if before:
                changed += " || jsonb_build_object('version',version+1)"
            row = f'CASE WHEN id IN ({ids}) THEN {changed} ELSE to_jsonb(t) END'
        result[name] = json.loads(sql(database,
            f"SELECT coalesce(json_agg(md5(({row})::text) ORDER BY md5(({row})::text)), '[]') FROM \"{name}\" t"))
    return result
