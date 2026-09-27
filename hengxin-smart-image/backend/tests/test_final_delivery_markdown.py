"""Structural Markdown formats share the existing file and slot safety gates."""
import pytest

from test_final_delivery import delivery  # noqa: F401
from app.execution.output_collector import OutputCollectionError


@pytest.mark.parametrize('reply', [
    '![成品][final]\n\n[final]: /work/final.png',
    '[下载][final]\n\n[final]: </work/final.png> "原图"',
    '![成品][]\n\n[成品]: /work/final.png',
    '![成品]\n\n[成品]: /work/final.png',
    '1.  成品\n\n    ![成品](/work/final.png)',
    '- 成品\n\n  [下载](/work/final.png)',
    '[![成品](/work/final.png)](/work/final.png)',
])
def test_structural_links(delivery, reply):
    image, run, *_ = delivery
    image()
    assert run(reply)[0].name == 'final.png'


@pytest.mark.parametrize('reply', [
    '```md\n![成品][ref]\n```\n\n[ref]: /work/final.png',
    '    ![成品](/work/final.png)',
    '`![成品](/work/final.png)`',
    '\\![成品](/work/final.png)',
])
def test_code_and_escaped_examples_are_not_images(delivery, reply):
    image, run, *_ = delivery
    image()
    # Escaping only ! creates a valid download link under CommonMark.
    if reply.startswith('\\!'):
        assert run(reply)
    else:
        with pytest.raises(OutputCollectionError, match='final_reply_missing'):
            run(reply)


def test_reference_order_is_display_order_not_definition_order(delivery):
    image, run, *_ = delivery
    image('a.png')
    image('b.png')
    reply = '2. 成品\n\n   ![图][b]\n\n1. 成品\n\n   [下载][a]\n\n[a]: /work/a.png\n[b]: /work/b.png'
    assert [img.name for img in run(reply, 2)] == ['a.png', 'b.png']
