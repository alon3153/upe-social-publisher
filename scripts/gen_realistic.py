#!/usr/bin/env python3
"""
UPE realistic image refresh — photoreal base (Higgsfield) + UPE brand overlay.
This module holds the per-day prompt map, headline text, slug map, and the
brand overlay renderer. Generation of bases is driven externally (MCP); this
script's overlay() is called on downloaded base PNGs.
"""
import os, textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO = os.path.join(ROOT, "..", "..", "Uproduction Brand", "Branding", "uproduction_logo_2026_transparent.png")
GOLD = (251, 206, 10)
DARK = (20, 20, 20)
WHITE = (245, 245, 245)
FONT_REG = "/Library/Fonts/Arial Unicode.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = FONT_REG

STYLE = ("Ultra-photorealistic editorial photograph, premium corporate incentive "
         "travel (MICE) brand aesthetic, warm cinematic golden light, shallow depth "
         "of field, candid documentary style, magazine quality, 50mm, high dynamic "
         "range, no text, no logos, no watermarks.")

# day -> (slug, headline English, base scene prompt)
DAYS = {
 1:("barcelona","From ordinary meetings to extraordinary experiences",
    "Elegant corporate professionals at a private rooftop incentive event in Barcelona at sunset, Sagrada Familia and city skyline behind, champagne, candid laughter"),
 2:("roi","The ROI of incentive travel",
    "Confident executives in a bright modern boardroom reviewing strong upward growth charts on a large screen, optimistic, premium office"),
 3:("athens","Athens — Where history meets team spirit",
    "Corporate incentive group exploring the Acropolis and Parthenon in Athens, Greece at golden hour, business-casual travelers, ancient marble columns"),
 4:("tips","5 mistakes HR makes planning corporate events",
    "A focused HR director planning a corporate event at a sleek desk with a laptop, sticky notes and a city view, thoughtful"),
 5:("bts","Behind the scenes — producing a 200-person summit",
    "Behind the scenes event production crew with headsets setting up a large corporate gala stage with lighting rigs and rows of chairs, dramatic"),
 6:("cta","Q3 is filling up — book your destination now",
    "Stunning wide Mediterranean European coastal resort at sunset ready for a corporate event, inviting luxury terrace, empty set tables"),
 7:("prague","Prague — Where elegance meets edge",
    "Corporate incentive group on the Charles Bridge in Prague at dusk, Gothic towers and Prague Castle, business-casual, atmospheric"),
 8:("teamwork","The science behind team building that actually works",
    "Diverse corporate team doing an engaging outdoor team-building activity in a scenic European setting, collaboration, genuine smiles"),
 9:("culinary","Tuscany — Farm to table, team to family",
    "Corporate group at a long farm-to-table dinner in a Tuscany vineyard at golden hour, rustic elegance, rolling hills, wine and food"),
 10:("awards","Why your awards ceremony is forgettable (and how to fix it)",
    "Elegant corporate awards gala, a winner receiving a trophy on a beautifully lit stage, applauding audience, confetti, premium"),
 11:("rhodes","Rhodes — Where history sails with luxury",
    "Corporate incentive group on a luxury yacht near Rhodes old town harbour, turquoise Aegean sea, medieval fortress, sunny"),
 12:("testimonial","What HR directors say after working with us",
    "Confident professional HR director woman smiling warmly in a modern office, candid corporate portrait, approachable"),
 13:("milan","Milan — Where business meets la dolce vita",
    "Corporate incentive group at the Milan Duomo and Galleria Vittorio Emanuele at golden hour, elegant fashion, la dolce vita"),
 14:("roi","The real ROI of incentive travel — numbers HR directors need",
    "Executive presenting impressive ROI numbers and graphs on a screen to an attentive corporate team in a premium meeting room"),
 15:("bts","What happens 48 hours before a corporate event",
    "Behind the scenes crew finalizing a corporate gala ballroom 48 hours before, floral centerpieces, lighting checks, clipboards"),
 16:("tip","5 questions every HR director should ask before signing",
    "Thoughtful HR director reviewing an event proposal contract at a desk, pen in hand, considering, modern office"),
 17:("prague","Prague — Europe's most photogenic corporate destination",
    "Breathtaking panoramic view of Prague old town red rooftops and Vltava river at sunset, a corporate group enjoying a terrace view"),
 18:("casestudy","Case study: 80 employees into brand ambassadors",
    "Energized corporate group of pharma employees celebrating together at a branded company event, unity, pride, applause"),
 19:("cta","2026 H2 planning: Your company event window is closing",
    "Elegant calendar and planning concept on a desk with a stunning European destination visible through a window, urgency, premium"),
 20:("seville","Seville — Spain's best-kept secret for corporate incentives",
    "Corporate incentive group at the Plaza de Espana in Seville, Spain at golden hour, Andalusian architecture, flamenco elegance"),
 21:("mallorca","Mallorca — Where Q3 corporate trips go to peak",
    "Corporate group at a luxury cliffside infinity-pool resort in Mallorca overlooking turquoise sea, summer, relaxed sophistication"),
 22:("redflags","5 contract red flags HR directors miss",
    "Close-up of hands reviewing a contract with a magnifying lens at an executive desk, cautious, professional, warning concept"),
 23:("retention","How a tech company kept their top 40 engineers",
    "Happy diverse tech employees collaborating and laughing in a bright modern startup office, retention and loyalty, genuine energy"),
 24:("bts","The moment 200 people almost ate dinner in the rain",
    "Dramatic outdoor gala dinner under elegant transparent marquee tent as evening clouds gather, staff rushing, candles, tension and rescue"),
 25:("testimonial","What a CFO said 6 months after the trip — unscripted",
    "Confident male CFO executive in a tailored suit smiling candidly in a corner office, authentic corporate portrait"),
 26:("cta","The 2026 Q3 corporate window is closing — what's left",
    "Inviting luxury European destination terrace at sunset with a few remaining reserved tables, exclusivity, warm light"),
 27:("lisbon","Lisbon: Europe's Rising Star for Incentive Travel",
    "Corporate incentive group riding the iconic yellow tram through colorful Lisbon Alfama streets at golden hour, tiles, trams, charm"),
 28:("roi","The Real ROI of Incentive Travel — 2026 Numbers",
    "Sharp executive analyzing a glowing dashboard of positive 2026 performance metrics in a dark modern boardroom, data-driven"),
 29:("bts","72 hours before 200 people land in a foreign city",
    "Event logistics team coordinating with maps, schedules and radios in a hotel war-room, focused teamwork, countdown energy"),
 30:("casestudy","How a pharma company solved a retention crisis",
    "Pharma corporate team bonding and smiling at an incentive retreat, sense of belonging and renewed motivation, premium resort"),
 31:("tips","How to choose the right destination for your corporate event",
    "A world map and elegant travel mood board on a desk with photos of European cities, planning the perfect destination, inspiring"),
 32:("testimonial","What our clients say — unscripted",
    "Candid group of satisfied corporate clients chatting warmly after an event, authentic smiles, premium venue background"),
 33:("insight","The future of corporate events — what AI can't replace",
    "A warm genuine human handshake at a corporate event foreground with subtle futuristic holographic tech in background, human connection vs AI"),
 34:("porto","Porto: The underrated gem for corporate groups",
    "Corporate incentive group along the colorful Ribeira riverside of Porto, Dom Luis I bridge, Douro river, rabelo boats, golden hour"),
 35:("engagement","Why your best employees are quietly updating their LinkedIn",
    "A thoughtful professional employee looking out an office window contemplating their career, quiet tension, cinematic, corporate"),
 36:("cta","Summer 2026 — Last spots available",
    "Vibrant summer European coastal incentive destination, sun-drenched luxury beach club set for a corporate group, last-minute exclusivity"),
 37:("bts2","The 5AM call that saved a 120-person event",
    "Event producer on an urgent early-morning phone call at dawn outside an event venue, problem-solving under pressure, dramatic sunrise"),
 38:("tips2","The 10-week timeline: How to plan a perfect corporate trip",
    "Organized project timeline and elegant planning board for a corporate trip on a modern desk, methodical, premium stationery"),
 39:("insight2","Why 2026 is the year of the European incentive pivot",
    "Sophisticated montage feel of iconic European cities skyline at golden hour with a confident corporate group, momentum and opportunity"),
 40:("cta2","One conversation. That's all it takes.",
    "Two professionals having a warm confident conversation over coffee with a stunning European city view, the start of a partnership, inviting"),
}


def _font(path, size):
    return ImageFont.truetype(path, size)


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def overlay(base_path, day, out_path):
    slug, headline, _ = DAYS[day]
    W = H = 1080
    img = Image.open(base_path).convert("RGB")
    # cover-fit to 1080x1080
    s = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
    img = img.crop(((img.width - W) // 2, (img.height - H) // 2,
                    (img.width - W) // 2 + W, (img.height - H) // 2 + H))

    # bottom scrim for legibility
    scrim = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(scrim)
    for y in range(H):
        if y > H * 0.50:
            a = int(225 * ((y - H * 0.50) / (H * 0.50)) ** 1.3)
            sd.line([(0, y), (W, y)], fill=min(a, 235))
    black = Image.new("RGB", (W, H), (10, 10, 12))
    img = Image.composite(black, img, scrim)

    d = ImageDraw.Draw(img)
    # gold frame: top + bottom bars
    bar = 14
    d.rectangle([0, 0, W, bar], fill=GOLD)
    d.rectangle([0, H - bar, W, H], fill=GOLD)

    # DAY marker top-right
    f_day = _font(FONT_BOLD, 26)
    dtxt = f"DAY {day}"
    d.text((W - 40 - d.textlength(dtxt, font=f_day), 34), dtxt, font=f_day, fill=GOLD)

    margin = 70
    # logo (with built-in tagline) bottom-left + domains bottom-right
    lw, pad = 330, 20
    ly = H - bar - 34 - int(466 * lw / 1383)
    try:
        logo = Image.open(LOGO).convert("RGBA")
        logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
        ly = H - bar - 34 - logo.height
        # localized dark plate behind logo for contrast on bright photos
        plate = Image.new("RGBA", (lw + 2 * pad, logo.height + 2 * pad), (0, 0, 0, 0))
        ImageDraw.Draw(plate).rounded_rectangle(
            [0, 0, plate.width - 1, plate.height - 1], radius=18, fill=(10, 10, 12, 180))
        plate = plate.filter(ImageFilter.GaussianBlur(7))
        img.paste(plate, (margin - pad, ly - pad), plate)
        img.paste(logo, (margin, ly), logo)
    except Exception:
        pass
    f_dom = _font(FONT_REG, 24)
    dom = "upe.co.il  |  upe-spain.com"
    d.text((W - 40 - d.textlength(dom, font=f_dom), H - bar - 44), dom, font=f_dom, fill=WHITE)

    # headline (white) above logo, with gold accent bar
    f_head = _font(FONT_BOLD, 58)
    lines = _wrap(d, headline, f_head, W - 2 * margin)
    line_h = 70
    block_h = len(lines) * line_h
    y = ly - pad - 34 - block_h
    d.rectangle([margin, y - 22, margin + 56, y - 16], fill=GOLD)
    yy = y
    for ln in lines:
        d.text((margin, yy), ln, font=f_head, fill=WHITE)
        yy += line_h

    img.save(out_path, "PNG")
    return out_path


def brand_all():
    """Overlay branding on every base PNG in _bases/ + _pilot/."""
    import glob, re
    out = os.path.join(ROOT, "content", "images_realistic")
    os.makedirs(out, exist_ok=True)
    bases = (glob.glob(os.path.join(out, "_bases", "*_real.png")) +
             glob.glob(os.path.join(out, "_pilot", "*_real.png")))
    done, miss = [], []
    for bp in sorted(bases):
        m = re.search(r"day(\d+)_", os.path.basename(bp))
        if not m:
            continue
        day = int(m.group(1))
        if day not in DAYS:
            continue
        slug = DAYS[day][0]
        overlay(bp, day, os.path.join(out, f"day{day}_{slug}_branded.png"))
        done.append(day)
    have = set(done)
    miss = [d for d in DAYS if d not in have]
    print(f"branded {len(done)}: {sorted(done)}")
    if miss:
        print(f"MISSING bases for days: {sorted(miss)}")
    return done, miss


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "all":
        brand_all()
    else:
        base = os.path.join(ROOT, "content", "images_realistic", "_pilot")
        out = os.path.join(ROOT, "content", "images_realistic")
        os.makedirs(out, exist_ok=True)
        for day, bp in [(1, os.path.join(base, "day1_barcelona_real.png")),
                        (34, os.path.join(base, "day34_porto_real.png"))]:
            slug = DAYS[day][0]
            overlay(bp, day, os.path.join(out, f"day{day}_{slug}_branded.png"))
            print("branded", day)
