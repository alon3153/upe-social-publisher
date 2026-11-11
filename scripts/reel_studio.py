#!/usr/bin/env python3
"""
Studio-style Reel editor for raw UPE event footage (used by reel_factory.py).

One call = one finished 1080x1920 Reel:
  - montage of 4-6 shots from ONE event, each cut on the music beat
  - optional AI cinematic opener (Higgsfield, made from a real frame of the event)
  - per shot: fill-crop, slow push-in, colour grade, sharpen, vignette, speed ramp
  - xfade transitions that rotate (white flash, slide, zoom, blur)
  - Hebrew hook that pops in, 2-3 kinetic caption words, retention progress bar
  - branded end card with logo + CTA
  - music bed with fade, original sound ducked underneath, loudness -14 LUFS

Pure ffmpeg + Pillow(raqm). No numpy: tempo is estimated from an energy envelope.
"""
import array, json, math, os, random, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets", "reels")
FONT_BLACK = os.path.join(ASSETS, "Heebo-Black.ttf")
FONT_BOLD = os.path.join(ASSETS, "Heebo-Bold.ttf")
LOGO = os.path.join(ASSETS, "logo.png")
GOLD, ORANGE, INK = (240, 192, 64, 255), (232, 133, 74, 255), (17, 17, 17, 255)
W, H, FPS = 1080, 1920, 30
TRANSITIONS = ["fadewhite", "slideleft", "zoomin", "hblur", "smoothup", "circleopen"]
END_CARD = 2.2


def sh(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def duration(path):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).strip())


def has_audio(path):
    return bool(sh(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                    "-of", "csv=p=0", path]).strip())


# ---------- music: tempo + the loudest rising point (the "drop") ----------

def music_plan(path, need):
    """Return (beat_seconds, start_offset). Energy envelope at 100 Hz, autocorrelation for tempo."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "4000", "-f", "s16le", "-"],
                         check=True, capture_output=True).stdout
    s = array.array("h"); s.frombytes(raw[: len(raw) // 2 * 2])
    hop = 40  # 10 ms
    env = [sum(abs(x) for x in s[i:i + hop]) / hop for i in range(0, len(s) - hop, hop)]
    if len(env) < 300:
        return 0.5, 0.0
    flux = [max(0.0, env[i] - env[i - 1]) for i in range(1, len(env))]
    best, beat = -1.0, 0.5
    for lag in range(33, 75):  # 80-180 BPM
        c = sum(flux[i] * flux[i - lag] for i in range(lag, min(len(flux), 3000)))
        if c > best:
            best, beat = c, lag / 100.0
    # start where a 1 s window jumps most vs the previous second, leaving room for `need`
    total = len(env) / 100.0
    best_j, start = -1.0, 0.0
    for i in range(100, int((total - need) * 100), 25):
        jump = sum(env[i:i + 100]) - sum(env[i - 100:i])
        if jump > best_j:
            best_j, start = jump, i / 100.0
    return beat, max(0.0, start - 0.15)


# ---------- text cards (Pillow + raqm shapes RTL; never pre-run python-bidi) ----------

def _wrap(draw, text, font, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if cur and draw.textlength(t, font=font, direction="rtl", language="he") > maxw:
            lines.append(cur); cur = w
        else:
            cur = t
    return lines + [cur]


def text_card(text, path, size=92, fill=GOLD, box=INK, font=FONT_BLACK, maxw=W - 160):
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(font, size, layout_engine=ImageFont.Layout.RAQM)
    d = ImageDraw.Draw(Image.new("RGBA", (W, 10)))
    lines = _wrap(d, text, f, maxw)
    lh = int(size * 1.25)
    img = Image.new("RGBA", (W, lh * len(lines) + 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    widest = max(d.textlength(l, font=f, direction="rtl", language="he") for l in lines)
    x0 = (W - widest) / 2 - 44
    d.rounded_rectangle((x0, 0, W - x0, img.height), radius=34, fill=box)
    d.rectangle((x0, img.height - 12, W - x0, img.height), fill=ORANGE)  # brand underline
    for i, ln in enumerate(lines):
        d.text((W // 2, 35 + i * lh + lh // 2), ln, font=f, fill=fill, anchor="mm", direction="rtl", language="he")
    img.save(path)
    return img.height


def end_card(cta, path):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (W, H), (17, 17, 17, 235))
    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((760, 300))
    img.alpha_composite(logo, ((W - logo.width) // 2, 640))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT_BLACK, 70, layout_engine=ImageFont.Layout.RAQM)
    for i, ln in enumerate(_wrap(d, cta, f, W - 180)):
        d.text((W // 2, 1060 + i * 92), ln, font=f, fill=GOLD, anchor="mm", direction="rtl", language="he")
    f2 = ImageFont.truetype(FONT_BOLD, 46, layout_engine=ImageFont.Layout.RAQM)
    d.text((W // 2, 1300), "upe.co.il", font=f2, fill=(255, 255, 255, 230), anchor="mm")
    img.save(path)


# ---------- shots ----------

def shot(src, seg, start, out, i):
    """One graded, pushed-in, vertical shot of exactly `seg` seconds."""
    speed = 0.8 if i % 3 == 1 else 1.0          # every 3rd shot a touch faster
    take = seg / speed
    zdir = "+" if i % 2 == 0 else "-"
    z0 = "1.0" if zdir == "+" else "1.10"
    zoom = f"if(eq(on,0),{z0},zoom{zdir}0.0016)"
    vf = (f"setpts={speed}*PTS,scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
          f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
          "eq=contrast=1.10:saturation=1.32:brightness=0.015:gamma=0.97,"
          "curves=preset=increase_contrast,unsharp=5:5:0.7,vignette=PI/5,"
          f"trim=duration={seg:.3f},setpts=PTS-STARTPTS,format=yuv420p")
    sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{take + 0.3:.2f}", "-i", src,
        "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", str(FPS), out])


def build(clips, music, hook, captions, cta, out, work, opener=None):
    """clips: list of local video paths from one event (4-6). opener: optional mp4 (AI cinematic shot)."""
    beat, moff = music_plan(music, 16)
    seg = beat * 4 if beat * 4 <= 2.6 else beat * 2           # 4 beats (or 2 when tempo is slow)
    seg = max(1.8, min(seg, 2.6))
    xf = 0.22
    parts = []
    if opener:  # AI cinematic shot: keep its best 2.8 s
        op = os.path.join(work, "op_cut.mp4")
        sh(["ffmpeg", "-y", "-v", "error", "-i", opener, "-t", "2.8", "-an", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "18", "-r", str(FPS), "-pix_fmt", "yuv420p", op])
        opener = op
    for i, c in enumerate(clips):
        d = duration(c)
        st = random.uniform(0.3, max(0.3, d - seg / 0.8 - 0.3)) if d > seg + 1 else 0
        p = os.path.join(work, f"s{i}.mp4")
        shot(c, seg, st, p, i)
        parts.append(p)
        if opener and i == 0:  # hook needs a human/action first frame; the AI cinematic shot comes 2nd
            parts.append(opener)

    # chain xfades
    lens = [duration(p) for p in parts]
    inputs, fc, last, t = [], [], "0:v", lens[0]
    for p in parts:
        inputs += ["-i", p]
    for k in range(1, len(parts)):
        tr = TRANSITIONS[(k - 1) % len(TRANSITIONS)]
        off = t - xf
        fc.append(f"[{last}][{k}:v]xfade=transition={tr}:duration={xf}:offset={off:.3f}[x{k}]")
        last, t = f"x{k}", off + lens[k]
    body = t
    total = body + END_CARD

    # overlays
    hook_png, cap_pngs = os.path.join(work, "hook.png"), []
    text_card(hook, hook_png, size=96)
    for j, c in enumerate(captions[:3]):
        p = os.path.join(work, f"cap{j}.png")
        text_card(c, p, size=78, fill=(255, 255, 255, 255), box=(232, 133, 74, 235))
        cap_pngs.append(p)
    end_png = os.path.join(work, "end.png")
    end_card(cta, end_png)
    n0 = len(parts)
    inputs += ["-loop", "1", "-t", f"{total:.2f}", "-i", hook_png]
    for p in cap_pngs:
        inputs += ["-loop", "1", "-t", f"{total:.2f}", "-i", p]
    inputs += ["-loop", "1", "-t", f"{total:.2f}", "-i", end_png]
    fc.append(f"[{last}]tpad=stop_mode=clone:stop_duration={END_CARD}[base]")
    # hook pops in (fade + slight drop) for 0-2.8 s
    fc.append(f"[{n0}:v]format=rgba,fade=in:st=0.05:d=0.25:alpha=1,fade=out:st=2.6:d=0.25:alpha=1[hk]")
    fc.append("[base][hk]overlay=x=0:y='300+max(0,40-80*t)':enable='lte(t,2.9)'[v0]")
    cur = "v0"
    slot = (body - 3.2) / max(1, len(cap_pngs))
    for j in range(len(cap_pngs)):
        a = 3.2 + j * slot
        b = a + min(1.6, slot - 0.1)
        fc.append(f"[{n0 + 1 + j}:v]format=rgba,fade=in:st={a:.2f}:d=0.15:alpha=1[c{j}]")
        fc.append(f"[{cur}][c{j}]overlay=x=0:y=1380:enable='between(t,{a:.2f},{b:.2f})'[v{j + 1}]")
        cur = f"v{j + 1}"
    ne = n0 + 1 + len(cap_pngs)
    fc.append(f"[{ne}:v]format=rgba,fade=in:st={body:.2f}:d=0.3:alpha=1[ec]")
    fc.append(f"[{cur}][ec]overlay=0:0:enable='gte(t,{body:.2f})'[ve]")
    # retention progress bar
    fc.append(f"[ve]drawbox=x=0:y={H - 14}:w='iw*t/{total:.2f}':h=14:color=0xF0C040@0.95:t=fill[vout]")

    # audio: music bed + ducked original sound of the first clip-ish
    mi = ne + 1
    inputs += ["-ss", f"{moff:.2f}", "-t", f"{total:.2f}", "-i", music]
    fc.append(f"[{mi}:a]afade=t=in:d=0.08,afade=t=out:st={total - 0.8:.2f}:d=0.8,volume=1.0[mus]")
    amix = "[mus]"
    nat = [k for k, p in enumerate(clips) if has_audio(p)]
    if nat:
        inputs += ["-i", clips[nat[0]]]
        fc.append(f"[{mi + 1}:a]atrim=0:{body:.2f},volume=0.12,apad=whole_dur={total:.2f}[nat]")
        fc.append("[mus][nat]amix=inputs=2:duration=first:normalize=0[mx]")
        amix = "[mx]"
    fc.append(f"{amix}loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100[aout]")

    sh(["ffmpeg", "-y", "-v", "error"] + inputs + ["-filter_complex", ";".join(fc),
        "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium",
        "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", out])
    return {"duration": round(total, 2), "beat": beat, "music_offset": moff, "shots": len(parts)}
