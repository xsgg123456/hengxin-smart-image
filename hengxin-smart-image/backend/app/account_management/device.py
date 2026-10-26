"""Official CLI device login in a disposable home; never expose raw CLI output."""
import os
import re
import subprocess
import time
from pathlib import Path

from app.execution.process import stop_process
from app.execution.managed_credentials_files import directory

VERIFICATION_URL = 'https://auth.openai.com/codex/device'


def device_login(home, binary, cancelled, publish_code, expires):
    home = Path(home)
    config = home / '.codex'
    with directory(config, create=True) as folder:
        folder.write('config.toml', b'cli_auth_credentials_store = "file"\n')
    env = {'HOME': str(home), 'CODEX_HOME': str(config), 'PATH': '/usr/bin:/bin',
           'LANG': 'C.UTF-8', 'NO_COLOR': '1', 'TERM': 'dumb'}
    logfile = home / 'login.log'
    with logfile.open('xb') as log:
        os.chmod(logfile, 0o600)
        process = subprocess.Popen([binary, 'login', '--device-auth'], cwd=home, env=env,
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True, close_fds=True)
        try:
            while process.poll() is None:
                if cancelled() or time.time() >= expires or logfile.stat().st_size > 65536:
                    return False
                text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', logfile.read_text(errors='replace'))
                if VERIFICATION_URL in text:
                    codes = re.findall(r'\b[A-Z0-9]{4,5}-[A-Z0-9]{4,5}\b', text)
                    if codes:
                        publish_code(codes[-1])
                time.sleep(.25)
            return process.returncode == 0 and not cancelled() and time.time() < expires
        finally:
            stop_process(process)
