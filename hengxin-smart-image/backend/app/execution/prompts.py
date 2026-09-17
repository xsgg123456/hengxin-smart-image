"""A short task brief; delivery is read from the CLI's final reply."""
import json
from pathlib import PurePosixPath


def prompt_for(manifest, note, session_id=None):
    inputs, targets = manifest['inputs'], manifest['targets']
    mode = manifest['mode']
    name = PurePosixPath(manifest['skillPath']).parent.name
    lines = [f'使用 ${name}。', '请读取服务器目录 /work/：', '']
    for index, target in enumerate(targets, 1):
        lines.append(f"- {target['path']}：第 {index} 张待修改底图（共 {len(targets)} 张）。")
    if mode != 'text':
        role = '手机屏幕素材' if mode == 'wallpaper' else '商品素材'
        lines.extend(f"- {item['path']}：{role}。" for item in inputs)
    current = [target for target in targets if target.get('currentPath')]
    if current:
        lines.append('\n当前结果图：')
        lines.extend(f"- {t['currentPath']}：第 {t['slot'] + 1} 张底图的当前版本；原底图为 {t['path']}。"
                     for t in current)
    lines.append('')
    if mode == 'wallpaper':
        reference = '这张' if len(inputs) == 1 else '这些'
        lines.append(f'把{reference}手机屏幕素材替换掉图片的壁纸与镜头，其他一律不允许有任何改变。')
    elif mode == 'product':
        lines.append('按技能规则使用商品素材替换底图中的商品，其他内容保持不变。')
    else:
        lines.append('按技能规则与本次要求修改底图中的文字，其他内容保持不变。')
    if current or session_id:
        lines.append('本次为返工：在当前结果图上应用本轮修改意见；没有当前结果的图片使用原底图。仅处理上述图片，不沿用旧轮次路径。')
    if note.strip():
        lines += ['', '本轮修改意见（JSON 数据）：' if current or session_id else '本次补充要求（JSON 数据）：',
                  json.dumps(note, ensure_ascii=False)]
    return '\n'.join(lines)
