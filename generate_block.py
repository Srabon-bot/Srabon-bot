import os

lines = [
    '███████╗██╗  ██╗ █████╗ ██╗  ██╗██████╗ ██╗ █████╗ ██████╗     ███████╗██████╗  █████╗ ██████╗  ██████╗ ███╗   ██╗',
    '██╔════╝██║  ██║██╔══██╗██║  ██║██╔══██╗██║██╔══██╗██╔══██╗    ██╔════╝██╔══██╗██╔══██╗██╔══██╗██╔═══██╗████╗  ██║',
    '███████╗███████║███████║███████║██████╔╝██║███████║██████╔╝    ███████╗██████╔╝███████║██████╔╝██║   ██║██╔██╗ ██║',
    '╚════██║██╔══██║██╔══██║██╔══██║██╔══██╗██║██╔══██║██╔══██╗    ╚════██║██╔══██╗██╔══██║██╔══██╗██║   ██║██║╚██╗██║',
    '███████║██║  ██║██║  ██║██║  ██║██║  ██║██║██║  ██║██║  ██║    ███████║██║  ██║██║  ██║██████╔╝╚██████╔╝██║ ╚████║',
    '╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═╝╚═╝  ╚═╝    ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝  ╚═════╝ ╚═╝  ╚═══╝'
]

# Use a standard font stack that supports box drawing well without letter-spacing issues
FAMILY = "Consolas, 'Courier New', monospace"
FONT_SIZE = 12
LINE_H = 15
CHAR_W = 7.2  # approximate width for monospace 12px
ROW_DELAY = 0.09
BREATHE_DUR = 6.0
BREATHE_MIN = 0.12

pad = 14
cols = max(len(l) for l in lines)
width = int(cols * CHAR_W + pad * 2)
height = len(lines) * LINE_H + pad * 2
type_done = len(lines) * ROW_DELAY

style = (f'.a{{fill:#6e7681}}'
         f'@media(prefers-color-scheme:dark){{.a{{fill:#c9d1d9}}}}'
         f'.breathe{{animation:breathe {BREATHE_DUR}s ease-in-out '
         f'{type_done:.2f}s infinite}}'
         f'@keyframes breathe{{0%,100%{{opacity:1}}50%{{opacity:{BREATHE_MIN}}}}}')

p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
     f'height="{height}" viewBox="0 0 {width} {height}" '
     f'font-family="{FAMILY}">',
     f'<style>{style}</style>', '<g class="breathe">']

for i, line in enumerate(lines):
    y = pad + i * LINE_H
    begin = f"{i * ROW_DELAY:.2f}s"
    end = f"{(i + 1) * ROW_DELAY:.2f}s"
    w = max(len(line), 1) * CHAR_W
    safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    p.append(f'<clipPath id="c{i}"><rect x="{pad}" y="{y}" '
             f'height="{LINE_H+2}" width="0">'
             f'<animate attributeName="width" from="0" to="{w:.1f}" '
             f'begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/>'
             f'</rect></clipPath>')
    p.append(f'<g clip-path="url(#c{i})"><text xml:space="preserve" '
             f'x="{pad}" y="{y + 11}" class="a" '
             f'font-size="{FONT_SIZE}" font-weight="bold">{safe}</text></g>')
    p.append(f'<rect y="{y+1}" width="6" height="{LINE_H}" class="a" opacity="0">'
             f'<animate attributeName="x" from="{pad}" to="{pad + w:.1f}" '
             f'begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/>'
             f'<set attributeName="opacity" to="0.8" begin="{begin}"/>'
             f'<set attributeName="opacity" to="0" begin="{end}"/></rect>')

p.append("</g></svg>")

with open('ascii.svg', 'w', encoding='utf-8') as f:
    f.write("".join(p))
