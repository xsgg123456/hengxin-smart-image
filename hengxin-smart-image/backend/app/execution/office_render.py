#!/usr/bin/python3
"""Offline PDF conversion through LibreOfficeKit; no IPC listener or network exception.

Stable ABI: LibreOffice 24.2 include/LibreOfficeKit/LibreOfficeKit.h.
Kit initialization calls RequestHandler::Enable(false), unlike the desktop CLI.
"""
import ctypes as C
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


P, S = C.c_void_p, C.c_char_p
Destroy = C.CFUNCTYPE(None, P)
Load = C.CFUNCTYPE(P, P, S)
Error = C.CFUNCTYPE(P, P)
LoadOptions = C.CFUNCTYPE(P, P, S, S)
Free = C.CFUNCTYPE(None, P)
Save = C.CFUNCTYPE(C.c_int, P, S, S, S)


class OfficeClass(C.Structure):
    _fields_ = [('size', C.c_size_t), ('destroy', Destroy), ('load', Load),
                ('error', Error), ('load_options', LoadOptions), ('free_error', Free)]


class DocumentClass(C.Structure):
    _fields_ = [('size', C.c_size_t), ('destroy', Destroy), ('save', Save)]


class Office(C.Structure):
    _fields_ = [('klass', C.POINTER(OfficeClass))]


class Document(C.Structure):
    _fields_ = [('klass', C.POINTER(DocumentClass))]


def worker(source, target, profile):
    """A dedicated process owns all native threads and memory for one conversion."""
    root = Path(profile)
    for key, name in [('XDG_CACHE_HOME', 'cache'), ('XDG_CONFIG_HOME', 'config')]:
        directory = root / name
        directory.mkdir()
        os.environ[key] = str(directory)
    os.environ['SAL_USE_VCLPLUGIN'] = 'svp'
    library = C.CDLL('/usr/lib/libreoffice/program/libmergedlo.so')
    init = library.libreofficekit_hook_2
    init.argtypes, init.restype = [S, S], P
    office = init(b'/usr/lib/libreoffice/program', (root / 'profile').as_uri().encode())
    if not office:
        raise RuntimeError('Document renderer initialization failed')
    api = C.cast(office, C.POINTER(Office)).contents.klass.contents
    if api.size < C.sizeof(OfficeClass):
        raise RuntimeError('Unsupported document renderer ABI')
    document = api.load_options(office, Path(source).as_uri().encode(), b'Batch=true')
    if not document:
        raise RuntimeError('Document cannot be opened')
    doc = C.cast(document, C.POINTER(Document)).contents.klass.contents
    if doc.size < C.sizeof(DocumentClass):
        raise RuntimeError('Unsupported document ABI')
    if not doc.save(document, Path(target).as_uri().encode(), b'pdf', None):
        raise RuntimeError('PDF export failed')
    with open(target, 'rb') as stream:
        if stream.read(5) != b'%PDF-':
            raise RuntimeError('PDF export is invalid')
        os.fsync(stream.fileno())
    # Kit owns process-global native state. Do not run it through Python/DSO teardown.
    # The parent validates the completed PDF and removes the private profile.
    os._exit(0)


def arguments(values):
    harmless = {'--headless', '--invisible', '--nologo', '--nodefault', '--norestore',
                '--nofirststartwizard', '--nolockcheck'}
    source, output, format_name = [], Path.cwd(), None
    index = 0
    while index < len(values):
        arg = values[index]
        if arg in ('--convert-to', '--outdir'):
            index += 1
            if index == len(values):
                raise ValueError('Missing conversion option value')
            if arg == '--convert-to':
                format_name = values[index]
            else:
                output = Path(values[index])
        elif arg in harmless or arg.startswith('-env:UserInstallation='):
            pass  # Every conversion receives its own private profile.
        elif arg.startswith('-'):
            raise ValueError('Unsupported offline PDF option: ' + arg)
        else:
            source.append(Path(arg))
        index += 1
    if format_name not in ('pdf', 'pdf:impress_pdf_Export', 'pdf:writer_pdf_Export', 'pdf:calc_pdf_Export') or not source:
        raise ValueError('Offline renderer supports --headless --convert-to pdf [--outdir DIR] FILE...')
    output = output.resolve(strict=True)
    if not output.is_dir() or not any(output.is_relative_to(p) for p in (Path('/work'), Path('/tmp'))):
        raise ValueError('Output must be a task work or temporary directory')
    files = [path.resolve(strict=True) for path in source]
    if any(not p.is_file() or not any(p.is_relative_to(r) for r in (Path('/work'), Path('/tmp'))) for p in files):
        raise ValueError('Input must be a task file')
    if len({p.stem for p in files}) != len(files):
        raise ValueError('Inputs have colliding PDF names')
    return files, output


def convert(source, output):
    ooxml = {'.pptx': 'ppt/presentation.xml', '.docx': 'word/document.xml', '.xlsx': 'xl/workbook.xml'}
    if source.suffix.lower() in ooxml:
        with zipfile.ZipFile(source) as archive:
            if ooxml[source.suffix.lower()] not in archive.namelist():
                raise ValueError('Invalid Office document structure')
    target = output / (source.stem + '.pdf')
    if target.is_symlink() or target == source:
        raise ValueError('Unsafe PDF output target')
    with tempfile.TemporaryDirectory(prefix='.office-', dir=output) as temporary:
        root = Path(temporary)
        result = subprocess.run(['/usr/bin/python3', str(Path(__file__).resolve()), '--kit-worker',
            str(source), str(root / 'result.pdf'), str(root)], capture_output=True, timeout=90)
        if result.returncode:
            raise RuntimeError('Offline document conversion failed')
        # Independently parse the file; a native success return alone is insufficient.
        from pypdf import PdfReader
        pdf = root / 'result.pdf'
        if not PdfReader(pdf).pages:
            raise RuntimeError('PDF contains no pages')
        if target.is_symlink():
            raise ValueError('PDF output changed during conversion')
        os.replace(pdf, target)
    print('convert ' + str(source) + ' -> ' + str(target), flush=True)


def main():
    values = sys.argv[1:]
    if values == ['--version']:
        os.execv('/usr/bin/libreoffice', ['/usr/bin/libreoffice', '--version'])
    if values in (['--help'], ['-h']):
        print('Offline LibreOfficeKit: --headless --convert-to pdf [--outdir DIR] FILE...')
        return
    if len(values) == 4 and values[0] == '--kit-worker':
        try:
            worker(*values[1:])
        except BaseException:
            os._exit(1)
    files, output = arguments(values)
    for source in files:
        convert(source, output)


if __name__ == '__main__':
    main()
