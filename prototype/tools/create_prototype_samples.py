"""Code-native SVG product mockups for interaction demonstrations, not AI output."""
from pathlib import Path
root = Path(__file__).resolve().parents[1] / 'source/public/samples'
root.mkdir(parents=True, exist_ok=True)
palettes = [('#e8eaf0','#8b9cae','#414e69'), ('#eadfd2','#b6937c','#65594e'), ('#dce8e4','#83a396','#344e4d'), ('#e1e5f1','#858cae','#444c74')]
for mode in ['wallpaper','product','text']:
    for i, (bg, mid, dark) in enumerate(palettes):
        title = ['让屏幕，遇见新风景','每一面，都有好风景','把山川握在掌心','留住纯粹的光影'][i] if mode == 'wallpaper' else ['轻薄，从容保护','清晰，看见每一处','贴合，不止于表面','原色呈现 自然通透'][i] if mode == 'product' else ['新品上市','轻薄好手感','高清 · 高透 · 高品质','为每一次出发而设计'][i]
        phone = f'''<g transform="translate({190 if i%2==0 else 175} 160) rotate({-12 if i%2==0 else 10} 110 190)">
        <rect x="-7" y="-6" width="227" height="385" rx="39" fill="url(#metal)" filter="url(#shadow)"/>
        <rect width="213" height="372" rx="33" fill="#131924"/>
        <rect x="7" y="7" width="199" height="358" rx="27" fill="url(#screen)"/>
        <path d="M7 223 Q55 140 110 221 T206 180 V330 Q204 366 178 365 H34 Q7 365 7 338Z" fill="{mid}" opacity=".9"/>
        <path d="M7 297 Q57 214 106 287 T206 247 V338 Q205 365 177 365 H32 Q7 365 7 338Z" fill="{dark}"/>
        <rect x="72" y="15" width="68" height="18" rx="10" fill="#151a20"/>
        <path d="M18 46 V315" stroke="#fff" stroke-opacity=".35" stroke-width="2"/>
        <text x="106" y="91" text-anchor="middle" fill="#fff" font-size="38" font-family="Arial">09:41</text>
        </g>'''
        if mode == 'product':
            phone += '''<g transform="translate(120 215) rotate(-18 80 150)"><rect width="175" height="303" rx="26" fill="#ffffff" fill-opacity=".19" stroke="#ffffff" stroke-width="3"/><rect x="5" y="5" width="165" height="293" rx="23" fill="none" stroke="#87939f" stroke-opacity=".6"/><path d="M18 280 L146 24" stroke="#fff" stroke-opacity=".7" stroke-width="4"/></g>'''
        svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="660" viewBox="0 0 600 660">
        <defs><linearGradient id="bg" x2=".8" y2="1"><stop stop-color="{bg}"/><stop offset="1" stop-color="#fbfbf9"/></linearGradient><linearGradient id="screen" x2=".7" y2="1"><stop stop-color="{bg}"/><stop offset="1" stop-color="{mid}"/></linearGradient><linearGradient id="metal"><stop stop-color="#c8cdd2"/><stop offset=".4" stop-color="#f2f3f5"/><stop offset="1" stop-color="#777e87"/></linearGradient><filter id="shadow" x="-80%" y="-40%" width="260%" height="220%"><feDropShadow dx="14" dy="24" stdDeviation="20" flood-color="{dark}" flood-opacity=".23"/></filter></defs>
        <rect width="600" height="660" fill="url(#bg)"/><circle cx="540" cy="370" r="220" fill="#fff" opacity=".35"/>
        <text x="42" y="46" fill="{dark}" font-size="11" letter-spacing="3" font-family="Arial">HENGXIN / ESSENTIAL COLLECTION</text>
        <text x="42" y="94" fill="{dark}" font-size="29" font-weight="600" font-family="Microsoft YaHei, sans-serif">{title}</text>
        <text x="43" y="120" fill="{dark}" opacity=".7" font-size="11" letter-spacing="2" font-family="Arial">DESIGNED FOR YOUR EVERYDAY</text>
        <ellipse cx="310" cy="559" rx="168" ry="22" fill="{dark}" opacity=".08"/>{phone}
        <line x1="42" y1="594" x2="558" y2="594" stroke="{dark}" opacity=".18"/>
        <text x="42" y="624" fill="{dark}" font-size="12" font-family="Microsoft YaHei, sans-serif">{['屏幕壁纸 · 质感展示','高清钢化膜 · 产品展示','商品文案 · 文字展示'][['wallpaper','product','text'].index(mode)]}</text><text x="558" y="624" text-anchor="end" fill="{dark}" font-size="10" font-family="Microsoft YaHei, sans-serif">原型示例 / {i+1:02}</text></svg>'''
        (root/f'{mode}-{i}.svg').write_text(svg,encoding='utf-8')
