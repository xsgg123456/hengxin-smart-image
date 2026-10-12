import base64
import io
import json
import os
import subprocess
import sys
import zlib
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi import HTTPException
from openpyxl import Workbook
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from app.overseas.materials import parsers
from app.overseas.materials.document_formats import DocumentError, TextCollector


def pdf(text=None, encrypted=False, pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(width=300, height=300)
        if text:
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                     NameObject('/Subtype'): NameObject('/Type1'),
                                     NameObject('/BaseFont'): NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
                DictionaryObject({NameObject('/F1'): font})})
            stream = DecodedStreamObject()
            stream.set_data(f'BT /F1 12 Tf 10 250 Td ({text}) Tj ET'.encode())
            page[NameObject('/Contents')] = writer._add_object(stream)
    if encrypted:
        writer.encrypt('password')
    result = io.BytesIO()
    writer.write(result)
    return result.getvalue()


def docx(body='<w:p><w:r><w:t>图需 A</w:t></w:r></w:p>', extra=None):
    result = io.BytesIO()
    with ZipFile(result, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr('word/document.xml',
            '<w:document xmlns:w="http://schemas.openxmlformats.org/'
            'wordprocessingml/2006/main"><w:body>' + body + '</w:body></w:document>')
        for name, value in (extra or {}).items():
            archive.writestr(name, value)
    return result.getvalue()


def xlsx(rows):
    book = Workbook()
    for row in rows:
        book.active.append(row)
    result = io.BytesIO()
    book.save(result)
    return result.getvalue()


@pytest.mark.parametrize('filename,kind,data,message', [
    ('a.doc', 'requirement', b'x', 'DOC'),
    ('a.pdf', 'competitor', b'%PDF-', '类型不匹配'),
    ('a.xlsx', 'competitor', b'not zip', '扩展名'),
    ('a.csv', 'competitor', b'a\x00b', '文本文件'),
    ('a.pdf', 'requirement', b'', '不能为空'),
])
def test_upload_rejects_invalid(filename, kind, data, message):
    with pytest.raises(HTTPException, match=message) as error:
        parsers.validate_document(data, filename, kind)
    assert error.value.status_code == 422


def test_upload_size_and_filename():
    with pytest.raises(HTTPException) as error:
        parsers.validate_document(b'a' * (parsers.MAX_DOCUMENT_BYTES + 1), 'a.csv', 'competitor')
    assert error.value.status_code == 413
    name, content_type = parsers.validate_document(b'a,b', '..\\<bad>\r.csv', 'competitor')
    assert name == '_bad__.csv'
    assert content_type == 'text/csv'


def test_pdf_extract_and_broken_original_retained():
    assert 'Actual requirements' in parsers.parse_document(pdf('Actual requirements'), 'a.pdf')
    assert parsers.validate_document(b'%PDF-broken', 'a.pdf', 'requirement')[0] == 'a.pdf'
    with pytest.raises(parsers.ParseError, match='损坏'):
        parsers.parse_document(b'%PDF-broken', 'a.pdf')


@pytest.mark.parametrize('data,message', [(pdf(), '没有可读取'),
    (pdf('secret', encrypted=True), '加密'), (pdf(pages=301), '300 页')], ids=['scanned', 'encrypted', 'too-many-pages'])
def test_pdf_failure_modes(data, message):
    with pytest.raises(parsers.ParseError, match=message):
        parsers.parse_document(data, 'a.pdf')


def test_docx_paragraph_table_and_header():
    body = '<w:p><w:r><w:t>图需</w:t><w:tab/><w:t>要求</w:t></w:r></w:p>'
    body += '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>表格值</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
    header = ('<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
              '<w:p><w:r><w:t>页眉</w:t></w:r></w:p></w:hdr>')
    text = parsers.parse_document(docx(body, {'word/header1.xml': header}), 'a.docx')
    assert text == '图需\t要求\n表格值\n页眉'


@pytest.mark.parametrize('data', [
    docx(extra={'word/evil.xml': '<!DOCTYPE x [<!ENTITY a SYSTEM "file:///etc/passwd">]><x>&a;</x>'}),
    docx(extra={'bomb.bin': b'0' * (2 * 1024**2)}),
    b'PK\x03\x04broken',
    xlsx([['wrong file']]),
])
def test_docx_unsafe_or_wrong_archive(data):
    with pytest.raises(parsers.ParseError):
        parsers.parse_document(data, 'a.docx')


def test_xlsx_values_no_formula_execution():
    text = parsers.parse_document(xlsx([['SKU', 'Price'], ['A-1', 12.5],
                                       ['=HYPERLINK("http://localhost/","unsafe")', None]]), 'a.xlsx')
    assert 'A-1\t12.5' in text
    assert 'unsafe' not in text and 'HYPERLINK' not in text
    with pytest.raises(parsers.ParseError, match='没有可读取'):
        parsers.parse_document(xlsx([['=1+1']]), 'a.xlsx')


@pytest.mark.parametrize('encoding', ['utf-8-sig', 'utf-8', 'gb18030'])
def test_csv_encodings_and_quoted_multiline(encoding):
    data = 'SKU,说明\r\nA1,"中文,逗号\n换行"\r\nA2,=1+1'.encode(encoding)
    assert parsers.parse_document(data, 'a.csv') == 'SKU\t说明\nA1\t中文,逗号\n换行\nA2\t=1+1'


@pytest.mark.parametrize('data', [b'\xff', b'a,"unfinished', b' , \n', b'\x00abc'])
def test_csv_invalid_and_empty(data):
    with pytest.raises(parsers.ParseError):
        parsers.parse_document(data, 'a.csv')


def test_output_limit_is_failure_not_truncation():
    with pytest.raises(parsers.ParseError, match='2 MiB'):
        parsers.parse_document((('x' * 1000 + '\n') * 2200).encode(), 'a.csv')
    collector = TextCollector()
    with pytest.raises(DocumentError):
        collector.add('x' * (parsers.MAX_TEXT_BYTES + 1))


def test_complete_long_text_is_preserved():
    text = '\n'.join('row-' + str(index) + '-' + '字' * 100 for index in range(2000))
    assert parsers.parse_document(text.encode(), 'a.csv') == text


@pytest.mark.skipif(os.name != 'posix', reason='Linux resource limits; Windows uses wall timeout')
def test_worker_memory_limit_really_enforced(tmp_path):
    source = tmp_path / 'input.csv'
    result = tmp_path / 'result.json'
    source.write_bytes(b'a,b')
    script = (
        'import sys; from app.overseas.materials import document_formats, parser_worker; '
        'document_formats.extract=lambda *_: bytearray(600*1024**2); '
        'sys.argv=["worker",sys.argv[1],sys.argv[2]]; parser_worker.main()'
    )
    subprocess.run([sys.executable, '-c', script, str(source), str(result)],
                   check=True, timeout=10)
    assert 'error' in json.loads(result.read_text())


def test_timeout_kills_and_reaps_real_process(monkeypatch):
    processes = []
    original = subprocess.Popen

    def sleeping_process(*args, **kwargs):
        process = original([sys.executable, '-c', 'import time; time.sleep(60)'], **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(parsers.subprocess, 'Popen', sleeping_process)
    monkeypatch.setattr(parsers, 'PARSE_TIMEOUT_SECONDS', 0.05)
    with pytest.raises(parsers.ParseError, match='超时'):
        parsers.parse_document(b'a,b', 'a.csv')
    assert len(processes) == 1
    assert processes[0].poll() is not None
    assert processes[0].wait(timeout=0.1) != 0


def test_xls_real_ole_fixture():
    # Small BIFF8/OLE workbook produced with xlwt; no runtime writer dependency.
    fixture = (
        'eJy7cF7wwcKNUg8Z0IAdAzPDv/+cDGxIYoxAzAnjCDAA5f//BzFhNAcQ/x8FQwpwcgAjko2VYTfv'
        'GXZQHILi+yEDE8MGloNAkoHhERDHMBQw+OXnpSrQETiB3ZDICHKDLZBkZJgDFOFjkAS7SghMJoNJ'
        'YTC5HqxyD5h0AIv0gklboNoHjFEM5+39tCygqTiCSQksx8cAMnc7WM8tsIghgyjDCVAqrp/ACFHL'
        'yuBYlJmYMzgl5Fh4GJYwAOPNPTUvtSgx5wGDCDAClzB8/a/AwPAFllMPKIyK01eckQEo/gNVnB2L'
        '+GQmFgaGBob/CeAE3gosUw8zg2Q4GAKK8lNKk0uK/zDIMICEoDjYO5SVASiZmZwK5DnqGnIBxSFZWA'
        'AlC/OCkzYPkExh4AezBcEJXABo9p+VHy/5JgXYx4NFGsDFNqRwVwW5h+E/QyNIB1AzH1iGCU5qg'
        'UltMNkENlUazJYCkyLAZAmk1QJEoQy3ZrCaFrCsGtAeYzC4bK+OxNYAsltfB+6Qa31srwlkr3N/WC'
        'Wy7rr9QgYlYGWTAtQPgs0MOow6jLNmgsBOexjNCC0I7oJJSYxCgYNJAOr2/5AgZ+Rn+MvABWYKgkkID'
        'xQ6jFD1jFjUM4LVg0ysY+ICu0eQoVsYWEkyCTFsAwePAwMCcDGMglEwCkbBKBgFo2AUjIJRMEgBpLk'
        'L6WCAGv/A7gW4AwHqSYDGdf4C8b+BHqQYBTQDQQz5QFgC7Ji6MuQB6SKGSpLSjxgDKyPMLEYi9cDGC'
        '0EgHGh7EUM2QxLYHdkk2Q0CwA4gI7J/iNYoQLJVuADJ9v8jxZ00th8An5nA4w=='
    )
    data = zlib.decompress(base64.b64decode(fixture))
    assert parsers.validate_document(data, 'a.xls', 'competitor')[1] == 'application/vnd.ms-excel'
    assert parsers.parse_document(data, 'a.xls') == '[Products] SKU\tPrice\n[Products] A-1\t12.5'
