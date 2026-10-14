"""Only explicit final deliveries cross the workbench image boundary."""
from types import SimpleNamespace

import pytest
from PIL import Image

from app.overseas.studio.delivery import collect_delivery


@pytest.fixture
def space(tmp_path):
    work, home = tmp_path / 'work', tmp_path / 'home'
    work.mkdir()
    (home / '.codex/generated_images/session').mkdir(parents=True)
    return SimpleNamespace(work=work, home=home, baseline={})


def picture(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (12, 13), 'blue').save(path)
    return path


def collect(space, text, **overrides):
    summary = dict(turn_completed=True, error=None, final_text=text, session_id='session')
    return collect_delivery(space, SimpleNamespace(**(summary | overrides)))


def test_generated_files_without_final_delivery_are_never_discovered(space):
    picture(space.work / 'temporary.png')
    picture(space.home / '.codex/generated_images/session/draft.png')
    assert collect(space, '我正在尝试构图，还没有正式交付图片。') == ([], [])


@pytest.mark.parametrize('text', [
    '`![草稿](/work/draft.png)`',
    '```markdown\n![草稿](/work/draft.png)\n```',
    '临时文件位于 /work/draft.png',
    '\\![草稿]\\(/work/draft.png)',
])
def test_code_and_bare_paths_are_not_delivery(space, text):
    picture(space.work / 'draft.png')
    assert collect(space, text) == ([], [])


def test_only_linked_formal_image_accepted_among_drafts(space):
    picture(space.work / 'final.png')
    picture(space.work / 'draft.png')
    delivered, warnings = collect(space, '正式交付：![最终设计](/work/final.png)')
    assert warnings == []
    assert [target for target, _ in delivered] == ['/work/final.png']
    assert delivered[0][1].width == 12


def test_explicit_draft_links_in_final_are_not_formal_delivery(space):
    picture(space.work / 'draft.png')
    picture(space.work / 'final.png')
    text = '## 草稿\n![预览](/work/draft.png)\n## 正式交付\n![最终设计](/work/final.png)'
    outputs, warnings = collect(space, text)
    assert [target for target, _ in outputs] == ['/work/final.png']
    assert warnings == []


@pytest.mark.parametrize('text', [
    '## 中间文件\n![预览](/work/a.png)',
    '这是草稿，暂不交付。\n\n![预览](/work/a.png)',
    '![预览](/work/a.png)\n\n以上是草稿，暂不交付。',
    '## 草稿\n### 预览\n![图片](/work/a.png)',
    '## 草稿\n### 最终图\n![图片](/work/a.png)',
    '这些是过程图。\n\n## 图片\n![预览](/work/a.png)',
    'Temporary working files.\n\n![Preview](/work/a.png)',
])
def test_non_delivery_scope_covers_paragraphs_and_child_headings(space, text):
    picture(space.work / 'a.png')
    assert collect(space, text) == ([], [])


@pytest.mark.parametrize('boundary', ['## 正式交付', '正式交付：'])
def test_explicit_formal_scope_after_draft_prose(space, boundary):
    picture(space.work / 'a.png')
    picture(space.work / 'final.png')
    text = f'这是草稿，暂不交付。\n\n![预览](/work/a.png)\n\n{boundary}\n\n![图片](/work/final.png)'
    outputs, warnings = collect(space, text)
    assert [target for target, _ in outputs] == ['/work/final.png']
    assert warnings == []


@pytest.mark.parametrize('reference', [
    '![预览](/work/final.png)',
    '![预览](/work/deliverable.png)',
    '![最终图片](/work/a.png)',
    '[下载最终图片](/work/a.png)',
    '`Final images`\n\n![预览](/work/a.png)',
    '<https://example.invalid/final>\n\n![预览](/work/a.png)',
    '文件在 /work/正式交付.png\n\n![预览](/work/a.png)',
    '文件名：正式交付.png\n\n![预览](/work/a.png)',
])
def test_reference_metadata_cannot_clear_non_delivery_scope(space, reference):
    for name in ('a.png', 'final.png', 'deliverable.png'):
        picture(space.work / name)
    assert collect(space, '这是草稿，暂不交付。\n\n' + reference) == ([], [])


@pytest.mark.parametrize('notice', [
    '以下图片仅供预览，并非最终交付。', '这不是正式交付。', '尚非最终图片。',
    '暂不作为正式交付。', '目前还没有达到交付标准。', '不能作为最终结果。',
    '仅供预览。', '此图待确认。', 'These are not final images.',
    'These are not yet approved for delivery.', "This isn't the final design.",
    'These cannot be delivered.', 'Non-final images.', 'For preview only.',
    'These are **not** final images.', 'These are not **final images**.',
    'These are n**ot** final images.', 'These are *not* **final** images.',
    'These are not\nfinal images.', 'These are not `final images`.',
    'These are [not](https://example.invalid) final images.',
    'These are not [final images](https://example.invalid).',
    '这些**并非**最终交付。', '这些并**非**最终交付。', '这些不是**正式交付**。',
    'These images are for testing only.', 'Experimental images.',
    'These images are for experimentation only.', 'This is a rough sketch.',
    'This is a preliminary version.', 'This is work in progress.',
    '这些图片仅用于测试。', '这些是初稿。', '这些是工作稿。', '这是中间版本。',
    '图片尚未完成。', 'Test images.',
])
@pytest.mark.parametrize('position', ['before', 'after', 'heading', 'alt', 'title'])
def test_negated_delivery_is_not_a_positive_declaration(space, notice, position):
    picture(space.work / 'final.png')
    image = '![图片](/work/final.png)'
    heading = notice.replace('\n', ' ')  # ATX headings end at the first newline.
    text = {'before': notice + '\n\n' + image, 'after': image + '\n\n' + notice,
            'heading': '## ' + heading + '\n\n### 图片\n' + image,
            'alt': '![' + notice + '](/work/final.png)',
            'title': '![图片](/work/final.png "' + notice + '")'}[position]
    assert collect(space, text) == ([], [])


def test_independent_positive_delivery_after_preview_notice(space):
    picture(space.work / 'preview.png')
    picture(space.work / 'final.png')
    text = ('以下仅供预览，并非最终交付。\n\n![图](/work/preview.png)\n\n'
            '## 正式交付\n无水印，保留全部细节。\n\n![图](/work/final.png)')
    outputs, warnings = collect(space, text)
    assert [target for target, _ in outputs] == ['/work/final.png'] and warnings == []


def test_emphasized_positive_declaration_starts_formal_section(space):
    picture(space.work / 'final.png')
    text = 'These are not final images.\n\n## **Final images**\n![Image](/work/final.png)'
    outputs, warnings = collect(space, text)
    assert [target for target, _ in outputs] == ['/work/final.png'] and warnings == []


@pytest.mark.parametrize('reference', [
    '![not final images](/work/final.png)',
    '![**not** final images](/work/final.png)',
    '![not **final images**](/work/final.png)',
    '![n**ot** final images](/work/final.png)',
    '![not `final images`](/work/final.png)',
    '![并**非**最终交付](/work/final.png)',
    '[![**not** final images](/work/final.png)](/work/final.png)',
    '![not ![final images](unused)](/work/final.png)',
    '![Image](/work/final.png "not final images")',
    '![Image](/work/final.png "not **final images**")',
    '[Download](/work/final.png "not final images")',
    '[Download](/work/final.png "not **final images**")',
    '![n&#111;t **final images**](/work/final.png)',
    '![n&#x6f;t **final images**](/work/final.png)',
    '![not&nbsp;final images](/work/final.png)',
    '![&#x975e;最终交付](/work/final.png)',
    r'![\*not\* final images](/work/final.png)',
    r'![n\*\*ot\*\* final images](/work/final.png)',
    '![ｎｏｔ final images](/work/final.png)',
    '![n\u200bot final images](/work/final.png)',
    '![Image](/work/final.png "n&#111;t final images")',
    'These are n&#111;t final images.\n\n![Image](/work/final.png)',
    '![![Image](unused "n&#111;t final images")](/work/final.png)',
])
def test_nested_alt_and_title_negations_are_not_delivery(space, reference):
    picture(space.work / 'final.png')
    assert collect(space, reference) == ([], [])


@pytest.mark.parametrize('notice', ['Tests passed. Final images:', '测试通过，正式交付：'])
def test_successful_validation_does_not_label_final_images_as_test_files(space, notice):
    picture(space.work / 'final.png')
    outputs, warnings = collect(space, notice + '\n\n![图片](/work/final.png)')
    assert [target for target, _ in outputs] == ['/work/final.png'] and warnings == []


@pytest.mark.parametrize('target', ['/work/final.png', 'final.png', 'sandbox:/work/final.png'])
def test_final_local_references_without_fixed_numbering(space, target):
    picture(space.work / 'final.png')
    outputs, warnings = collect(space, f'## 主图9\n[下载最终图片]({target})')
    assert len(outputs) == 1 and warnings == []


def test_native_generation_output_must_be_explicit_and_new(space):
    picture(space.home / '.codex/generated_images/session/old.png')
    picture(space.home / '.codex/generated_images/session/new.png')
    space.baseline = {'old.png': 'old-hash'}
    prefix = '/home/runner/.codex/generated_images/session/'
    outputs, warnings = collect(space, f'![新图]({prefix}new.png)\n![旧图]({prefix}old.png)')
    assert [target for target, _ in outputs] == [prefix + 'new.png']
    assert len(warnings) == 1


def test_invalid_one_does_not_hide_valid_delivery(space):
    picture(space.work / 'final.png')
    (space.work / 'broken.png').write_bytes(b'not-an-image')
    outputs, warnings = collect(space, '![正式1](/work/final.png)\n![正式2](/work/broken.png)')
    assert len(outputs) == len(warnings) == 1


@pytest.mark.parametrize('target', [
    '/work/inputs/original.png', '/work/skills/secret.png',
    '/work/../outside.png', 'https://example.invalid/result.png',
    '/home/runner/.codex/generated_images/another/result.png',
])
def test_input_skills_escape_external_and_other_sessions_rejected(space, target):
    picture(space.work / 'inputs/original.png')
    outputs, warnings = collect(space, f'![图片]({target})')
    assert outputs == [] and len(warnings) == 1


def test_preview_and_download_same_file_do_not_duplicate(space):
    picture(space.work / 'final.png')
    outputs, warnings = collect(space, '[![最终图](/work/final.png)](/work/final.png)')
    assert len(outputs) == 1 and warnings == []


@pytest.mark.parametrize('overrides', [{'turn_completed': False}, {'error': 'turn_failed'}])
def test_unfinished_or_failed_invocation_never_delivers_images(space, overrides):
    picture(space.work / 'final.png')
    assert collect(space, '![图片](/work/final.png)', **overrides) == ([], [])


def test_escaped_unicode_name(space):
    picture(space.work / '正式 交付.png')
    outputs, warnings = collect(space, '![设计](</work/正式 交付.png>)')
    assert len(outputs) == 1 and warnings == []
