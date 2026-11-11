"""Run as the real non-root worker UID: exercise both sandbox layers without a model."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4


PROBE = r'''
import json, pathlib, subprocess, shutil, zipfile, re, xml.etree.ElementTree as ET
from PIL import Image
from docx import Document
from openpyxl import Workbook, load_workbook
from pypdf import PdfReader
root=pathlib.Path('/work')
report={}
for name in ['bwrap','python3','python','node','rg','git','curl','unzip','zip','libreoffice','pdftoppm','pdftotext']:
 assert shutil.which(name), name+' missing'
report['executables']=True
for path in ['/var/run/docker.sock','/etc/hengxin-lan','/home/codex/account-management',
             '/var/lib/hengxin-overseas/execution','/opt/hengxin-smart-image/infra/runtime/execution']:
 assert not pathlib.Path(path).exists(), 'host data exposed: '+path
for path in ['/usr/hx-runtime-test','/etc/hosts']:
 try:
  with open(path,'ab'): pass
 except OSError: pass
 else: raise AssertionError('system writable: '+path)
report['isolation']=True
(root/'own.txt').write_text('PRIVATE_WORKSPACE')
subprocess.run(['node','-e',"require('fs').writeFileSync('/work/node.txt','NODE_OK')"],check=True,timeout=15)
assert (root/'node.txt').read_text()=='NODE_OK'
report['python_node_write']=True
for fmt in ['PNG','JPEG','WEBP']:
 path=root/('image.'+fmt.lower())
 Image.new('RGB',(32,24),(15,90,160)).save(path,fmt)
 with Image.open(path) as im: assert im.size==(32,24)
report['image_formats']=['PNG','JPEG','WEBP']
d=Document(); d.add_paragraph('DOCX_READ_OK'); d.save(root/'sample.docx')
assert Document(root/'sample.docx').paragraphs[0].text=='DOCX_READ_OK'
wb=Workbook(); wb.active['A1']='XLSX_READ_OK'; wb.save(root/'sample.xlsx')
assert load_workbook(root/'sample.xlsx').active['A1'].value=='XLSX_READ_OK'
report['docx_xlsx']=True
for name in ['sample.docx','sample.xlsx']:
 subprocess.run(['libreoffice','--headless','--convert-to','pdf','--outdir','/work',str(root/name)],
                check=True,capture_output=True,timeout=90)
 assert PdfReader(root/'sample.pdf').pages
 (root/'sample.pdf').unlink()
report['docx_xlsx_render']=True
(root/'invalid.pptx').write_bytes(b'not a powerpoint file')
bad=subprocess.run(['libreoffice','--headless','--convert-to','pdf','--outdir','/work',
                    '/work/invalid.pptx'],capture_output=True,timeout=90)
assert bad.returncode!=0 and not (root/'invalid.pdf').exists()
assert not list(root.glob('.office-*'))
report['invalid_document_rejected']=True
ppt=root/'sample.pptx'
if ppt.exists():
 with zipfile.ZipFile(ppt) as z:
  assert z.testzip() is None
  slides=[n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)]
  media=[n for n in z.namelist() if n.startswith('ppt/media/') and not n.endswith('/')]
  texts=[''.join(ET.fromstring(z.read(n)).itertext()) for n in slides]
  for n in media:
   from io import BytesIO
   with Image.open(BytesIO(z.read(n))) as im: im.load()
  report['ppt']={'slides':len(slides),'media':len(media),'text_characters':sum(map(len,texts))}
 r=subprocess.run(['libreoffice','-env:UserInstallation=file:///tmp/hx-lo-profile',
   '--headless','--convert-to','pdf','--outdir','/work',str(ppt)],capture_output=True,text=True,timeout=90)
 assert r.returncode==0 and (root/'sample.pdf').is_file(), (r.returncode,r.stderr,r.stdout)
 pdf=PdfReader(root/'sample.pdf'); assert len(pdf.pages)==len(slides)
 subprocess.run(['pdftoppm','-scale-to','1400','-png',str(root/'sample.pdf'),'/work/slide'],
                check=True,capture_output=True,timeout=60)
 pages=sorted(root.glob('slide-*.png')); assert len(pages)==len(slides)
 for p in pages:
  with Image.open(p) as im: im.load(); assert min(im.size)>300
 subprocess.run(['pdftotext',str(root/'sample.pdf'),'/work/slide-text.txt'],check=True,timeout=20)
 assert (root/'slide-text.txt').read_text().strip()
 report['ppt']['rendered_pages']=len(pages)
report['passed']=True
(root/'probe-result.json').write_text(json.dumps(report))
print(json.dumps(report))
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace-module', required=True)
    p.add_argument('--binary', required=True)
    p.add_argument('--bwrap', default='/opt/hengxin-runtime/bwrap')
    p.add_argument('--pptx')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    if sys.platform != 'linux' or os.geteuid() == 0:
        raise RuntimeError('Use the actual non-root worker identity')
    spec = importlib.util.spec_from_file_location('runtime_workspace', args.workspace_module)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    output = Path(args.output)
    output.mkdir(mode=0o700)  # Refuse overwriting earlier evidence.
    with tempfile.TemporaryDirectory(prefix='hx-runtime-check-') as temporary:
        ws = module.prepare_workspace(temporary, uuid4(), uuid4(), None, copy_auth=False)
        ws.use_skill = False
        (ws.work / 'probe.py').write_text(PROBE)
        if args.pptx:
            shutil.copyfile(args.pptx, ws.work / 'sample.pptx')
        argv = module.sandbox_command(ws, args.binary,
            ['sandbox', '-c', 'sandbox_mode="workspace-write"', '--', 'python3', '/work/probe.py'], args.bwrap)
        result = subprocess.run(argv, capture_output=True, text=True, timeout=300)
        (output / 'stdout.txt').write_text(result.stdout)
        (output / 'stderr.txt').write_text(result.stderr)
        if result.returncode or not (ws.work / 'probe-result.json').exists():
            raise RuntimeError('Actual nested sandbox probe failed; inspect private output')
        report = json.loads((ws.work / 'probe-result.json').read_text())
        assert report['passed'] and report['isolation']
        report['uid'] = os.geteuid()
        report['workspace_module'] = args.workspace_module
        for file in ws.work.glob('slide-*.png'):
            shutil.copyfile(file, output / file.name)
        (output / 'report.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
