"""Translate image-edit history to archive-owned, verified file identities."""
from uuid import UUID

from app.overseas.studio.image_edit_history import public_edits
from app.overseas.studio.schemas import Send


def validate(edits, attachments, pictures, text):
    if not isinstance(edits, list):
        raise ValueError('Invalid archive image edits')
    if not edits:
        return
    if not isinstance(text, str):
        raise ValueError('Invalid archive turn text')
    # The normal send schema verifies per-image references, annotation identity,
    # input uniqueness, required descriptions and supported reference purposes.
    # The displayed message concatenates every edit and can exceed the input
    # field limit even though the original request was valid; keep it intact.
    Send(text=text[:100000], attachmentIds=['upload:' + item['id'] for item in attachments],
         referencePictureIds=[UUID(item['id']) for item in pictures], imageEdits=edits)


def copy(payload, attachments, pictures, text):
    source_attachments = payload.get('attachmentIds', [])
    source_pictures = payload.get('referencePictureIds', [])
    if len(source_attachments) != len(attachments) or len(source_pictures) != len(pictures):
        raise ValueError('Archive source inputs do not match')
    uploads = {source: 'upload:' + item['id'] for source, item in zip(source_attachments, attachments)}
    originals = {source: item['id'] for source, item in zip(source_pictures, pictures)}
    result = []
    for edit in public_edits(payload):
        result.append(dict(pictureId=originals[edit['pictureId']],
            annotationId=uploads[edit['annotationId']] if edit['annotationId'] else None,
            text=edit['text'], references=[dict(attachmentId=uploads[ref['attachmentId']],
                kind=ref['kind'], customPurpose=ref['customPurpose'], note=ref['note'])
                for ref in edit['references']]))
    validate(result, attachments, pictures, text)
    return result
