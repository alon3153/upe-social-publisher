#!/usr/bin/env python3
"""Burn UPE branding onto a rendered Sofia clip.

Bridges scripts/render_sofia_arcads.py (raw Seedance output) and
scripts/enqueue_sofia.py (expects a publish-ready video), reproducing the look
of the published films: rounded translucent caption cards in the upper third,
the uproduction wordmark top-left, upe.co.il bottom-right.

    python3 scripts/brand_video_overlay.py in.mp4 out.mp4 --batch week2 --ad rome_power
    python3 scripts/brand_video_overlay.py in.mp4 out.mp4 --cards "LINE ONE|LINE TWO" "SECOND CARD"

Cards are spread evenly across the clip unless --timings is given. Cards whose
text starts with a digit followed by a separator render in brand yellow, which
is how the published films mark the numbered fix steps.

Needs ffmpeg: found on PATH, or via the imageio-ffmpeg package as a fallback.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_PATH = os.path.join(ROOT, "assets", "fonts", "Comfortaa[wght].ttf")
LOGO_PATH = os.path.join(ROOT, "assets", "upe_app_icon_1024.png")

BRAND_YELLOW = (251, 206, 10)          # #FBCE0A
WHITE = (255, 255, 255)
CARD_FILL = (40, 40, 40, 150)          # translucent dark slab
W, H = 1080, 1920

CARD_TOP = 340                         # upper third, clear of the logo
CARD_RADIUS = 28
CARD_PAD_X, CARD_PAD_Y = 46, 34
CARD_FONT_SIZE = 62
LINE_SPACING = 14

LOGO_X, LOGO_Y, LOGO_W = 60, 78, 230
SITE_TEXT = "upe.co.il"
SITE_FONT_SIZE = 30
SITE_MARGIN = 58

NUMBERED = re.compile(r"^\s*\d+\s*[·.)\-:]")   # "1 ·", "2.", "3)", "4 -"


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        sys.exit("ffmpeg not found. Install it (brew install ffmpeg / apt install ffmpeg) "
                 "or `pip install imageio-ffmpeg`.")


def font(size, weight="Bold"):
    f = ImageFont.truetype(FONT_PATH, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass  # static build or no variation support; regular weight is acceptable
    return f


def probe(ffmpeg, path):
    """Return (duration_seconds, width, height) for the source clip."""
    out = subprocess.run([ffmpeg, "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", out)
    if not m:
        sys.exit(f"Could not read the duration of {path}")
    h, mnt, s = m.groups()
    duration = int(h) * 3600 + int(mnt) * 60 + float(s)
    dims = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", out)
    if not dims:
        sys.exit(f"Could not read the video dimensions of {path}")
    return duration, int(dims.group(1)), int(dims.group(2))


def wordmark():
    """The app-icon asset is the wordmark on white. Key out the white and
    recolour the near-black glyphs to white for the light-on-dark video lockup,
    leaving the yellow as it is."""
    im = Image.open(LOGO_PATH).convert("RGBA")
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, _ = px[x, y]
            if r > 238 and g > 238 and b > 238:
                px[x, y] = (0, 0, 0, 0)
            elif r < 110 and g < 110 and b < 110:
                px[x, y] = WHITE + (255,)
    im = im.crop(im.getbbox())
    return im.resize((LOGO_W, max(1, round(LOGO_W * im.height / im.width))), Image.LANCZOS)


def draw_card(layer, text, mark):
    lines = text.split("\n")
    fnt = font(CARD_FONT_SIZE)
    d = ImageDraw.Draw(layer)
    widths, heights = [], []
    for ln in lines:
        box = d.textbbox((0, 0), ln, font=fnt)
        widths.append(box[2] - box[0])
        heights.append(box[3] - box[1])
    text_w = max(widths)
    line_h = max(heights)
    block_h = line_h * len(lines) + LINE_SPACING * (len(lines) - 1)

    card_w = min(text_w + CARD_PAD_X * 2, W - 80)
    card_h = block_h + CARD_PAD_Y * 2
    x0 = (W - card_w) // 2
    d.rounded_rectangle([x0, CARD_TOP, x0 + card_w, CARD_TOP + card_h],
                        radius=CARD_RADIUS, fill=CARD_FILL)

    colour = BRAND_YELLOW if NUMBERED.match(lines[0]) else WHITE
    y = CARD_TOP + CARD_PAD_Y
    for i, ln in enumerate(lines):
        box = d.textbbox((0, 0), ln, font=fnt)
        d.text(((W - (box[2] - box[0])) // 2 - box[0], y - box[1]), ln, font=fnt, fill=colour)
        y += line_h + LINE_SPACING
    layer.alpha_composite(mark, (LOGO_X, LOGO_Y))

    sf = font(SITE_FONT_SIZE, "Regular")
    sbox = d.textbbox((0, 0), SITE_TEXT, font=sf)
    d.text((W - (sbox[2] - sbox[0]) - SITE_MARGIN, H - (sbox[3] - sbox[1]) - SITE_MARGIN),
           SITE_TEXT, font=sf, fill=(255, 255, 255, 225))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("output")
    ap.add_argument("--batch", default="week2")
    ap.add_argument("--ad", help="ad id in content/sofia/prompts/<batch>.json")
    ap.add_argument("--cards", nargs="*", help="card text; use | between lines")
    ap.add_argument("--timings", help="comma-separated start,end pairs in seconds per card")
    ap.add_argument("--keep-frames", action="store_true", help="leave the overlay PNGs on disk")
    args = ap.parse_args()

    if not os.path.exists(args.source):
        sys.exit(f"No such file: {args.source}")
    if not os.path.exists(FONT_PATH):
        sys.exit(f"Missing brand font at {FONT_PATH}")

    if args.cards:
        cards = [c.replace("|", "\n") for c in args.cards]
    elif args.ad:
        spec = json.load(open(os.path.join(ROOT, "content", "sofia", "prompts",
                                           f"{args.batch}.json"), encoding="utf-8"))
        match = [a for a in spec["ads"] if a["id"] == args.ad]
        if not match:
            sys.exit(f"No ad '{args.ad}' in batch {args.batch}")
        cards = match[0]["overlay_cards"]
    else:
        sys.exit("Pass --ad <id> or --cards ...")

    ffmpeg = find_ffmpeg()
    duration, src_w, src_h = probe(ffmpeg, args.source)

    if args.timings:
        nums = [float(x) for x in args.timings.split(",")]
        if len(nums) != 2 * len(cards):
            sys.exit(f"--timings needs {2 * len(cards)} numbers for {len(cards)} cards")
        spans = list(zip(nums[0::2], nums[1::2]))
    else:
        step = duration / len(cards)
        spans = [(i * step, (i + 1) * step) for i in range(len(cards))]

    mark = wordmark()
    tmp = tempfile.mkdtemp(prefix="upe-overlay-")
    pngs = []
    for i, text in enumerate(cards):
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_card(layer, text, mark)
        path = os.path.join(tmp, f"card{i}.png")
        layer.save(path)
        pngs.append(path)

    cmd = [ffmpeg, "-y", "-i", args.source]
    for p in pngs:
        cmd += ["-i", p]
    steps, prev = [], "[0:v]"
    for i, (start, end) in enumerate(spans):
        # Overlays are authored at 1080x1920; scale to the source's real size.
        steps.append(f"[{i + 1}:v]scale={src_w}:{src_h}[c{i}]")
        label = f"[v{i}]" if i < len(spans) - 1 else "[vout]"
        steps.append(f"{prev}[c{i}]overlay=0:0:enable='between(t,{start:.2f},{end:.2f})'{label}")
        prev = f"[v{i}]"
    cmd += ["-filter_complex", ";".join(steps), "-map", "[vout]"]
    cmd += ["-map", "0:a?", "-c:a", "copy", "-c:v", "libx264", "-preset", "medium",
            "-crf", "18", "-pix_fmt", "yuv420p", args.output]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit("ffmpeg failed:\n" + res.stderr[-1500:])

    if not args.keep_frames:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print(f"Overlay PNGs kept in {tmp}")

    print(f"Wrote {args.output}  ({len(cards)} cards over {duration:.1f}s)")
    for (start, end), text in zip(spans, cards):
        print(f"  {start:5.1f}-{end:5.1f}s  {text.splitlines()[0]}")


if __name__ == "__main__":
    main()
