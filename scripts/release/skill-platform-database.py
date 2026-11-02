"""Private overseas dump, isolated restore and additive migration proof."""
import importlib.util
import json
from pathlib import Path
import subprocess
import time

spec = importlib.util.spec_from_file_location('platform_runtime', Path(__file__).with_name('skill-platform-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def closed_gate(work,data):
    r.require(not r.inspect()['State']['Running'],'API must remain stopped during migration')
    gate = json.loads((work/'gate.json').read_text())
    r.require(gate['manifest'] == data['manifest'] and gate['phase'] == 'api-stopped-consumer-paused','Gate proof mismatch')
    r.worker('paused',gate['node'])


def restore_test(work, data, dumpfile, before):
    name = 'hx-platform-restore-' + data['manifest'][:12]
    image = json.loads(r.run('docker','inspect',r.PG))[0]['Image']
    created = False
    try:
        r.run('docker','run','--rm','-d','--network','none','--name',name,
              '--mount','type=volume,dst=/var/lib/postgresql/data',
              '-e','POSTGRES_HOST_AUTH_METHOD=trust',image)
        created = True
        deadline = time.monotonic()+45
        while True:
            try:
                r.run('docker','exec',name,'pg_isready','-U','postgres',timeout=4)
                break
            except RuntimeError:
                r.require(time.monotonic()<deadline,'Restore database readiness timeout')
                time.sleep(0.5)
        with dumpfile.open('rb') as stream:
            result = subprocess.run(['docker','exec','-i',name,'pg_restore','--exit-on-error',
                '--no-owner','--no-acl','-U','postgres','-d','postgres'],stdin=stream,capture_output=True,timeout=120)
        r.require(result.returncode == 0,'Isolated restore failed; inspect private evidence')
        db = (name,'postgres','postgres')
        r.require(r.fingerprints(db) == before,'Restored backup differs')
        old_columns = r.columns(db)
        env = {'HX_BUSINESS_CONTEXT':'overseas','OVERSEAS_DATABASE_URL':'postgresql+psycopg://postgres@127.0.0.1/postgres',
               'OVERSEAS_REDIS_URL':'redis://127.0.0.1:6379/0','OVERSEAS_MINIO_ENDPOINT':'127.0.0.1:9000',
               'OVERSEAS_MINIO_ACCESS_KEY':'isolated','OVERSEAS_MINIO_SECRET_KEY':'isolated',
               'OVERSEAS_MINIO_BUCKET':'isolated','OVERSEAS_CODEX_EXECUTION_ROOT':'/tmp/execution',
               'OVERSEAS_SKILL_INSTALL_ROOT':'/tmp/install','OVERSEAS_LOCAL_SKILL_ROOT':'/tmp/skills'}
        command = ['docker','run','--rm','--network','container:'+name,'--read-only','--tmpfs','/tmp:rw,nosuid']
        for key,value in env.items():
            command += ['-e',key+'='+value]
        command += ['--entrypoint','python',data['image'],'-B','-m','alembic','-c','alembic.overseas.ini','upgrade',r.REVISION]
        r.run(*command,timeout=120)
        r.require(r.sql(db,'SELECT version_num FROM overseas_alembic_version') == r.REVISION,'Restored migration revision')
        r.preserved(before,r.fingerprints(db))
        r.require(r.columns(db) == old_columns,'Existing schema columns changed')
        r.platform_seed(db,Path(data['source']),before)
        r.require(r.sql(db,"SELECT count(*) FROM overseas_installed_skill_availability WHERE platforms IS NULL") == '0',
                  'Null platform associations')
        migrated = r.fingerprints(db)
        r.run(*command,timeout=120)
        r.require(r.fingerprints(db) == migrated,'Repeated migration changed records')
        r.private(work/'restore-proof.json',{'manifest':data['manifest'],'image':data['image'],
            'dumpSha256':r.digest(dumpfile),'restored':True,'existingRowsPreserved':True,'repeatStable':True})
    finally:
        if created:
            r.run('docker','rm','-f','-v',name)


def backup(work,data):
    closed_gate(work,data)
    destination = work/'backup'
    destination.mkdir(mode=0o700,exist_ok=False)
    before = r.fingerprints(r.DB)
    r.private(destination/'columns.json',r.columns(r.DB))
    dumpfile = destination/'overseas.dump'
    with dumpfile.open('xb') as stream:
        result = subprocess.run(['docker','exec',r.PG,'pg_dump','-U','postgres','-d',r.DB[2],'-Fc'],
                                stdout=stream,stderr=subprocess.PIPE,timeout=120)
    dumpfile.chmod(0o600)
    r.require(result.returncode == 0 and dumpfile.stat().st_size>0,'Database dump failed')
    r.require(r.fingerprints(r.DB) == before,'Database changed during backup; no migration permitted')
    r.private(destination/'fingerprints.json',before)
    restore_test(work,data,dumpfile,before)
    r.require(r.fingerprints(r.DB) == before,'Database changed during isolated validation')
    r.private(destination/'COMPLETE',{'dumpSha256':r.digest(dumpfile),'manifest':data['manifest']})


def migrate(work,data):
    closed_gate(work,data)
    before = json.loads((work/'backup/fingerprints.json').read_text())
    proof = json.loads((work/'restore-proof.json').read_text())
    r.require(proof['manifest'] == data['manifest'] and proof['image'] == data['image'] and
              proof['dumpSha256'] == r.digest(work/'backup/overseas.dump'),'Restore proof drift')
    r.require((work/'backup/COMPLETE').is_file(),'Backup incomplete')
    r.require(r.fingerprints(r.DB) == before,'Database changed since backup')
    r.require(r.sql(r.DB,'SELECT version_num FROM overseas_alembic_version') == 'overseas_0022','Schema baseline drift')
    overlay = work/'migration-overlay.json'
    r.private(overlay,{'services':{'migrate':{'image':data['image']}}})
    original = json.loads(r.a.compose(data['compose'],'config','--format','json'))
    actual = json.loads(r.a.compose(data['compose'],'config','--format','json',overlay=overlay))
    original['services']['migrate']['image'] = data['image']
    r.require(actual == original,'Migration overlay scope drift')
    r.private(work/'MIGRATION_STARTED','Forward only. Never restore or downgrade the live database.')
    r.a.compose(data['compose'],'run','--rm','--no-deps','--pull','never','migrate',
                'alembic','-c','alembic.overseas.ini','upgrade',r.REVISION,overlay=overlay)
    r.require(r.sql(r.DB,'SELECT version_num FROM overseas_alembic_version') == r.REVISION,'Migration revision mismatch')
    r.preserved(before,r.fingerprints(r.DB))
    r.require(r.columns(r.DB) == (work/'backup/columns.json').read_text(),'Existing schema columns changed')
    r.platform_seed(r.DB,Path(data['source']),before)
    r.private(work/'MIGRATION_VERIFIED',{'manifest':data['manifest'],'revision':r.REVISION})
