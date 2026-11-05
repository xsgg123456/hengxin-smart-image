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
        frozen = edit.model_dump(mode='json')
        for reference in frozen['references']:
            index = body.attachmentIds.index(reference['attachmentId'])
            source = attachments[index]
            if str(source.id) != str(UUID(reference['attachmentId'].split(':', 1)[1])):
                raise HTTPException(422, '参考图附件身份不匹配')
            if source.content_type not in ('image/png', 'image/jpeg', 'image/webp'):
                raise HTTPException(422, '参考图必须是PNG、JPG或WebP图片')
            if not 0 < source.size_bytes <= 20 * 1024 * 1024:
                raise HTTPException(422, '参考图大小不能超过20MiB')
            reference['inputIndex'] = index
        result.append(dict(**frozen,
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
        references = [dict(path=bound(ref['inputIndex'], str(UUID(ref['attachmentId'].split(':', 1)[1]))),
            kind=ref['kind'], customPurpose=ref.get('customPurpose'), note=ref['note'])
            for ref in edit.get('references', [])]
        instructions.append(dict(pictureId=edit['pictureId'], originalPath=original,
            annotationPath=marked, text=edit['text'], references=references))
    return ('图片修改要求：每项 originalPath 是对应原图，必须以原图为编辑基础；'
            'annotationPath 如存在仅用于定位修改区域，线框、画笔、编号不得画进成品。'
            '逐图完整执行对应 text，并结合本轮主输入的整体补充。'
            '每项 references 只属于该项原图，不是额外待生成图片；path 是真实参考文件。'
            'kind=product 为本产品实拍，参照商品结构；kind=effect 为成品效果参考，按 note 参照表现；'
            'kind=custom 按完整 customPurpose 用途参考。所有参考均须完整遵循 note，不得跨图套用。\n'
            + json.dumps(instructions, ensure_ascii=False))
