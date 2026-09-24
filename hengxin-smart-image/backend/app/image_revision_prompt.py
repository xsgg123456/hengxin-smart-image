"""Shared single-image repair brief, adapted to paths or API image positions."""
import json


REVISION_POLICY_VERSION = 'single-image-reference-v2'

ANNOTATION_GUIDANCE = (
    '参考图可能是当前成品上的标注，也可能是用户上传的已有截图，请结合当前成品核对对应位置。'
    '矩形框、自由画笔圈线和编号仅用于定位问题，不是像素蒙版，不代表框外或圈外像素绝对不变；这些标记不得进入成品。'
    '框选不表示替换框内全部内容，画笔圈线不表示需要绘制的成品线条；具体修改以对应文字意见为准，继续以无标注成品为基础。'
    '图中存在编号时，按用户修改意见中的对应编号逐项处理；没有编号时，按实际标记和文字意见定位，不自行假定编号。'
    '无法确定对应位置或编号意见时，如实说明歧义，不猜测修改区域。')


def build_revision_prompt(*, current, original, materials, note, annotation=None, api=False):
    material_title = '共用参考素材' if api else '手机屏幕素材'
    material_purpose = (
        '用于核对已替换内容的外观、细节、位置和比例。涉及手机屏幕替换时，用于核对新壁纸及屏内前置镜头或开孔。'
        if api else '用于核对新壁纸及屏内前置镜头或开孔的内容、位置和比例。')
    reference_rule = (
        '需要还原原有细节时，对照原始底图；需要修正替换内容时，对照共用参考素材。不要恢复原始底图中已经被替换的旧内容，也不要撤销此前已确认且与本次问题无关的修改。'
        if api else
        '需要还原原有细节时，对照原始底图；需要修正壁纸或屏内开孔时，对照手机屏幕素材。不要恢复旧壁纸，也不要撤销此前已确认且与本次问题无关的修改。')
    delivery_rule = (
        '保持当前成品的构图和其他内容，仅按本次要求修改。标注和参考图片不得作为额外画面拼入成品。只输出修改后的1张完整成品图片，不输出对比图、拼图或参考图。'
        if api else
        '保持当前成品的画布尺寸和其他内容。完成后只展示并提供修改后的这1张成品图片；若仍有无法解决的问题，如实说明，不将未解决的问题表述为已修复。')
    lines = ['请根据本次修改意见，修改下面这张成品图片。', '',
             '当前成品：', f'- {current}',
             '这是本次唯一修改对象，请以此版本为基础。', '',
             '对应原始底图：', f'- {original}',
             '用于对照本次问题涉及的原有结构、边缘、遮挡和光影细节。', '',
             f'{material_title}：']
    lines.extend(f'- {reference}' for reference in materials)
    lines.append(material_purpose)
    if annotation:
        lines += ['', '问题位置参考图：', f'- {annotation}',
                  '仅用于定位问题，图中的圈线、箭头、文字标记及截图界面不得进入成品。',
                  ANNOTATION_GUIDANCE]
    if note.strip():
        lines += ['', '本次修改意见：', json.dumps(note, ensure_ascii=False)]
    elif api and annotation:
        lines += ['', '本次修改意见：',
                  f'本次未提供文字修改意见，请结合{annotation}的标注定位问题，并对照当前成品、原始底图和共用参考素材完成相关区域的修正。不要将标注本身视为需要添加到成品中的内容。']
    lines += ['', '修改要求：',
              '1. 优先解决本次指出的问题，只调整相关区域及必要的衔接部分，保留当前成品中其他已完成的内容。',
              f'2. {reference_rule}',
              '3. 输出前，将修复位置及周边交界与原始底图、当前成品进行对照，确认本次问题得到改善，且没有引入明显的漏贴、接缝、变形或遮挡错误。发现明确缺陷时继续局部修复，不因无关的细微疑虑反复重做整张图。',
              f'4. {delivery_rule}']
    return '\n'.join(lines)
