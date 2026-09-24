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


METADATA = ('text(Object.fromEntries(Object.entries(result).filter(([k]) => '
            '!["image_url", "b64_json", "data"].includes(k))));')


def test_real_exec_with_result_storage_and_metadata_projection():
    code = """const result = await tools.image_gen__imagegen({
        referenced_image_paths:['/work/current/00.png','/work/original/00.jpg','/work/inputs/00.png'],
        prompt:'完整业务文字'});
        store('key', result);
        text(Object.fromEntries(Object.entries(result).filter(([k]) =>
            !['image_url','b64_json','data'].includes(k))));"""
    assert image_calls(code) == ([{
        'referenced_image_paths': ['/work/current/00.png', '/work/original/00.jpg', '/work/inputs/00.png'],
        'prompt': '完整业务文字',
    }], False)


@pytest.mark.parametrize('tail', [
    "store('key', result);",
    'store("key", result); text(result); generatedImage(result);',
    METADATA,
    METADATA.replace('[k]', '[field]').replace('includes(k)', 'includes(field)'),
    METADATA.replace('["image_url", "b64_json", "data"]', '[]'),
])
def test_safe_result_tail(tail):
    assert image_calls('const result = await ' + CALL + ';' + tail) == ([{'prompt': '实际内容'}], False)


@pytest.mark.parametrize('tail', [
    "store('key', missing);", "store(missing, result);", 'store(1, result);',
    "store(['key'], result);", "store('key', result, exit());",
    "store('key', result", "store('key' result);", "store('key', result); exit();",
    METADATA.replace('entries(result)', 'entries(missing)'),
    METADATA.replace('includes(k)', 'includes(missing)'),
    METADATA.replace('[k]', '[k, value]'),
    METADATA.replace('[k]', '[await]'),
    METADATA.replace('=> !', '=> exit() || !'),
    METADATA.replace('=>', '= >'),
    METADATA.replace('=>', '\n=>'),
    METADATA.replace('=>', '/*\n*/=>'),
    METADATA.replace('=> !', '=> { exit(); return !'),
    METADATA.replace('includes(k)', 'includes(exit())'),
    METADATA.replace('"data"', 'unknown'),
    METADATA.replace('"data"', '1'),
    METADATA.replace('"data"', '{}'),
    METADATA.replace('"data"', '...missing'),
    METADATA.replace('"data"', '"data" "extra"'),
    METADATA.replace('"data"]', '"data"'),
    METADATA.replace('includes(k)', 'includes(k, missing)'),
    METADATA[:-2],
    METADATA + ' await ' + CALL + ';',
])
def test_unrecognized_result_tail_rejects_entire_program(tail):
    assert image_calls('const result = await ' + CALL + ';' + tail) == ([], True)


@pytest.mark.parametrize('prefix', [
    "store('key', result);", METADATA, 'const Object = {};', 'const store = null;',
    'exit();', 'await tools.some_tool();',
])
def test_metadata_tail_does_not_allow_prior_side_effects_or_shadowed_globals(prefix):
    assert image_calls(prefix + 'const result = await ' + CALL + ';' + METADATA) == ([], True)


def test_result_tail_requires_defined_image_result():
    assert image_calls('await ' + CALL + ';' + METADATA) == ([], True)
    assert image_calls('await ' + CALL + "; store('key', result);") == ([], True)
