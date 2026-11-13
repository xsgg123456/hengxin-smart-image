"""Publish immutable captured files under a creator-owned object namespace."""
from types import SimpleNamespace
from uuid import UUID

from app.overseas.studio.files import verify
from app.overseas.studio.output_files import FileRef
from . import output_intents
from .bindings import lock_admission
from .runtime import changed, locked, valid
from .turn_models import OutputFile, Picture


def same(row, expected):
    return all(getattr(row, key) == value for key, value in expected.items())


def save(factory, job_id, token, store, bucket, target, result, item):
    size = result.size_bytes if isinstance(result, FileRef) else len(result.data)
    if (item.get('status') != 'captured' or item.get('target') != target
            or item.get('checksum') != result.checksum or item.get('sizeBytes') != size
            or item.get('name') != result.name or item.get('contentType') != result.content_type
            or item.get('width') != result.width or item.get('height') != result.height):
        raise ValueError('Domestic Studio captured output mismatch')
    identity = UUID(item['pictureId'])
    image = result.width is not None and result.height is not None
    model, other_model = (Picture, OutputFile) if image else (OutputFile, Picture)
    with factory.begin() as session:
        lock_admission(session)
        _, channel, turn, job = locked(session, job_id)
        if not job or not valid(turn, job, token):
            raise ValueError('Domestic Studio delivery ownership lost')
        prefix = f'domestic-studio/outputs/{channel.owner_id}/{channel.workspace}/{channel.id}/{turn.id}'
        owner, workspace, turn_id = channel.owner_id, channel.workspace, turn.id
        expected = dict(turn_id=turn_id, name=result.name, content_type=result.content_type,
                        size_bytes=size, checksum=result.checksum,
                        bucket=bucket, object_key=f'{prefix}/{identity}', source_path=target)
        if image:
            expected.update(width=result.width, height=result.height)
        old = session.get(model, identity)
        if session.get(other_model, identity) is not None or (old is not None and not same(old, expected)):
            raise ValueError('Domestic Studio output identity conflict')
        write = output_intents.reserve(turn, identity, expected) and old is None
    file = SimpleNamespace(**expected)
    if write:
        if isinstance(result, FileRef):
            from app.overseas.studio import context_fs as fs
            with fs.reader(result.path) as source:
                store.put_stream(file, source, size)
        else:
            store.put(file, result.data)
    verify(store, file)
    with factory.begin() as session:
        lock_admission(session)
        state, channel, turn, job = locked(session, job_id)
        if (not job or not valid(turn, job, token) or channel.owner_id != owner
                or channel.workspace != workspace or turn.id != turn_id):
            raise ValueError('Domestic Studio delivery ownership lost')
        row = session.get(model, identity)
        if session.get(other_model, identity) is not None:
            raise ValueError('Domestic Studio output identity conflict')
        if row is None:
            session.add(model(id=identity, **expected))
            changed(state, channel, turn)
        elif not same(row, expected):
            raise ValueError('Domestic Studio output identity conflict')
        output_intents.confirm(turn, identity, expected)
    return identity
