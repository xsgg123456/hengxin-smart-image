"""Select only CLI user-facing messages; never publish reasoning or tool output."""
import re
import unicodedata

PREFIX = 'Codex：'
SENSITIVE = re.compile(
    r'api[ _-]?key|access[ _-]?key|token|secret|password|authorization|bearer|cookie|'
    r'凭证|密钥|口令|密码|-----BEGIN', re.I)


def public_message(event, skill_name=None) -> str | None:
    # Only the prepared task binding is trusted, never a name claimed in prose.
    if not isinstance(skill_name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', skill_name):
        skill_name = None
    if not isinstance(event, dict) or event.get('type') != 'item.completed':
        return None
    item = event.get('item')
    if not isinstance(item, dict) or item.get('type') != 'agent_message':
        return None
    value = item.get('text')
    if not isinstance(value, str) or not value.strip() or len(value) > 16000:
        return None
    value = ''.join(c for c in value if c in '\n\t' or not unicodedata.category(c).startswith('C'))
    # Drop the entire message on credential markers, rather than guessing where
    # a potentially multiline secret ends. Only prose on allowed channels passes.
    if SENSITIVE.search(value):
        return None
    value = re.sub(r'```[\s\S]*?(?:```|$)', '', value)
    value = re.sub(r'~~~[\s\S]*?(?:~~~|$)', '', value)
    value = re.sub(r'!\[[^\]]*\]\([^\n]*?\)', '[图片]', value)
    value = re.sub(r'\[([^\]]+)\]\([^\n]*?\)', r'\1', value)
    value = re.sub(r'`[^`]*(?:`|$)', lambda m: m[0][1:-1]
                   if skill_name and m[0] in (f'`{skill_name}`', f'`${skill_name}`')
                   else '[技术细节已省略]', value)
    value = re.sub(r'<[^>]*>', '', value)
    value = re.sub(r'(?:[a-z][a-z0-9+.-]{1,20}://|www\.)[^\s，。；）)]+', '[链接已省略]', value, flags=re.I)
    value = re.sub(r'(?:[A-Za-z]:[\\/]|\\\\)[^\s，。；）)]+', '[路径已省略]', value)
    value = re.sub(r'(?<!\d)/[^\s，。；）)]+', '[路径已省略]', value)
    value = re.sub(r'\b[A-Za-z_.-][\w.-]*(?:[/\\][\w.-]+)+', '[路径已省略]', value)
    value = re.sub(r'(?<![A-Za-z0-9_+=-])[A-Za-z0-9_+=-]{32,}(?![A-Za-z0-9_+=-])', lambda m: m[0]
                   if m[0] == skill_name else '[标识已省略]', value)
    value = re.sub(r'(?im)^.*(?:\b(?:sudo|curl|wget|bash|powershell|python3?|node|npm|pip|chmod)\s).*$','',value)
    value = re.sub(r'[^。！？\n]*(?:\bmanifest(?:\.json)?\b|\bslot\s+\d+)[^。！？\n]*[。！？]?', '', value, flags=re.I)
    value = re.sub(r'\n{3,}', '\n\n', value).strip()
    if not value or SENSITIVE.search(value):
        return None
    return PREFIX + value[:800] + ('…（内容已精简）' if len(value) > 800 else '')
