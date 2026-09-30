"""API-only image editing policy, independent from text editing."""
from pathlib import Path

IMAGE_EDIT_POLICY = 'api-image-edit-v2'
IMAGE_EDIT_TEMPLATE = (Path(__file__).parent / 'image_edit_prompt.txt').read_text(encoding='utf-8')


def build_image_prompt(text):
    return (IMAGE_EDIT_TEMPLATE.replace('{{用户修改意见}}', text),
            IMAGE_EDIT_POLICY)
