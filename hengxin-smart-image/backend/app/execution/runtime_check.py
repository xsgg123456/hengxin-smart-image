"""Non-billing service preflight: exercise actual CLI command sandbox before consuming jobs."""
import json
import subprocess
import tempfile
from uuid import uuid4

from app.core.config import get_settings
from app.execution.workspace import prepare_workspace, sandbox_command


CHECK = """
import json, pathlib, shutil, subprocess
from PIL import Image
from docx import Document
from openpyxl import Workbook
from pypdf import PdfReader
names=['bwrap','python3','python','node','rg','git','curl','unzip','zip','libreoffice','pdftoppm','pdftotext']
missing=[name for name in names if shutil.which(name) is None]
assert not missing, 'Runtime tools missing: '+','.join(missing)
p=pathlib.Path('/work/preflight.txt'); p.write_text('RUNTIME_READY')
assert p.read_text()=='RUNTIME_READY'
subprocess.run(['node','-e','process.stdout.write("NODE_READY")'],check=True,capture_output=True,timeout=10)
assert not pathlib.Path('/var/run/docker.sock').exists()
d=Document(); d.add_paragraph('RENDER_READY'); d.save('/work/preflight.docx')
subprocess.run(['libreoffice','--headless','--convert-to','pdf','--outdir','/work',
                '/work/preflight.docx'],check=True,capture_output=True,timeout=25)
assert len(PdfReader('/work/preflight.pdf').pages)==1
print(json.dumps({'ready':True}))
"""


def main():
    settings = get_settings()
    with tempfile.TemporaryDirectory(prefix='hx-executor-preflight-') as root:
        ws = prepare_workspace(root, uuid4(), uuid4(), None, copy_auth=False)
        ws.use_skill = False
        command = sandbox_command(ws, settings.codex_binary,
            ['sandbox', '-c', 'sandbox_mode="workspace-write"', '--', 'python3', '-c', CHECK],
            settings.codex_bwrap_binary)
        result = subprocess.run(command, capture_output=True, text=True, timeout=45)
        if result.returncode or result.stdout.strip() != '{"ready": true}':
            # Dependency diagnostics cannot include the worker environment or credentials.
            raise RuntimeError('Codex runtime preflight failed; run infra/verify_codex_runtime.py')
    print('Codex command sandbox and runtime dependencies ready')


if __name__ == '__main__':
    main()
