"""Rebuild the approved Hengxin identity. Usage: python build_vectors.py FONT.otf"""
from pathlib import Path
import sys

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen

ROOT = Path(__file__).resolve().parents[1]
FONT = TTFont(sys.argv[1])
GLYPHS = FONT.getGlyphSet()
CMAP = FONT.getBestCmap()
EM = FONT['head'].unitsPerEm

# Geometry redrawn from approved-concept.png; all versions share this silhouette.
OUTLINE = ('M135 52Q135 48 131 50L25 111Q22 113 22 118V262Q22 267 27 270'
           'L99 311Q106 315 106 307V230H221V246L191 264Q188 266 188 270V340'
           'Q188 348 195 344L302 282Q307 279 307 273V140Q307 134 302 131'
           'L229 88Q221 83 221 91V174H106V158L132 143Q135 141 135 137Z')
PIXEL = ('M296 20Q300 16 304 20L341 57Q345 61 341 65L304 102'
         'Q300 106 296 102L259 65Q255 61 259 57Z')


def mark(white=False, small=False):
    color = '#FFFFFF' if white else '#F1362F'
    pixel = '#FFFFFF' if white else '#FF9A16'
    body = f'<path fill="{color}" d="{OUTLINE}"/>'
    if not white and not small:
        body += ('<path fill="#D92D27" d="M22 262L106 194V230H221V174'
                 'L307 273V275L221 230H106V307Q106 315 99 311L27 270Q22 267 22 262Z"/>')
    return body + f'<path fill="{pixel}" d="{PIXEL}"/>'


def lettering(text, x, baseline, size, color, spacing=0):
    paths = []
    scale = size / EM
    for char in text:
        glyph = GLYPHS[CMAP[ord(char)]]
        pen = SVGPathPen(GLYPHS)
        glyph.draw(pen)
        paths.append(f'<path transform="translate({x:.3f} {baseline}) scale({scale:.5f} {-scale:.5f})" d="{pen.getCommands()}"/>')
        x += glyph.width * scale + spacing
    return f'<g fill="{color}">' + ''.join(paths) + '</g>'


def svg(width, height, content, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{label}">\n'
            f'<title>{label}</title>\n{content}\n</svg>\n')


def save(name, width, height, content, label='恒鑫智图'):
    (ROOT / f'{name}.svg').write_text(svg(width, height, content, label), encoding='utf-8')


for name, white, small in [('mark', False, False), ('mark-small', False, True), ('mark-white', True, True)]:
    save(name, 360, 360, mark(white, small))

for white in (False, True):
    suffix = '-white' if white else ''
    ink, secondary = ('#FFFFFF', '#D9DCE3') if white else ('#20242D', '#707782')
    content = '<g transform="translate(4 10) scale(.5)">' + mark(white) + '</g>'
    content += lettering('恒鑫智图', 210, 114, 80, ink, 4)
    content += lettering('京东业务生图', 214, 165, 25, secondary, 9)
    save('logo-horizontal' + suffix, 570, 200, content, '恒鑫智图 · 京东业务生图')
    content = '<g transform="translate(0 3) scale(.25)">' + mark(white) + '</g>'
    content += lettering('恒鑫智图', 108, 70, 54, ink, 2)
    save('logo-compact' + suffix, 340, 96, content)

save('app-icon', 512, 512, '<rect width="512" height="512" rx="108" fill="#FAFAFA"/>'
     '<g transform="translate(58 58) scale(1.1)">' + mark() + '</g>')
save('app-icon-dark', 512, 512, '<rect width="512" height="512" rx="108" fill="#20242D"/>'
     '<g transform="translate(58 58) scale(1.1)">' + mark(True) + '</g>')

# The favicon includes safe space; small version omits folds but preserves the H.
save('favicon', 64, 64, '<g transform="translate(1 1) scale(.1722)">' + mark(small=True) + '</g>')
print('Built 10 self-contained SVG assets (text converted to paths).')
