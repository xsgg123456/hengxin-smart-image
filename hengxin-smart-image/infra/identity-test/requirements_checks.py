"""Real identity/HTTP/MinIO requirements gate; no workers or provider calls."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from io import BytesIO
import json
from pathlib import Path
import time
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile
from openpyxl import Workbook
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from sqlalchemy import text
from phase19_fixtures import prepare, domestic_snapshot
from phase20_checks import storage


def documents():
    writer = PdfWriter()
    for number in range(1, 4):
        page = writer.add_blank_page(width=595, height=842)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
            DictionaryObject({NameObject('/F1'): font})})
        stream = DecodedStreamObject()
        stream.set_data(f'BT /F1 22 Tf 50 760 Td (Hengxin Requirements - Page {number}) Tj '
                        f'0 -50 Td /F1 14 Tf (SKU HX-USB-C: clear product, white background.) Tj ET'.encode())
        page[NameObject('/Contents')] = writer._add_object(stream)
    pdf = BytesIO()
    writer.write(pdf)
    docx = BytesIO()
    with ZipFile(docx, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<?xml version="1.0"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>')
        archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>')
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>海外商品图需：展示产品接口及配件。</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>&lt;script&gt;禁止执行上传内容&lt;/script&gt;</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>市场：美国；平台：Amazon；SKU：HX-USB-C。</w:t></w:r></w:p></w:body></w:document>')
    book = Workbook()
    book.active.title = '竞品分析'
    for row in [('商品', '卖点', '价格'), ('USB-C Charger', 'Compact fast charging', 29.9),
                ('HX-USB-C', 'Clear connector details', 25.5)]:
        book.active.append(row)
    xlsx = BytesIO()
    book.save(xlsx)
    return {'图需原件.pdf': ('requirement', pdf.getvalue()),
            '修订图需.docx': ('requirement', docx.getvalue()),
            '竞品分析.xlsx': ('competitor', xlsx.getvalue()),
            '竞品更新.csv': ('competitor', '商品,卖点\nHX-USB-C,紧凑快充\n'.encode())}


def run(h, fixtures):
    ids = prepare(h, fixtures)
    for kind in ('domestic', 'overseas'):
        store = storage(kind)
        for attempt in range(30):
            try:
                if not store.bucket_exists(kind + '-test'):
                    store.make_bucket(kind + '-test')
                break
            except Exception:
                if attempt == 29:
                    raise
                time.sleep(.2)
    domestic_before = domestic_snapshot(h)
    base = h.BUSINESS['overseas'][0] + '/api/overseas/v1'
    files = documents()
    folder = Path('/tmp/requirements-fixtures')
    folder.mkdir(exist_ok=True)
    for name, (_, data) in files.items():
        (folder / name).write_bytes(data)
    with ExitStack() as stack:
        clients = {}
        for code in ('p18-operator', 'p19-operator2', 'p18-designer', 'p19-designer2', 'p18-admin'):
            clients[code] = stack.enter_context(h.login(code))
            h.exchange(clients[code], 'overseas')
        operator, outsider, designer, other_design, admin = clients.values()

        def upload(name):
            kind, data = files[name]
            response = h.expect(operator.post(base + '/materials', params={'kind': kind},
                files={'file': (name, data, 'application/octet-stream')}, timeout=40), 201).json()
            assert response['status'] == 'ready', response
            content = h.expect(operator.get(base + '/materials/' + response['id'] + '/content'), 200)
            assert content.content == data
            assert 'filename*=' in content.headers['content-disposition']
            return response

        def create(name, names=('图需原件.pdf', '竞品分析.xlsx')):
            materials = [upload(filename) for filename in names]
            body = dict(name=name, productName='USB-C 充电器', brand='HX', platform='Amazon',
                market='美国', remarks='保留完整产品，清晰展示接口', skus=[{'code': 'HX-USB-C'}],
                designerId=ids['p18-designer'], materialIds=[item['id'] for item in materials])
            result = h.expect(operator.post(base + '/tasks', json=body,
                headers={'Idempotency-Key': str(uuid4())}), 201).json()
            assert result['status'] == 'pending_review'
            return result, body, materials

        def post(client, task, suffix, body, key=None, status=200):
            return h.expect(client.post(base + '/tasks/' + task['id'] + suffix, json=body,
                headers={'Idempotency-Key': key or str(uuid4())}), status)

        task, body, materials = create('真实HTTP：退回修改与审核通过')
        request = {'decision': 'approve', 'comment': '', 'version': task['version']}
        for client in (operator, outsider, other_design, admin):
            post(client, task, '/requirements-review', request, status=403)
        post(designer, task, '/analysis', {'version': 1}, status=409)
        with h.ENGINES['overseas'].connect() as connection:
            assert connection.execute(text('SELECT count(*) FROM overseas_jobs')).scalar_one() == 0
        post(designer, task, '/requirements-review', {**request, 'decision': 'reject'}, status=422)
        rejected = post(designer, task, '/requirements-review',
            {**request, 'decision': 'reject', 'comment': '补充新版图需，保留竞品资料'}).json()
        assert rejected['status'] == 'returned'
        replacement = upload('修订图需.docx')
        resubmission = {**body, 'name': '真实HTTP：已修订图需', 'version': rejected['version'],
            'materialIds': [replacement['id'], materials[1]['id']]}
        post(outsider, task, '/resubmit', resubmission, status=403)
        resubmitted = post(operator, task, '/resubmit', resubmission, 'resubmit').json()
        assert post(operator, task, '/resubmit', resubmission, 'resubmit').json() == resubmitted
        assert resubmitted['status'] == 'pending_review'
        original = base + '/materials/' + materials[0]['id'] + '/content'
        assert h.expect(designer.get(original), 200).content == files['图需原件.pdf'][1]
        h.expect(other_design.get(original), 403)
        h.expect(outsider.get(original), 403)
        decision = {'decision': 'approve', 'comment': '图需完整', 'version': resubmitted['version']}
        def concurrent(_):
            return post(designer, task, '/requirements-review', decision, 'approve-once').json()
        with ThreadPoolExecutor(2) as pool:
            decisions = list(pool.map(concurrent, (1, 2)))
        assert decisions[0] == decisions[1] and decisions[0]['status'] == 'analyzing'
        with h.ENGINES['overseas'].connect() as connection:
            jobs = connection.execute(text('SELECT status,payload FROM overseas_jobs')).all()
            assert len(jobs) == 1 and jobs[0].status == 'queued'
            assert {item['id'] for item in jobs[0].payload['materials']} == set(resubmission['materialIds'])
            assert connection.execute(text('SELECT count(*) FROM overseas_job_outbox')).scalar_one() == 1
        preview_pdf, _, _ = create('待审核：PDF分页与竞品表格')
        preview_word, _, _ = create('待审核：Word安全阅读', ('修订图需.docx', '竞品更新.csv'))
        returned, _, _ = create('退回运营：可修改并重新提交')
        post(designer, returned, '/requirements-review',
            {'decision': 'reject', 'comment': '请补全SKU及图需文档', 'version': returned['version']})
        print('REQUIREMENTS_FIXTURES ' + json.dumps({'pdfTask': preview_pdf['id'], 'wordTask': preview_word['id'],
            'returnedTask': returned['id'], 'approvedTask': task['id'], 'designerId': ids['p18-designer']}, ensure_ascii=False), flush=True)
    assert domestic_snapshot(h) == domestic_before
    print('PASS real PDF/DOCX/XLSX/CSV original bytes; pending no AI; roles; reject/resubmit; '
          'concurrent idempotent approval one queued job; old evidence authorization; domestic unchanged', flush=True)
    print('READY requirements browser codes: p18-operator p18-designer p18-design_manager p18-admin', flush=True)
