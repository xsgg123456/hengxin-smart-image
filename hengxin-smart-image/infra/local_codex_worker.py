"""WSL worker entry point: explicit local configuration, no credential output."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote

from dotenv import dotenv_values


def configuration(env_file, local_file):
    base = dotenv_values(env_file, interpolate=False)
    local = dotenv_values(local_file, interpolate=False)
    if base.get('APP_ENV') not in ('test', 'development'):
        raise ValueError('Local CLI requires an explicit non-production environment')
    binary = local['LOCAL_CODEX_BINARY']
    values = dict(base)
    values.update(
        ENABLE_FIXTURE_EXECUTOR='false', ENABLE_CODEX_EXECUTOR='true',
        CODEX_BINARY=binary, CODEX_AUTH_FILE=local['LOCAL_CODEX_AUTH_FILE'],
        CODEX_BWRAP_BINARY=local['LOCAL_CODEX_BWRAP'],
        CODEX_EXECUTION_ROOT=local['LOCAL_CODEX_EXECUTION_ROOT'],
        SKILL_INSTALL_ROOT=local['LOCAL_CODEX_SKILL_ROOT'],
        WORKER_NODE_NAME=local['LOCAL_CODEX_NODE'],
        HENGXIN_CODEX_PROXY_URL=local.get('LOCAL_CODEX_PROXY_URL') or '',
        DATABASE_URL='postgresql+psycopg://hengxin:'+quote(base['POSTGRES_PASSWORD'], safe='')+
                     '@127.0.0.1:'+base.get('POSTGRES_PORT','55433')+'/hengxin',
        REDIS_URL='redis://127.0.0.1:'+local['LOCAL_CODEX_REDIS_PORT']+'/0',
        MINIO_ENDPOINT='127.0.0.1:'+base.get('MINIO_PORT','59002'),
        MINIO_SECURE='false',
    )
    values['GENERATION_CONCURRENCY'] = base.get('GENERATION_CONCURRENCY', '1')
    return {k:v for k,v in values.items() if v is not None}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['check','serve'])
    parser.add_argument('--env-file',required=True)
    parser.add_argument('--local-file',required=True)
    args=parser.parse_args()
    if sys.platform!='linux' or os.getuid()==0:
        raise ValueError('Run this worker as a non-root Linux user')
    backend=Path(__file__).resolve().parents[1]/'backend'
    os.chdir(backend)
    sys.path.insert(0,str(backend))
    values=configuration(args.env_file,args.local_file)
    os.environ.update(values)
    from app.core.config import get_settings
    settings=get_settings()
    binary=Path(settings.codex_binary)
    for p in (binary,binary.parent/'codex-code-mode-host',Path(settings.codex_bwrap_binary),Path(settings.codex_auth_file)):
        if not p.is_file():
            raise ValueError('Missing local runtime file: '+str(p))
    version=subprocess.run([str(binary),'--version'],capture_output=True,text=True,timeout=10)
    if version.returncode or version.stdout.strip()!=f'codex-cli {settings.codex_version}':
        raise ValueError('CLI version does not match the validated project version')
    auth_env=dict(os.environ,CODEX_HOME=str(Path(settings.codex_auth_file).parent))
    result=subprocess.run([str(binary),'login','status'],env=auth_env,capture_output=True,timeout=15)
    if result.returncode:
        raise ValueError('CLI authentication unavailable; sign in before starting')
    if args.action=='check':
        import tempfile
        from uuid import uuid4
        from app.execution.workspace import prepare_workspace,sandbox_command
        with tempfile.TemporaryDirectory(prefix='hx-preflight-') as root:
            ws=prepare_workspace(root,uuid4(),uuid4(),settings.codex_auth_file)
            result=subprocess.run(sandbox_command(ws,str(binary),['--version'],settings.codex_bwrap_binary),capture_output=True,text=True,timeout=15)
            if result.returncode or result.stdout.strip()!=version.stdout.strip():
                raise ValueError('Actual CLI sandbox preflight failed')
        print('PASS pinned CLI, authentication and actual task sandbox')
        return
    from app.worker.celery_app import celery_app
    celery_app.worker_main(['worker','--concurrency='+str(settings.generation_concurrency),
                           '--hostname='+settings.worker_node_name+'@%h','--loglevel=INFO'])


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        # Settings/connection exceptions can contain credential-bearing URLs.
        print('Local worker failed: '+type(error).__name__+'; verify runtime and local configuration',file=sys.stderr)
        sys.exit(1)
