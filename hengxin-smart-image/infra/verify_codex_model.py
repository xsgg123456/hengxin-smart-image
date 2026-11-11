"""Opt-in, bounded real model verification using the worker's existing credential broker."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', required=True)
    parser.add_argument('--side', choices=['domestic', 'overseas'], required=True)
    parser.add_argument('--pptx')
    parser.add_argument('--skill')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise RuntimeError('Run as the actual worker user')
    sys.path.insert(0, args.backend)
    from app.core.config import get_settings
    from app.execution.workspace import prepare_workspace, sandbox_command
    from app.execution.managed_credentials import sync_credentials
    from app.execution.process import execute
    from app.execution.events import parse_events
    from app.overseas.studio.execution import StudioProtocol
    from app.overseas.studio.delivery import collect_delivery
    from PIL import Image
    settings = get_settings()
    if not settings.codex_auth_broker_socket:
        raise RuntimeError('Use the existing managed account broker')
    output = Path(args.output)
    output.mkdir(mode=0o700)
    marker = 'HX-RUNTIME-' + uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix='hx-model-runtime-') as temporary:
        identity = uuid4()
        ws = prepare_workspace(temporary, identity, uuid4(), None, copy_auth=False)
        ws.use_skill = bool(args.skill)
        if args.skill:
            ws.local_skill = Path(args.skill)
            ws.skill_name = ws.local_skill.name
        ws.previous_session = None
        ws.baseline = {}
        if args.side == 'overseas':
            if not args.pptx:
                raise ValueError('PPT fixture required')
            shutil.copyfile(args.pptx, ws.work / 'product.pptx')
            prompt = ('这是内网执行环境修复验收，已授权读取附件和本地工具，无需向用户询问。'
                '请实际调用命令工具读取 /work/product.pptx：用Python zipfile/XML提取全部页面文字和媒体，'
                '用已安装的libreoffice转为 /work/product.pdf，再用pdftoppm输出 /work/page-1.png、'
                '/work/page-2.png，并用图片查看工具实际查看两页。'
                '若有挂载Skill，先用命令实际读取其SKILL.md。只检查附件，不生成新图，不访问外部连接器。'
                '最后中文报告总页数、媒体数、逐页主要文字与图示，并写 /work/model-evidence.json '
                '包含 pages、media、marker 字段，其中 marker='+marker+'。请记住这个marker供下一轮验证。')
        else:
            Image.new('RGB', (256, 256), (20, 80, 180)).save(ws.work / 'input.png')
            prompt = ('这是国内图片修改执行环境的授权验收。先实际用命令工具执行Python和Node，'
                '读取 /work/input.png 的尺寸并用图片查看工具查看；然后用原生图片编辑工具引用此图，'
                '只生成一张修改图：保留蓝色背景，中心加一个白色圆。不要用Python/SVG代替这一步。'
                '最终交付生成图片的实际Markdown链接，并说明原图尺寸；将验证标记 '+marker+
                ' 写入 /work/domestic-marker.txt。不要读取凭据、环境变量或业务数据库。')
        sync_credentials(Path(settings.codex_auth_file), ws.home, 360,
                         broker_socket=settings.codex_auth_broker_socket, control=ws.control.parent)
        auth = json.loads((ws.home / '.codex' / 'auth.json').read_text())
        assert not auth.get('tokens', {}).get('refresh_token')
        command = sandbox_command(ws, settings.codex_binary, StudioProtocol().arguments(ws), settings.codex_bwrap_binary)
        receipt = execute(command, prompt, ws.control, 360, lambda: False, lambda *a: None)
        summary = parse_events(ws.control / 'events.jsonl')
        (output / 'reply.txt').write_text(summary.final_text or '')
        shutil.copyfile(ws.control / 'events.jsonl', output / 'events.jsonl')
        shutil.copyfile(ws.control / 'stderr.log', output / 'stderr.log')
        if receipt['exit_code'] or receipt['reason'] or summary.error or not summary.turn_completed:
            raise RuntimeError('Real model execution did not complete')
        report = {'side': args.side, 'uid': os.geteuid(), 'session': summary.session_id,
                  'receipt': receipt, 'access_only_credentials': True}
        # Preserve tool evidence, excluding credential files and generic discovery dumps.
        evidence = []
        for file in (ws.home / '.codex' / 'sessions').rglob('*.jsonl'):
            for line in file.read_text().splitlines():
                record = json.loads(line)
                payload = record.get('payload', {})
                if record.get('type') == 'turn_context':
                    evidence.append({'type':'model', 'model':payload.get('model'), 'effort':payload.get('effort')})
                if payload.get('type') in ('custom_tool_call','custom_tool_call_output','function_call','function_call_output'):
                    value = {k:payload[k] for k in ('type','name','input','output','arguments','call_id') if k in payload}
                    if len(json.dumps(value)) < 12000:
                        evidence.append(value)
        (output / 'tools.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
        assert any(e.get('type') in ('custom_tool_call','function_call') for e in evidence)
        calls = '\n'.join(json.dumps(e, ensure_ascii=False) for e in evidence
                          if e.get('type') in ('custom_tool_call','function_call'))
        assert 'view_image' in calls, 'Actual image viewing call missing'
        if args.side == 'overseas':
            result = json.loads((ws.work / 'model-evidence.json').read_text())
            assert result['pages'] == 2 and result['media'] == 2 and result['marker'] == marker
            info = subprocess.run(['pdfinfo', str(ws.work / 'product.pdf')], capture_output=True,
                                  text=True, check=True, timeout=15)
            assert any(line.split() == ['Pages:', '2'] for line in info.stdout.splitlines())
            shutil.copyfile(ws.work / 'product.pdf', output / 'product.pdf')
            for number in (1, 2):
                page = ws.work / f'page-{number}.png'
                with Image.open(page) as im:
                    im.load()
                    assert min(im.size) > 300
                shutil.copyfile(page, output / page.name)
            assert 'product.pptx' in calls and 'pdftoppm' in calls and 'libreoffice' in calls
            if args.skill:
                assert 'SKILL.md' in calls
            report['ppt'] = result
            # Resume the same session and prove private context can be read again.
            resumed = prepare_workspace(temporary, identity, uuid4(), None, copy_auth=False)
            resumed.use_skill = False
            resumed.work = ws.work
            resumed.previous_session = summary.session_id
            sync_credentials(Path(settings.codex_auth_file), resumed.home, 120,
                broker_socket=settings.codex_auth_broker_socket, control=resumed.control.parent, require_existing=True)
            command = sandbox_command(resumed, settings.codex_binary, StudioProtocol().arguments(resumed), settings.codex_bwrap_binary)
            again = execute(command, '读取 /work/model-evidence.json 并回复上一轮marker，只回复marker。',
                            resumed.control, 120, lambda: False, lambda *a: None)
            second = parse_events(resumed.control / 'events.jsonl', summary.session_id)
            shutil.copyfile(resumed.control / 'events.jsonl', output / 'resume-events.jsonl')
            resumed_tools = []
            for file in (resumed.home / '.codex' / 'sessions').rglob('*.jsonl'):
                for line in file.read_text().splitlines():
                    payload = json.loads(line).get('payload', {})
                    if payload.get('type') in ('custom_tool_call','custom_tool_call_output','function_call','function_call_output'):
                        if len(json.dumps(payload)) < 12000:
                            resumed_tools.append(payload)
            (output / 'resume-tools.json').write_text(json.dumps(resumed_tools, ensure_ascii=False, indent=2))
            assert again['exit_code'] == 0 and not again['reason'] and second.turn_completed and not second.error
            assert second.session_id == summary.session_id and marker in second.final_text
            report['same_session_resume'] = True
        else:
            assert (ws.work / 'domestic-marker.txt').read_text().strip() == marker
            assert 'imagegen' in calls and 'referenced_image_paths' in calls and '/work/input.png' in calls
            images, warnings = collect_delivery(ws, summary)
            images = [(path, file) for path, file in images if file.content_type.startswith('image/')]
            assert len(images) == 1 and not warnings, {'count':len(images), 'warnings':warnings}
            picture = images[0][1]
            (output / 'domestic-result.png').write_bytes(picture.data)
            report['image'] = {'count':1, 'width':picture.width, 'height':picture.height}
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
