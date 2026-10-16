"""Bind edit instructions to frozen inputs, never to potentially repeated filenames."""
import json
from uuid import UUID
from fastapi import HTTPException


def freeze_edits(body, attachments, references):
    result = []
    for edit in body.imageEdits:
        picture_index = body.referencePictureIds.index(edit.pictureId)
        if references[picture_index].content_type not in ('image/png', 'image/jpeg', 'image/webp'):
            raise HTTPException(422, '修改原图必须是支持的图片')
        annotation_index = None
        if edit.annotationId is not None:
            annotation_index = body.attachmentIds.index(edit.annotationId)
            if attachments[annotation_index].content_type != 'image/png':
                raise HTTPException(422, '标注附件必须是PNG图片')
        result.append(dict(**edit.model_dump(mode='json'),
            pictureInputIndex=len(attachments) + picture_index, annotationInputIndex=annotation_index))
    return result


def message_text(body, references):
    if not body.imageEdits:
        return body.text
    names = {row.id: row.name for row in references}
    parts = [f'修改{names[edit.pictureId]}：\n{edit.text}' for edit in body.imageEdits]
    if body.text:
        parts.append(body.text)
    return '\n\n'.join(parts)


def prompt_edits(payload, paths):
    edits = payload.get('imageEdits', [])
    if not edits:
        return ''
    inputs = payload['inputs']
    if len(paths) != len(inputs):
        raise ValueError('Image edit input paths mismatch')

    def bound(index, identity):
        if (type(index) is not int or not 0 <= index < len(inputs)
                or inputs[index]['id'] != identity):
            raise ValueError('Image edit frozen input mismatch')
        return paths[index]['path']

    instructions = []
    for edit in edits:
        original = bound(edit['pictureInputIndex'], edit['pictureId'])
        annotation = edit.get('annotationId')
        marked = bound(edit['annotationInputIndex'], str(UUID(annotation.split(':', 1)[1]))) if annotation else None
        instructions.append(dict(pictureId=edit['pictureId'], originalPath=original,
            annotationPath=marked, text=edit['text']))
    return ('图片修改要求：每项 originalPath 是对应原图，必须以原图为编辑基础；'
            'annotationPath 如存在仅用于定位修改区域，线框、画笔、编号不得画进成品。'
            '逐图完整执行对应 text，并结合本轮主输入的整体补充。\n'
            + json.dumps(instructions, ensure_ascii=False))
