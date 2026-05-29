#!/usr/bin/env python3
"""UPE branded post compositor — real photo bg + pixel-perfect logo/text overlay."""
import argparse, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BRAND_DARK = (28, 28, 28)      # #1C1C1C
BRAND_YELLOW = (251, 206, 10)  # #FBCE0A
FONT_DIR = "/Users/alonouanine/Library/CloudStorage/Dropbox-UproductionEvents/Alon ouaknine/Uproduction Brand/Branding/מיתוג מחדש 2019 גיתם/font/Comfortaa/static"
LOGO_SRC = "/Users/alonouanine/Library/CloudStorage/Dropbox-UproductionEvents/Alon ouaknine/Uproduction Brand/Branding/uproduction_logo_1024x1024.png"
S = 1080


def key_black(img, thresh=45):
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r < thresh and g < thresh and b < thresh:
                px[x, y] = (r, g, b, 0)
    return img


def crop_square(im):
    w, h = im.size
    m = min(w, h)
    im = im.crop(((w - m) // 2, (h - m) // 2, (w - m) // 2 + m, (h - m) // 2 + m))
    return im.resize((S, S), Image.LANCZOS)


def bottom_gradient(strength=238, start=0.42):
    grad = Image.new("L", (1, S), 0)
    for y in range(S):
        t = (y / S - start) / (1 - start)
        grad.putpixel((0, y), 0 if t < 0 else int(min(1, t) ** 1.15 * strength))
    grad = grad.resize((S, S))
    layer = Image.new("RGBA", (S, S), BRAND_DARK + (0,))
    layer.putalpha(grad)
    return layer


def top_scrim(strength=120, end=0.22):
    grad = Image.new("L", (1, S), 0)
    for y in range(S):
        t = 1 - (y / S) / end
        grad.putpixel((0, y), 0 if t < 0 else int(min(1, t) * strength))
    grad = grad.resize((S, S))
    layer = Image.new("RGBA", (S, S), BRAND_DARK + (0,))
    layer.putalpha(grad)
    return layer


def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bg", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lines", required=True, help="headline lines separated by |")
    ap.add_argument("--accent", default="", help="word to color yellow")
    ap.add_argument("--site", default="upe.co.il")
    a = ap.parse_args()

    base = crop_square(Image.open(a.bg)).convert("RGBA")
    base = Image.alpha_composite(base, top_scrim())
    base = Image.alpha_composite(base, bottom_gradient())
    draw = ImageDraw.Draw(base)

    # logo top-left
    logo = key_black(Image.open(LOGO_SRC))
    bbox = logo.getbbox()
    logo = logo.crop(bbox)
    lw = 250
    lh = int(logo.height * lw / logo.width)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    base.alpha_composite(logo, (60, 56))

    # headline
    lines = a.lines.split("|")
    f_head = font("Comfortaa-Bold.ttf", 70)
    lh_head = 92
    total_h = lh_head * len(lines)
    y = S - 150 - total_h
    # yellow accent line
    draw.rectangle([60, y - 34, 60 + 70, y - 28], fill=BRAND_YELLOW)
    for line in lines:
        x = 60
        for i, word in enumerate(line.split(" ")):
            w = word + (" " if i < len(line.split(" ")) - 1 else "")
            col = BRAND_YELLOW if a.accent and a.accent.lower() in word.lower() else (255, 255, 255)
            draw.text((x, y), w, font=f_head, fill=col)
            x += draw.textlength(w, font=f_head)
        y += lh_head

    # site bottom-right
    f_site = font("Comfortaa-Medium.ttf", 30)
    tw = draw.textlength(a.site, font=f_site)
    draw.text((S - 60 - tw, S - 72), a.site, font=f_site, fill=(255, 255, 255, 220))

    base.convert("RGB").save(a.out, quality=95)
    print("saved", a.out)


if __name__ == "__main__":
    main()
