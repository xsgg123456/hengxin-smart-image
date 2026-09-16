import pytest

from app.execution.public_messages import public_message


def message(text, kind='agent_message', event_type='item.completed'):
    return public_message({'type': event_type, 'item': {'type': kind, 'text': text}})


@pytest.mark.parametrize('kind', ['reasoning', 'command_execution', 'mcp_tool_call', 'file_change', 'unknown'])
def test_only_user_facing_channel_is_selected(kind):
    assert message('内部内容', kind) is None


def test_only_completed_messages_and_well_formed_text_are_selected():
    for event in [None, [], {}, {'type': []}, {'type': 'item.completed', 'item': []}]:
        assert public_message(event) is None
    for value in [None, {}, 1, '', '  ', 'x' * 16001]:
        assert message(value) is None
    assert message('处理中', event_type='item.started') is None


@pytest.mark.parametrize('credential', ['api_key=abc', 'Bearer xyz', 'token: xyz', '密钥是 abc',
                                       'password\nabc', '-----BEGIN PRIVATE KEY-----'])
def test_credential_marker_discards_entire_message(credential):
    assert message('第1张已完成\n' + credential) is None


def test_prose_and_native_dimension_distinction_survive():
    text = '第 1 张已生成，保留文字和钻石。原生 1254×1254，放大至 4096×4096，并非原生 4K。'
    assert message(text) == 'Codex：' + text
    assert message(text + 'manifest.json 已更新为本轮 slot 0。') == 'Codex：' + text


@pytest.mark.parametrize('path', ['/home/private/result.png', '文件/work/result.png',
                                 '/用户/private/result.png', '/123/private/result.png',
                                 'C:\\Users\\private\\result.png', '\\\\server\\private\\result.png',
                                 './private/result.png', 'output/result.png'])
def test_paths_are_removed(path):
    result = message('已完成：' + path)
    assert 'private' not in result and 'result.png' not in result


def test_filter_does_not_expose_credentials_created_by_markup_removal():
    for text in ['api<b></b>_key=abc', 'pass<b></b>word=demo123', 'to```text\nx\n```ken=demo123']:
        assert message(text) is None
    assert message('第 1/2 张，2026/09/11 完成。') == 'Codex：第 1/2 张，2026/09/11 完成。'


@pytest.mark.parametrize('suffix', ['', '。', '\n继续处理'])
def test_numeric_directory_is_not_mistaken_for_fraction(suffix):
    assert '/123' not in message('工作目录：/123' + suffix)


def test_code_link_targets_controls_and_identifiers_are_removed():
    text = ('已生成\x00\u202e\n```python\nprint("internal")\n```\n'
            '[下载图片](https://internal.example/output.png)\n'
            'ftp://private.example/file\n`/work/manifest.json`\n' + 'a' * 40)
    result = message(text)
    assert '已生成' in result and '下载图片' in result
    for hidden in ['print', 'internal', 'private', '/work', '\x00', '\u202e', 'a' * 40]:
        assert hidden not in result
    assert message('```bash\ncat private') is None
    assert 'private' not in message('处理中 `private')


def test_message_is_bounded_and_plain_command_line_dropped():
    assert len(message('图' * 2000)) < 830
    assert message('准备好了\ncurl https://example.com\n继续生成') == 'Codex：准备好了\n\n继续生成'
