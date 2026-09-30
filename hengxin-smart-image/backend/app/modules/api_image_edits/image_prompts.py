"""API-only image editing policy, independent from text editing."""
from pathlib import Path

IMAGE_EDIT_POLICY = 'api-image-edit-v1'
IMAGE_EDIT_TEMPLATE = (Path(__file__).parent / 'image_edit_prompt.txt').read_text(encoding='utf-8')


def build_image_prompt(text):
    return (IMAGE_EDIT_TEMPLATE.replace('{{用户本次填写的修改意见及各处标注说明}}', text),
            IMAGE_EDIT_POLICY)
