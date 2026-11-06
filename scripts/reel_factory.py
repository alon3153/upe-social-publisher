#!/usr/bin/env python3
"""
UPE Reel Factory - turns raw event footage in Dropbox into ready Instagram Reels
and drops them into the existing approval gate. Alon only clicks Approve.

Runs LOCALLY (needs the Dropbox archive), weekly via launchd:
  1. pick N unused clips from Uproduction/pic/<year>/<event>/ (newest years first,
     one clip per event, Philip Morris excluded - client policy)
  2. extract 3 frames -> headless `claude -p` looks at them and writes a Hebrew
     hook + caption in the shapes from state/ig_swipe.json (or rejects the clip)
  3. render 1080x1920 (blur-pad if landscape), max 15s, hook burned on the first
     3.5s (Pillow+raqm for correct RTL), original audio
  4. upload mp4 to GitHub release `reels-auto`, write content/sofia/queue/<name>.json,
     push, dispatch `sofia-approve.yml` -> approval email per reel
  5. Approve click -> existing `Publish Approved` cron publishes the Reel

Usage:
  python3 scripts/reel_factory.py --count 3            # full run
  python3 scripts/reel_factory.py --count 1 --dry-run  # render only, no upload/queue
"""
import argparse, datetime as dt, json, os, random, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = os.path.expanduser(
    "~/Library/CloudStorage/Dropbox-UproductionEvents/Alon ouaknine/Uproduction Brand/Movies & Photos/Uproduction/pic")
STATE = os.path.expanduser("~/.upe-jobs/reel_factory/state.json")
OUTDIR = os.path.expanduser("~/.upe-jobs/reel_factory/out")
SWIPE = os.path.join(ROOT, "state", "ig_swipe.json")
FONT = "/Library/Fonts/Arial Unicode.ttf"
RELEASE = "reels-auto"
REPO = "alon3153/upe-social-publisher"
YEARS = ["2026", "2025", "2024", "2023"]
EXCLUDE = re.compile(r"פליפ|פיליפ|מוריס|philip|pmi|פמי", re.I)
VIDEO = re.compile(r"\.(mp4|mov|m4v)$", re.I)
MAX_SEC = 15.0
CLAUDE = os.environ.get("CLAUDE_BIN", "claude")


def sh(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw).stdout


def load_state():
    try:
        return json.load(open(STATE))
    except (OSError, ValueError):
        return {"used": [], "rejected": [], "seq": 0}


def save_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), ensure_ascii=False, indent=1)


def candidates(state):
    """One random unused clip per event folder, newest years first. Listing only - no hydration."""
    skip = set(state["used"]) | set(state["rejected"])
    out = []
    for y in YEARS:
        ydir = os.path.join(ARCHIVE, y)
        if not os.path.isdir(ydir):
            continue
        events = sorted(os.listdir(ydir))
        random.shuffle(events)
        for ev in events:
            if EXCLUDE.search(ev):
                continue
            clips = []
            for dp, _, fs in os.walk(os.path.join(ydir, ev)):
                clips += [os.path.join(dp, f) for f in fs if VIDEO.search(f) and os.path.join(dp, f) not in skip]
            if clips:
                out.append((ev, random.choice(clips)))
    return out


def probe(path):
    j = json.loads(sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                       "stream=width,height:stream_side_data=rotation:format=duration", "-of", "json", path]))
    st = j["streams"][0]
    w, h = st["width"], st["height"]
    rot = abs(int(next((d.get("rotation", 0) for d in st.get("side_data_list", [])), 0)))
    if rot in (90, 270):
        w, h = h, w
    return float(j["format"]["duration"]), w, h


def frames(path, dur, work):
    paths = []
    for i, frac in enumerate((0.15, 0.5, 0.85)):
        p = os.path.join(work, f"f{i}.jpg")
        sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{dur * frac:.2f}", "-i", path, "-frames:v", "1",
            "-vf", "scale=540:-2", p])
        paths.append(p)
    return paths


def write_copy(event, frame_paths):
    sw = json.load(open(SWIPE))
    prompt = f"""You write Instagram Reels for Uproduction Events (UPE): Israeli B2B corporate events and
incentive trips. Account @uproductionevents, Hebrew audience: HR, CEOs, sales managers.

Look at these 3 frames from ONE raw phone clip shot at a real UPE production: {', '.join(frame_paths)}
Event folder name (client + destination): "{event}"

Hook shapes that win on Instagram right now (copy the SHAPE, never words):
{chr(10).join('- ' + x for x in sw['winning_patterns'])}
Never open with:
{chr(10).join('- ' + x for x in sw['losing_patterns'])}

Rules:
- Reject the clip (usable=false) if it is blurry, dark, mostly empty, shows a screen/slide only,
  shows a document, a passport, children close-up, or anything embarrassing for a client.
- hook: natural spoken Hebrew, max 9 words, about what is actually visible. It is burned on screen.
  No hashtags, no emoji, no company name, no year or date.
- caption: Hebrew. Line 1 = a stronger version of the hook (must make sense before the "...more" cut).
  Then 1-2 short lines of value for an HR/CEO reader. Then one soft ask (save / send to your HR /
  comment). Then the line "📷 רגע אמיתי מהפקה של Uproduction · <place in Hebrew>". Then 4 hashtags
  max (one of #נופשחברה #ימיגיבוש #אירועיחברה #כנסים + one destination tag).
- Never invent numbers, prices, client quotes or names you cannot see. Client brand names from the
  folder are allowed. Never mention a year or date.
- place: the destination from the folder name, in Hebrew.

Return ONLY JSON: {{"usable": true|false, "reason": "...", "hook": "...", "caption": "...", "place": "..."}}"""
    out = subprocess.run([CLAUDE, "-p", "--allowedTools=Read", "--output-format", "text", prompt],
                         capture_output=True, text=True, timeout=300).stdout
    m = re.search(r"\{.*\}", out, re.S)
    if not m:  # infra failure (login, quota) - abort the run, never blame the clip
        raise SystemExit(f"reel_factory: claude CLI gave no JSON, aborting: {out.strip()[:200]}")
    return json.loads(m.group(0))


def hook_png(text, path):
    from PIL import Image, ImageDraw, ImageFont  # raqm layout shapes RTL - no python-bidi pass
    W, pad = 1080, 40
    font = ImageFont.truetype(FONT, 74, layout_engine=ImageFont.Layout.RAQM)
    words, lines, cur = text.split(), [], ""
    d = ImageDraw.Draw(Image.new("RGBA", (W, 10)))
    for w in words:  # greedy wrap, RTL word order preserved by raqm per line
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font, direction="rtl", language="he") > W - 2 * pad - 60 and cur:
            lines.append(cur); cur = w
        else:
            cur = t
    lines.append(cur)
    lh = 96
    img = Image.new("RGBA", (W, lh * len(lines) + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((30, 0, W - 30, img.height), radius=28, fill=(17, 17, 17, 205))
    for i, ln in enumerate(lines):
        d.text((W // 2, pad + i * lh + lh // 2), ln, font=font, fill=(240, 192, 64, 255),
               anchor="mm", direction="rtl", language="he")
    img.save(path)
    return img.height


def render(src, dur, w, h, hook, out, work):
    png = os.path.join(work, "hook.png")
    ph = hook_png(hook, png)
    length = min(dur, MAX_SEC)
    start = 0.0 if dur <= MAX_SEC else min(2.0, dur - MAX_SEC)
    if h / w >= 1.7:   # already vertical
        base = "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[bg]"
    else:              # blur-pad landscape/square so nothing is cropped
        base = ("[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                "boxblur=30:3[bgb];[b]scale=1080:-2[fg];[bgb][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[bg]")
    y = int(1920 * 0.18)
    fc = f"{base};[bg][1:v]overlay=0:{y}:enable='lte(t,3.5)'[v]"
    sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{length:.2f}", "-i", src, "-i", png,
        "-filter_complex", fc, "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium",
        "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-movflags", "+faststart", out])
    return ph


def slots(n):
    """Next Sun/Tue/Thu dates (the cadence the 2026-08 batch used)."""
    d, out = dt.date.today() + dt.timedelta(days=1), []
    while len(out) < n:
        if d.weekday() in (6, 1, 3):
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    state = load_state()
    os.makedirs(OUTDIR, exist_ok=True)
    made = []
    for event, clip in candidates(state):
        if len(made) >= a.count:
            break
        with tempfile.TemporaryDirectory() as work:
            try:
                dur, w, h = probe(clip)
                if dur < 4:
                    state["rejected"].append(clip); continue
                copy = write_copy(event, frames(clip, dur, work))
                if not copy.get("usable"):
                    print(f"skip {event}: {copy.get('reason')}")
                    state["rejected"].append(clip); continue
                state["seq"] += 1
                name = f"upe-reel-{dt.date.today():%Y%m%d}-{state['seq']:04d}.mp4"
                out = os.path.join(OUTDIR, name)
                render(clip, dur, w, h, copy["hook"], out, work)
            except Exception as e:  # one bad clip must not kill the batch
                print(f"error {event}: {e}")
                state["rejected"].append(clip); continue
        state["used"].append(clip)
        made.append({"name": name, "file": out, "event": event, "clip": clip, **copy})
        print(f"made {name}: {copy['hook']}")
        save_state(state)
    save_state(state)
    if a.dry_run or not made:
        print(json.dumps(made, ensure_ascii=False, indent=1)); return 0

    if subprocess.run(["gh", "release", "view", RELEASE, "-R", REPO], capture_output=True).returncode:
        sh(["gh", "release", "create", RELEASE, "-R", REPO, "--title", "Reel factory assets",
            "--notes", "Auto-rendered reels. Do not delete: approved posts reference these URLs."])
    sh(["gh", "release", "upload", RELEASE, "-R", REPO, "--clobber"] + [m["file"] for m in made])
    qname = f"reels-{dt.date.today():%Y%m%d}-{state['seq']:04d}"
    queue = [{"id": m["name"][:-4], "headline": m["hook"], "caption": m["caption"],
              "video_url": f"https://github.com/{REPO}/releases/download/{RELEASE}/{m['name']}",
              "accounts": ["uproductionevents"], "scheduled_date": s, "day": 80000 + int(m["name"][-8:-4]),
              "kind": "reel_factory", "source_event": m["event"]}
             for m, s in zip(made, slots(len(made)))]
    qpath = os.path.join(ROOT, "content", "sofia", "queue", f"{qname}.json")
    json.dump(queue, open(qpath, "w"), ensure_ascii=False, indent=1)
    sh(["git", "-C", ROOT, "pull", "-q", "--rebase"])
    sh(["git", "-C", ROOT, "add", qpath])
    sh(["git", "-C", ROOT, "commit", "-q", "-m", f"chore(reels): queue {len(queue)} factory reels for approval"])
    sh(["git", "-C", ROOT, "push", "-q"])
    sh(["gh", "workflow", "run", "sofia-approve.yml", "-R", REPO, "-f", f"queue_file={qname}"])
    print(f"queued {len(queue)} reels -> approval emails dispatched ({qname})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
