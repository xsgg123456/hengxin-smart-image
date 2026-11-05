"""Expose only public edit fields and the metadata captured at send time."""
from uuid import UUID


def public_edits(payload):
    return [dict(pictureId=edit['pictureId'], annotationId=edit.get('annotationId'),
        text=edit.get('text', ''), references=[dict(attachmentId=ref['attachmentId'],
            kind=ref['kind'], customPurpose=ref.get('customPurpose') or '', note=ref['note'])
            for ref in edit.get('references', [])])
        for edit in payload.get('imageEdits', [])]


def frozen_metadata(payload, attachments, pictures):
    if not payload.get('imageEdits'):
        return
    inputs = payload.get('inputs', [])
    for index, item in enumerate([*attachments, *pictures]):
        identity = item['id'].split(':', 1)[-1]
        if index >= len(inputs) or inputs[index]['id'] != str(UUID(identity)):
            raise ValueError('Image edit history input mismatch')
        source = inputs[index]
        item['name'] = source['name']
        if index < len(attachments):
            item['contentType'] = source['content_type']
            item['sizeBytes'] = source['size_bytes']
