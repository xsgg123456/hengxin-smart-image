"""A high file limit must not become a high minimum allocation."""
import tracemalloc

import pytest

from app.execution.bounded_read import read_bounded
from app.execution.diagnostics import _safe_read
from app.overseas.studio.delivery_snapshot_fs import read_bytes


@pytest.mark.parametrize('reader', [lambda p: _safe_read(p, 500_000_000, allow_windows_fallback=True),
                                    lambda p: read_bytes(p, 500_000_000)])
def test_eight_megabyte_file_does_not_preallocate_five_hundred_megabytes(tmp_path, reader):
    path = tmp_path / 'output.bin'
    path.write_bytes(b'x' * (8 * 1024 * 1024))
    tracemalloc.start()
    try:
        data = reader(path)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert len(data) == 8 * 1024 * 1024
    assert peak < 40 * 1024 * 1024


def test_bounded_reader_rejects_a_byte_over_limit():
    from io import BytesIO
    assert read_bounded(BytesIO(b'abc'), 3, 2) == b'abc'
    with pytest.raises(ValueError):
        read_bounded(BytesIO(b'abcd'), 3, 2)
