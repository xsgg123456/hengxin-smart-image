"""Verified immutable backup at schema 0026; deliberately has no migration command."""
import importlib.util
import json
from pathlib import Path
import subprocess
import time

spec = importlib.util.spec_from_file_location('polling_runtime', Path(__file__).with_name('polling-runtime.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
r = p.runtime


def schema(database):
    # SKU columns() protects old tables; draft_schema() additionally protects all three existing draft tables.
    return {'existing':r.columns(database), 'drafts':r.draft_schema(database)}


def closed_gate(work, data):
    live = r.inspect()
    r.require(live['Id'] == data['oldId'] and not live['State']['Running'], 'Original API must remain stopped')
    gate = json.loads((work/'gate.json').read_text())
    r.require(gate['manifest'] == data['manifest'] and gate['phase'] == 'api-stopped-consumer-paused', 'Gate mismatch')
    r.helper('sku-native').stopped()
    r.require(r.sql(r.DB, 'SELECT version_num FROM overseas_alembic_version') == r.REVISION, 'Schema drift')
    r.require(r.sql(r.DB, "SELECT count(*) FROM overseas_draft_imports WHERE state IN ('queued','running')") == '0',
              'Draft import drain incomplete')


def restore_test(work, data, dumpfile, before, expected_schema):
    name = 'hx-polling-restore-'+data['manifest'][:12]
    image = json.loads(r.run('docker', 'inspect', r.PG))[0]['Image']
    created = False
    try:
        r.run('docker', 'run', '--rm', '-d', '--network', 'none', '--name', name,
              '--mount', 'type=volume,dst=/var/lib/postgresql/data', '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', image)
        created = True
        deadline = time.monotonic()+45
        while True:
            remaining = deadline-time.monotonic()
            r.require(remaining > 0, 'Restore database readiness timeout')
            try:
                r.run('docker', 'exec', name, 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres', timeout=min(4, remaining))
                break
            except RuntimeError:
                time.sleep(min(0.5, max(0, deadline-time.monotonic())))
        r.run('docker', 'exec', name, 'createdb', '-h', '127.0.0.1', '-U', 'postgres', r.DB[2])
        with dumpfile.open('rb') as stream:
            result = subprocess.run(['docker', 'exec', '-i', name, 'pg_restore', '--exit-on-error', '--no-owner',
                '--no-acl', '-h', '127.0.0.1', '-U', 'postgres', '-d', r.DB[2]], stdin=stream,
                capture_output=True, timeout=120)
        r.require(result.returncode == 0, 'Isolated restore failed')
        restored = (name, 'postgres', r.DB[2])
        r.require(r.fingerprints(restored) == before, 'Restored records differ')
        r.require(schema(restored) == expected_schema, 'Restored schema differs')
        r.require(r.sql(restored, 'SELECT version_num FROM overseas_alembic_version') == r.REVISION, 'Restored revision differs')
        r.private(work/'restore-proof.json', {'manifest':data['manifest'], 'image':data['image'],
            'dumpSha256':r.digest(dumpfile), 'schemaSha256':r.digest(work/'backup/schema.json'), 'restored':True,
            'revision':r.REVISION, 'migration':False})
    finally:
        if created:
            r.run('docker', 'rm', '-f', '-v', name)  # Only the uniquely named isolated test container.


def backup(work, data):
    closed_gate(work, data)
    destination = work/'backup'
    destination.mkdir(mode=0o700, exist_ok=False)
    before, expected_schema = r.fingerprints(r.DB), schema(r.DB)
    dumpfile = destination/'overseas.dump'
    with dumpfile.open('xb') as stream:
        result = subprocess.run(['docker', 'exec', r.PG, 'pg_dump', '-U', 'postgres', '-d', r.DB[2], '-Fc'],
                                stdout=stream, stderr=subprocess.PIPE, timeout=120)
    dumpfile.chmod(0o600)
    r.require(result.returncode == 0 and dumpfile.stat().st_size > 0, 'Database dump failed')
    r.private(destination/'fingerprints.json', before)
    r.private(destination/'schema.json', expected_schema)
    restore_test(work, data, dumpfile, before, expected_schema)
    closed_gate(work, data)
    r.require(r.fingerprints(r.DB) == before and schema(r.DB) == expected_schema, 'Database changed during backup')
    r.private(destination/'COMPLETE', {'dumpSha256':r.digest(dumpfile), 'manifest':data['manifest']})
    return 'SCHEMA_0026_BACKUP_RESTORED_WITHOUT_MIGRATION'


def backup_verified(work, data):
    dump_hash = r.digest(work/'backup/overseas.dump')
    r.require(json.loads((work/'restore-proof.json').read_text()) == {
        'manifest':data['manifest'], 'image':data['image'], 'dumpSha256':dump_hash,
        'schemaSha256':r.digest(work/'backup/schema.json'), 'restored':True, 'revision':r.REVISION,
        'migration':False}, 'Restore proof mismatch')
    r.require(json.loads((work/'backup/COMPLETE').read_text()) ==
              {'dumpSha256':dump_hash, 'manifest':data['manifest']}, 'Backup incomplete')
    r.require(r.fingerprints(r.DB) == json.loads((work/'backup/fingerprints.json').read_text()), 'Database changed since backup')
    r.require(schema(r.DB) == json.loads((work/'backup/schema.json').read_text()), 'Schema changed since backup')
