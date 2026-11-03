"""Private backup, isolated restore/migration proof and guarded overseas draft migration."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('sku_runtime', Path(__file__).with_name('sku-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def closed_gate(work, data):
    live = r.inspect()
    r.require(live['Id'] == data['oldId'] and not live['State']['Running'], 'Original API must remain stopped')
    gate = json.loads((work/'gate.json').read_text())
    r.require(gate['manifest'] == data['manifest'] and gate['phase'] == 'api-stopped-consumer-paused',
              'Gate proof mismatch')
    r.helper('sku-native').stopped()
    r.require(r.sql(r.DB, 'SELECT version_num FROM overseas_alembic_version') == r.OLD_REVISION, 'Schema drift')


def migrated(database, expected, schema, columns):
    r.require(r.sql(database, 'SELECT version_num FROM overseas_alembic_version') == r.REVISION, 'Migration revision mismatch')
    r.require(r.migration_fingerprints(database) == expected, 'Unexpected migration data changes')
    r.require(r.columns(database) == columns, 'Existing schema columns changed')
    r.verify_new_tables(database)
    r.require(r.draft_schema(database) == schema, 'Draft schema differs from isolated migration')


def isolated_command(name, image):
    env = {'HX_BUSINESS_CONTEXT':'overseas',
        'OVERSEAS_DATABASE_URL':'postgresql+psycopg://postgres@127.0.0.1/'+r.DB[2],
        'OVERSEAS_REDIS_URL':'redis://127.0.0.1:6379/0','OVERSEAS_MINIO_ENDPOINT':'127.0.0.1:9000',
        'OVERSEAS_MINIO_ACCESS_KEY':'isolated','OVERSEAS_MINIO_SECRET_KEY':'isolated',
        'OVERSEAS_MINIO_BUCKET':'isolated','OVERSEAS_CODEX_EXECUTION_ROOT':'/tmp/execution',
        'OVERSEAS_SKILL_INSTALL_ROOT':'/tmp/install','OVERSEAS_LOCAL_SKILL_ROOT':'/tmp/skills'}
    command = ['docker','run','--rm','--network','container:'+name,'--read-only','--tmpfs','/tmp:rw,nosuid']
    for key,value in env.items():
        command += ['-e',key+'='+value]
    return command+['--entrypoint','python',image,'-B','-m','alembic','-c','alembic.overseas.ini','upgrade',r.REVISION]


def restore_test(work, data, dumpfile, before, columns):
    name = 'hx-sku-restore-'+data['manifest'][:12]
    image = json.loads(r.run('docker', 'inspect', r.PG))[0]['Image']
    created = False
    try:
        r.run('docker', 'run', '--rm', '-d', '--network', 'none', '--name', name,
              '--mount', 'type=volume,dst=/var/lib/postgresql/data',
              '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', image)
        created = True
        deadline = time.monotonic()+45
        while True:
            try:
                r.run('docker', 'exec', name, 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres', timeout=4)
                break
            except RuntimeError:
                r.require(time.monotonic() < deadline, 'Restore database readiness timeout')
                time.sleep(0.5)
        # information_schema includes the database name; retain it inside the isolated container.
        r.run('docker', 'exec', name, 'createdb', '-h', '127.0.0.1', '-U', 'postgres', r.DB[2])
        with dumpfile.open('rb') as stream:
            result = subprocess.run(['docker', 'exec', '-i', name, 'pg_restore', '--exit-on-error',
                '--no-owner', '--no-acl', '-h', '127.0.0.1', '-U', 'postgres', '-d', r.DB[2]],
                stdin=stream, capture_output=True, timeout=120)
        r.require(result.returncode == 0, 'Isolated restore failed')
        restored = (name, 'postgres', r.DB[2])
        r.require(r.fingerprints(restored) == before, 'Restored records differ')
        r.require(r.columns(restored) == columns, 'Restored schema differs')
        r.require(r.sql(restored, 'SELECT version_num FROM overseas_alembic_version') == r.OLD_REVISION,
                  'Restored revision differs')
        r.verify_new_tables(restored, before=True)
        expected = r.migration_fingerprints(restored)
        command = isolated_command(name, data['image'])
        r.run(*command, timeout=120)
        schema = r.draft_schema(restored)
        migrated(restored, expected, schema, columns)
        first = r.fingerprints(restored)
        r.run(*command, timeout=120)
        r.require(r.fingerprints(restored) == first, 'Repeated migration changed records')
        migrated(restored, expected, schema, columns)
        r.private(work/'draft-schema.json', schema)
        r.private(work/'restore-proof.json', {'manifest':data['manifest'], 'image':data['image'],
                  'dumpSha256':r.digest(dumpfile), 'draftSchemaSha256':r.digest(work/'draft-schema.json'),
                  'restored':True, 'migration':r.REVISION, 'repeatStable':True})
    finally:
        if created:
            r.run('docker', 'rm', '-f', '-v', name)


def backup(work, data):
    closed_gate(work, data)
    r.verify_new_tables(r.DB, before=True)
    destination = work/'backup'
    destination.mkdir(mode=0o700, exist_ok=False)
    before, columns = r.fingerprints(r.DB), r.columns(r.DB)
    dumpfile = destination/'overseas.dump'
    with dumpfile.open('xb') as stream:
        result = subprocess.run(['docker', 'exec', r.PG, 'pg_dump', '-U', 'postgres', '-d', r.DB[2], '-Fc'],
                                stdout=stream, stderr=subprocess.PIPE, timeout=120)
    dumpfile.chmod(0o600)
    r.require(result.returncode == 0 and dumpfile.stat().st_size > 0, 'Database dump failed')
    r.require(r.fingerprints(r.DB) == before and r.columns(r.DB) == columns, 'Database changed during backup')
    r.private(destination/'fingerprints.json', before)
    r.private(destination/'columns.json', columns)
    r.private(destination/'expected-migration.json', r.migration_fingerprints(r.DB))
    restore_test(work, data, dumpfile, before, columns)
    closed_gate(work, data)
    r.require(r.fingerprints(r.DB) == before and r.columns(r.DB) == columns, 'Database changed during restore test')
    r.private(destination/'COMPLETE', {'dumpSha256':r.digest(dumpfile), 'manifest':data['manifest']})
    return 'BACKUP_RESTORED_AND_MIGRATION_PROVEN_IN_ISOLATION'


def backup_verified(work, data):
    dump_hash = r.digest(work/'backup/overseas.dump')
    proof = json.loads((work/'restore-proof.json').read_text())
    r.require(proof == {'manifest':data['manifest'], 'image':data['image'], 'dumpSha256':dump_hash,
              'draftSchemaSha256':r.digest(work/'draft-schema.json'),
              'restored':True, 'migration':r.REVISION, 'repeatStable':True},
              'Restore proof mismatch')
    r.require(json.loads((work/'backup/COMPLETE').read_text()) ==
              {'dumpSha256':dump_hash, 'manifest':data['manifest']}, 'Backup incomplete')
    r.require(r.fingerprints(r.DB) == json.loads((work/'backup/fingerprints.json').read_text()),
              'Database changed since backup')
    r.require(r.columns(r.DB) == (work/'backup/columns.json').read_text(), 'Schema changed since backup')


def verify_migration(work, data):
    expected = json.loads((work/'backup/expected-migration.json').read_text())
    proof = json.loads((work/'restore-proof.json').read_text())
    r.require(proof['draftSchemaSha256'] == r.digest(work/'draft-schema.json'), 'Draft schema proof drift')
    schema = json.loads((work/'draft-schema.json').read_text())
    migrated(r.DB, expected, schema, (work/'backup/columns.json').read_text())
    r.private(work/'MIGRATION_VERIFIED', {'manifest':data['manifest'], 'revision':r.REVISION})


def migrate(work, data):
    closed_gate(work,data)
    backup_verified(work,data)
    r.require(not (work/'MIGRATION_STARTED').exists(), 'Inspect previous migration attempt; forward repair only')
    overlay = work/'migration-overlay.json'
    r.private(overlay, {'services':{'migrate':{'image':data['image']}}})
    original = json.loads(r.a.compose(data['compose'],'config','--format','json'))
    actual = json.loads(r.a.compose(data['compose'],'config','--format','json',overlay=overlay))
    original['services']['migrate']['image'] = data['image']
    r.require(actual == original, 'Migration overlay changes unrelated settings')
    r.private(work/'MIGRATION_STARTED', {'manifest':data['manifest'], 'image':data['image']})
    r.a.compose(data['compose'],'run','--rm','--no-deps','--pull','never','migrate',
                'alembic','-c','alembic.overseas.ini','upgrade',r.REVISION,overlay=overlay)
    verify_migration(work,data)
    return 'OVERSEAS_0026_MIGRATED_EXISTING_DATA_PRESERVED'
