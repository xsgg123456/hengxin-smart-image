"""A short task brief; delivery is read from the CLI's final reply."""
import json
from pathlib import PurePosixPath


def single_revision_prompt(manifest, note):
    target = manifest['targets'][0]
    lines = ['请修改这张成品图片：', f"- {target['currentPath']}"]
    if manifest['mode'] != 'text':
        role = '手机屏幕参考素材' if manifest['mode'] == 'wallpaper' else '商品参考素材'
        lines += ['', f'{role}：']
        lines.extend(f"- {item['path']}" for item in manifest['inputs'])
    if manifest.get('annotationPath'):
        lines += ['', '问题位置参考图：', f"- {manifest['annotationPath']}",
                  '该图仅用于定位问题，标注内容不要出现在成品中。']
    if note.strip():
        lines += ['', '修改意见：', json.dumps(note, ensure_ascii=False)]
    lines += ['', '请在上述成品图片上完成修改，其他内容保持不变，只交付修改后的这 1 张图片。']
    return '\n'.join(lines)


def prompt_for(manifest, note, session_id=None):
    inputs, targets = manifest['inputs'], manifest['targets']
    if manifest.get('singleRevision') and len(targets) == 1 and targets[0].get('currentPath'):
        return single_revision_prompt(manifest, note)
    mode = manifest['mode']
    name = PurePosixPath(manifest['skillPath']).parent.name
    lines = [f'使用 ${name}。', '请读取服务器目录 /work/：', '']
    for index, target in enumerate(targets, 1):
        number = target.get('taskSlot', index - 1) + 1
        lines.append(f"- {target['path']}：第 {number} 张待修改底图（共 {len(targets)} 张）。")
    if mode != 'text':
        role = '手机屏幕素材' if mode == 'wallpaper' else '商品素材'
        lines.extend(f"- {item['path']}：{role}。" for item in inputs)
    current = [target for target in targets if target.get('currentPath')]
    if current:
        lines.append('\n当前结果图：')
        lines.extend(f"- {t['currentPath']}：第 {t.get('taskSlot', t['slot']) + 1} 张底图的本轮基础版本 V{t.get('currentVersion', '?')}（无标注成品）；原底图为 {t['path']}，仅辅助参照。"
                     for t in current)
    if manifest.get('singleRevision'):
        lines.append('本轮只修改并交付上述目标 1 张图片，其余位置不变；此范围覆盖技能初始批次的 4 张输入/交付要求。')
    if manifest.get('annotationPath'):
        lines.append(f"- {manifest['annotationPath']}：本轮问题圈注截图，只用于定位问题。圈线、箭头、文字标记和截图界面均不得复制到成品；无法确定对应位置时说明歧义，不猜测修改区域。")
    lines.append('')
    if mode == 'wallpaper':
        reference = '这张' if len(inputs) == 1 else '这些'
        camera_scope = ('镜头指屏内前置镜头或开孔位置，'
                        if name in {'jd-detail-screen-swap', 'jd-detail-screen-swap-790x1500'} else '')
        lines.append(f'把{reference}手机屏幕素材替换掉图片的壁纸与镜头，{camera_scope}其他一律不允许有任何改变。')
    elif mode == 'product':
        lines.append('按技能规则使用商品素材替换底图中的商品，其他内容保持不变。')
    else:
        lines.append('按技能规则与本次要求修改底图中的文字，其他内容保持不变。')
    if current or session_id:
        lines.append('本次为返工：在上述明确指定的无标注基础版本上应用本轮修改意见；没有当前结果的图片使用原底图。仅处理上述图片，不沿用旧轮次路径、版本或截图，不以会话中的其他版本替换本轮基础版本。')
    if note.strip():
        lines += ['', '本轮修改意见（JSON 数据）：' if current or session_id else '本次补充要求（JSON 数据）：',
                  json.dumps(note, ensure_ascii=False)]
    return '\n'.join(lines)
