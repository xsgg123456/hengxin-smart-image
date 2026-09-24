"""Only a wholly recognized exec program is evidence for an image call."""
import pytest

from app.execution.material_literals import image_calls


CALL = 'tools.image_gen__imagegen({prompt:"实际内容"})'


@pytest.mark.parametrize('prefix', [
    'exit();',
    'await tools.some_tool();',
    'const previous = await tools.some_tool();',
    'const previous = missing;',
    'missing();',
    'const tools = {};',
    'let generatedImage = null;',
    'const text = 1;',
    'const x = 1; let x = 2;',
    'const await = 1;',
    'const arguments = 1;',
    'const x = {a: unknown};',
    'const x = 01;',
    "const x = '\\u12';",
    "const x = '\\01';",
    "const x = 'line\nbreak';",
    '\u0085',
])
def test_prior_execution_or_invalid_declaration_is_not_evidence(prefix):
    assert image_calls(prefix + CALL + ';') == ([], True)


@pytest.mark.parametrize('suffix', [
    '}', '(', 'const broken =;', '/* never closed',
    'generatedImage(missing);', 'exit();', 'const result = 1;',
    '// comment\u2028}', '// comment\r}',
])
def test_entire_program_must_parse_including_tail(suffix):
    assert image_calls('const result = await ' + CALL + ';' + suffix) == ([], True)


@pytest.mark.parametrize('first', [CALL, 'await ' + CALL, 'const result = await ' + CALL])
def test_second_call_is_unknown_even_if_first_is_literal(first):
    assert image_calls(first + '; await ' + CALL + ';') == ([], True)


@pytest.mark.parametrize('code', [
    CALL,
    'await ' + CALL + ';',
    'const result = await ' + CALL + '; generatedImage(result);',
    'let result = await ' + CALL + '; text(result); generatedImage(result);',
    'const fake = "tools.image_gen__imagegen({prompt:unknown})"; ' + CALL,
    'let x = {nested:[true, false, null, -2.5, "ok"],}; const y = `静态文本`; ' + CALL,
    '// @exec: {}\n/* leading */ const result = await ' + CALL + ';\n'
    '/* display */ generatedImage(result); // done',
    '// comment\u2028' + CALL,
    '// comment\r' + CALL,
])
def test_restricted_literal_programs_and_real_production_shape(code):
    assert image_calls(code) == ([{'prompt': '实际内容'}], False)


@pytest.mark.parametrize('code', [
    '// tools.image_gen__imagegen({prompt:"fake"});',
    'const fake = "tools.image_gen__imagegen({prompt:unknown})";',
    'text("nothing relevant");',
])
def test_comments_and_strings_are_not_calls(code):
    assert image_calls(code) == ([], False)


def test_separate_exec_programs_keep_each_call():
    scripts = ['const result = await ' + CALL + '; generatedImage(result);'] * 2
    assert [call for script in scripts for call in image_calls(script)[0]] == [
        {'prompt': '实际内容'}, {'prompt': '实际内容'},
    ]
