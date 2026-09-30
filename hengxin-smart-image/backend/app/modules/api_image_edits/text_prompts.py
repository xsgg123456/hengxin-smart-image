"""API-only fixed text policies; never share these with CLI revisions."""
from pathlib import Path

_ROOT = Path(__file__).parent
TEXT_EDIT_POLICY = 'api-text-edit-v1'
TEXT_REPAIR_POLICY = 'api-text-repair-v2'
TEXT_EDIT_TEMPLATE = (_ROOT / 'text_edit_prompt.txt').read_text(encoding='utf-8')
TEXT_REPAIR_PROMPT = (_ROOT / 'text_repair_prompt.txt').read_text(encoding='utf-8').strip()


def build_text_prompt(kind, text):
    if kind == 'text_repair':
        return TEXT_REPAIR_PROMPT, TEXT_REPAIR_POLICY
    return (TEXT_EDIT_TEMPLATE.replace('{{用户输入的修改意见及各处标注说明}}', text),
            TEXT_EDIT_POLICY)
