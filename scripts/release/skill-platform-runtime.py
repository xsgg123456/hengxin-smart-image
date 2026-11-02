"""Pinned overseas API helpers; no domestic or native service mutation."""
import importlib.util
import json
from pathlib import Path


def helper(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


a = helper('account-runtime')
b = helper('skill-platform-baseline')
run, require, digest, private = a.run, a.require, a.digest, a.private
API, FILES = b.API, b.FILES
VERSION, REVISION = '0.2.57', 'overseas_0023'
TESTS = tuple('test_overseas_'+name+'.py' for name in (
    'skill_platforms','skill_platforms_postgres','skill_platforms_migration','installed_skills',
    'management_freeze','pictures','pictures_protocol','skill_availability','installed_titles',
    'management','studio','requirements','tasks','configuration'))
PG = 'hengxin-overseas-overseas-postgres-1'
DB = (PG, 'postgres', 'hengxin_overseas')


def inspect():
    return json.loads(run('docker', 'inspect', API))[0]


def verify_package(source):
    manifest = json.loads((source/'release.json').read_text())
    require(manifest['version'] == VERSION and set(manifest['api']['files']) == FILES, 'Unexpected release scope')
    for name, expected in manifest['files'].items():
        path = source/name
        require(path.resolve().is_relative_to(source.resolve()) and not any(p.is_symlink() for p in (path,*path.parents)),
                'Unsafe package path')
        require(digest(path) == expected, 'Package checksum mismatch: ' + name)
    require(all('api/'+name in manifest['files'] for name in FILES), 'Incomplete API package')
    return manifest


def hashes(image):
    previous = a.API_FILES
    try:
        a.API_FILES = FILES
        return a.api_hashes(image)
    finally:
        a.API_FILES = previous


def worker(mode, node='-'):
    state = a.worker('overseas')
    raw = (Path('/proc')/str(state['pid'])/'environ').read_bytes()
    env = dict(x.decode().split('=',1) for x in raw.split(b'\0') if x)
    env['PYTHONPATH'] = state['cwd']
    return json.loads(run(state['cwd']+'/.venv/bin/python', '-B', str(Path(__file__).with_name('skill-platform-worker.py')),
                         mode, str(state['pid']), node, cwd=state['cwd'], env=env, timeout=40))


def unchanged(before):
    after = b.snapshot()
    require(before['units'] == after['units'], 'Native service or source drift')
    require(before['skills'] == after['skills'], 'Installed Skill bytes drift')
    for name, value in before['containers'].items():
        if name != API:
            require(after['containers'].get(name) == value, 'Unrelated container drift: '+name)


def sql(database, query):
    return run('docker','exec',database[0],'psql','-v','ON_ERROR_STOP=1','-U',database[1],'-d',database[2],'-Atc',query)


def fingerprints(database):
    import re
    result = {}
    names = sql(database,"SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
    for name in names:
        require(re.fullmatch('[a-z][a-z0-9_]*',name), 'Invalid table')
        if name == 'overseas_alembic_version':
            continue
        row = "to_jsonb(t)-'platforms'" if name == 'overseas_installed_skill_availability' else 'to_jsonb(t)'
        aggregate = (f"json_object_agg(id::text,md5(({row})::text))" if name == 'overseas_installed_skill_availability'
                     else f"json_agg(md5(({row})::text) ORDER BY md5(({row})::text))")
        empty = '{}' if name == 'overseas_installed_skill_availability' else '[]'
        result[name] = json.loads(sql(database,f"SELECT coalesce({aggregate},'{empty}') FROM \"{name}\" t"))
    return result


def columns(database):
    return sql(database,"SELECT md5(coalesce(string_agg(to_jsonb(c)::text,'' ORDER BY table_name,ordinal_position),'')) "
        "FROM information_schema.columns c WHERE table_schema='public' AND NOT "
        "(table_name='overseas_installed_skill_availability' AND column_name='platforms')")


def platform_seed(database, source, before):
    expected = {row['name']:row['platforms'] for row in
                json.loads((source/'frontend/preview-skill-platforms/seed.json').read_text())}
    actual = json.loads(sql(database,"SELECT json_object_agg(id,platforms) FROM overseas_installed_skill_availability"))
    require(set(actual) == set(expected) | set(before['overseas_installed_skill_availability']),
            'Unexpected availability records added')
    require(all(actual.get(k) == v for k,v in expected.items()),'Initial platform associations differ')
    require(all(value == [] for key,value in actual.items() if key not in expected),'Unknown Skill was grouped')


def preserved(before, after):
    require(set(before) == set(after), 'Migration table set changed')
    for name, rows in before.items():
        if name == 'overseas_installed_skill_availability':
            require(all(after[name].get(k) == v for k,v in rows.items()), 'Existing switches changed')
        else:
            require(after[name] == rows, 'Unexpected records added: '+name)
