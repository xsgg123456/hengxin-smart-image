"""Bound reads without allocating the entire allowed maximum for small files."""
from hashlib import sha256


def read_bounded(stream, limit, chunk_size=1024 * 1024):
    if type(limit) is not int or limit < 0 or chunk_size < 1:
        raise ValueError('Invalid read limit')
    chunks, total = [], 0
    while True:
        data = stream.read(min(chunk_size, limit - total + 1))
        if not data:
            break
        total += len(data)
        if total > limit:
            raise ValueError('File exceeds resource limit')
        chunks.append(data)
    return b''.join(chunks)


def copy_verified(stream, output, size, checksum, chunk_size=1024 * 1024):
    """Copy a known-size original in bounded chunks, verifying before commit."""
    if type(size) is not int or size < 0 or chunk_size < 1:
        raise ValueError('Invalid verified copy size')
    digest, total = sha256(), 0
    while chunk := stream.read(chunk_size):
        if not isinstance(chunk, bytes) or len(chunk) > chunk_size:
            raise ValueError('Invalid verified copy chunk')
        total += len(chunk)
        if total > size:
            raise ValueError('Verified copy exceeds expected size')
        digest.update(chunk)
        if output is not None:
            output.write(chunk)
    if total != size or digest.hexdigest() != checksum:
        raise ValueError('Verified copy integrity mismatch')
