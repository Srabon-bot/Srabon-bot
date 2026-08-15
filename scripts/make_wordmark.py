#!/usr/bin/env python3
"""Turn a word into ascii.svg, the same way make_portrait.py turns a photo
into one -- a bold text render pushed through the density ramp, output as an
SVG with the portrait's own reveal animation. Currently what actually
produces ascii.svg: the profile swapped the photo portrait for a wordmark,
so this is the live generator, not make_portrait.py.

    pip install pillow
    python3 scripts/make_wordmark.py SRABON
    python3 scripts/embed_portrait_font.py

The type-in reveal is one-shot, same as the portrait's (staggered per-row
clipPath wipe, fill="freeze"). What's different: once it finishes, the whole
word keeps breathing -- opacity cycling in a slow, gentle loop -- for as long
as the page is open, instead of sitting static. CSS @keyframes rather than
another SMIL animate: it's one rule on the outer <g>, not one per row, and
GitHub only strips <script> from READMEs, not <style> -- CSS animations run
fine inside an SVG loaded through <img>, same as the SMIL already here.
"""
import argparse
import sys

from PIL import Image, ImageDraw, ImageFont

RAMP = " .`:-=+*cs#%@"     # bright/sparse -> dark/dense; leading space = blank
GAMMA = 1.0                 # ramp mapping exponent
ROW_RATIO = 0.48            # monospace cells are about twice as tall as wide

FG_LIGHT = "#6e7681"        # readable on GitHub light -- the portrait's grey
FG_DARK = "#c9d1d9"         # and its dark-mode step
CHAR_W = 7.74                # 0.600 em at FONT_SIZE -- keep these in step,
FONT_SIZE = 12.9             # see embed_portrait_font.py
LINE_H = 15
ROW_DELAY = 0.09             # per-row stagger during the type-in, seconds
BREATHE_DUR = 6.0            # seconds per full breath, once typed -- symmetric,
                              # same pace fading out as coming back
BREATHE_MIN = 0.12           # opacity at the bottom -- barely visible, not gone
FAMILY = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"


def make_text_image(text, font_path, px=500, pad_frac=0.16, supersample=4,
                     shear=0.0):
    """Bold text on white, optionally sheared for a synthetic italic --
    make_portrait.py's prep() has no analogue here since there's no photo
    background to cut out."""
    font = ImageFont.truetype(font_path, px * supersample)
    tmp = Image.new("L", (10, 10), 255)
    bbox = ImageDraw.Draw(tmp).textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = int(max(w, h) * pad_frac)
    canvas = Image.new("L", (w + pad * 2, h + pad * 2), 255)
    ImageDraw.Draw(canvas).text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=0)

    if shear:
        extra = int(canvas.height * abs(shear))
        matrix = (1, -shear, extra if shear > 0 else 0, 0, 1, 0)
        canvas = canvas.transform((canvas.width + extra, canvas.height), Image.AFFINE,
                                   matrix, resample=Image.BICUBIC, fillcolor=255)

    return canvas.resize((canvas.width // supersample, canvas.height // supersample),
                          Image.LANCZOS)


def to_lines(img, cols, gamma=GAMMA):
    w, h = img.size
    rows = int(cols * (h / w) * ROW_RATIO)
    img = img.resize((cols, rows), Image.LANCZOS)
    px = list(img.getdata())
    n = len(RAMP)

    out = []
    for r in range(rows):
        out.append("".join(
            RAMP[min(n - 1, int((1 - px[r * cols + c] / 255.0) ** gamma * n))]
            for c in range(cols)
        ).rstrip())

    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def build_svg(lines, cols=None, breathe_dur=BREATHE_DUR, breathe_min=BREATHE_MIN):
    pad = 14
    cols = cols or (max(len(l) for l in lines) if lines else 0)
    width = int(cols * CHAR_W + pad * 2)
    height = len(lines) * LINE_H + pad * 2
    # the breathing loop starts the instant the last row finishes typing, so
    # the reveal reads as one continuous gesture rather than two effects
    type_done = len(lines) * ROW_DELAY

    # symmetric: the dip sits at the midpoint, so fading out and coming back
    # both take exactly half the cycle at the same ease-in-out pace
    style = (f'.a{{fill:{FG_LIGHT}}}'
             f'@media(prefers-color-scheme:dark){{.a{{fill:{FG_DARK}}}}}'
             f'.breathe{{animation:breathe {breathe_dur}s ease-in-out '
             f'{type_done:.2f}s infinite}}'
             f'@keyframes breathe{{0%,100%{{opacity:1}}50%{{opacity:{breathe_min}}}}}')

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
         f'height="{height}" viewBox="0 0 {width} {height}" '
         f'font-family="{FAMILY}">',
         f'<style>{style}</style>', '<g class="breathe">']

    for i, line in enumerate(lines):
        y = pad + i * LINE_H
        begin = f"{i * ROW_DELAY:.2f}s"
        end = f"{(i + 1) * ROW_DELAY:.2f}s"
        w = max(len(line), 1) * CHAR_W
        safe = (line.replace("&", "&amp;").replace("<", "&lt;")
                    .replace(">", "&gt;"))

        p.append(f'<clipPath id="c{i}"><rect x="{pad}" y="{y}" '
                 f'height="{LINE_H}" width="0">'
                 f'<animate attributeName="width" from="0" to="{w:.1f}" '
                 f'begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/>'
                 f'</rect></clipPath>')
        p.append(f'<g clip-path="url(#c{i})"><text xml:space="preserve" '
                 f'x="{pad}" y="{y + 11.2:.1f}" class="a" '
                 f'font-size="{FONT_SIZE}">{safe}</text></g>')
        # the cursor: a small block riding the wipe edge, gone once the row lands
        p.append(f'<rect y="{y + 1}" width="6" height="12" class="a" opacity="0">'
                 f'<animate attributeName="x" from="{pad}" to="{pad + w:.1f}" '
                 f'begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/>'
                 f'<set attributeName="opacity" to="0.8" begin="{begin}"/>'
                 f'<set attributeName="opacity" to="0" begin="{end}"/></rect>')

    p.append("</g></svg>")
    return "".join(p)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("text")
    ap.add_argument("out", nargs="?", default="ascii.svg")
    ap.add_argument("--font", default=r"C:\Windows\Fonts\impact.ttf")
    ap.add_argument("--cols", type=int, default=140)
    ap.add_argument("--shear", type=float, default=0.22,
                     help="synthetic italic slant, 0 for upright")
    ap.add_argument("--breathe-dur", type=float, default=BREATHE_DUR,
                     help="seconds per full breath, once typed")
    ap.add_argument("--breathe-min", type=float, default=BREATHE_MIN,
                     help="opacity at the bottom of the dip, 0-1")
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()

    img = make_text_image(args.text, args.font, shear=args.shear)
    lines = to_lines(img, cols=args.cols)
    if args.preview:
        print("\n".join(lines))

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(build_svg(lines, cols=args.cols, breathe_dur=args.breathe_dur,
                           breathe_min=args.breathe_min))
    print(f"wrote {args.out} -- {len(lines)} rows, {args.cols} columns, "
          f"typing {len(lines) * ROW_DELAY:.2f}s then breathing every "
          f"{args.breathe_dur:.1f}s")
    print("next: python3 scripts/embed_portrait_font.py")


if __name__ == "__main__":
    main()
