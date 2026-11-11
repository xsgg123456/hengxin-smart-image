import ctypes
from pathlib import Path

import pytest

from app.execution import office_render as render


@pytest.mark.parametrize('args', [[], ['--convert-to'], ['--outdir'],
    ['--convert-to', 'html', 'test.pptx'], ['--accept=socket,host=0.0.0.0'],
    ['--convert-to', 'pdf:impress_pdf_Export:unsupported', 'test.pptx']])
def test_unsupported_cli_options_fail_explicitly(args):
    with pytest.raises(ValueError):
        render.arguments(args)


def test_native_abi_uses_size_checked_stable_prefix():
    assert render.OfficeClass.destroy.offset == ctypes.sizeof(ctypes.c_size_t)
    assert render.DocumentClass.save.offset == ctypes.sizeof(ctypes.c_size_t) + ctypes.sizeof(ctypes.c_void_p)


def test_same_input_output_refused_before_native_load(tmp_path):
    source = tmp_path / 'source.pdf'
    source.write_bytes(b'%PDF-test')
    with pytest.raises(ValueError, match='Unsafe PDF'):
        render.convert(source, tmp_path)
    assert source.read_bytes() == b'%PDF-test'


def test_invalid_native_output_preserves_existing_file(tmp_path, monkeypatch):
    from types import SimpleNamespace
    source = tmp_path / 'sample.txt'
    source.write_bytes(b'test input')
    target = tmp_path / 'sample.pdf'
    target.write_bytes(b'existing result')
    monkeypatch.setattr(render.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=1))
    with pytest.raises(RuntimeError, match='conversion failed'):
        render.convert(source, tmp_path)
    assert target.read_bytes() == b'existing result'
    assert not list(tmp_path.glob('.office-*'))


@pytest.mark.parametrize('failure', ['timeout', 'corrupt_pdf'])
def test_native_timeout_or_corrupt_success_preserves_existing_file(tmp_path, monkeypatch, failure):
    from types import SimpleNamespace
    source = tmp_path / 'sample.txt'
    source.write_bytes(b'test input')
    target = tmp_path / 'sample.pdf'
    target.write_bytes(b'existing result')

    def native_run(argv, **kwargs):
        if failure == 'timeout':
            raise render.subprocess.TimeoutExpired(argv, kwargs['timeout'])
        Path(argv[-2]).write_bytes(b'corrupt PDF')
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(render.subprocess, 'run', native_run)
    with pytest.raises(Exception):
        render.convert(source, tmp_path)
    assert target.read_bytes() == b'existing result'
    assert not list(tmp_path.glob('.office-*'))
