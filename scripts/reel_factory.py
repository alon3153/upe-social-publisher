#!/usr/bin/env python3
"""
UPE Reel Factory - turns raw event footage in Dropbox into ready Instagram Reels
and drops them into the existing approval gate. Alon only clicks Approve.

Runs LOCALLY (needs the Dropbox archive), weekly via launchd:
  1. per event folder in Uproduction/pic/<year>/<event>/ (newest years first, Philip Morris
     excluded - client policy): one mid frame from up to 10 unused clips
  2. headless `claude -p` looks at the frames, picks 4-6 shots in story order + the opener frame,
     writes Hebrew hook / captions / CTA / post caption in the shapes from state/ig_swipe.json
  3. studio edit (reel_studio.py): beat-cut montage, grade, push-ins, transitions, kinetic Hebrew
     captions, progress bar, end card, UPE music bed; Higgsfield Seedance cinematic opener from a
     real frame of the event
  4. host on fal (real video/mp4 content-type), Higgsfield Virality Predictor score in the email
     subject, write content/sofia/queue/<name>.json to main, dispatch `sofia-approve.yml`
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
REPO = "alon3153/upe-social-publisher"
YEARS = ["2026", "2025", "2024", "2023"]
EXCLUDE = re.compile(r"פליפ|פיליפ|מוריס|philip|pmi|פמי", re.I)
VIDEO = re.compile(r"\.(mp4|mov|m4v)$", re.I)
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


MUSIC_DIR = os.path.expanduser(
    "~/Library/CloudStorage/Dropbox-UproductionEvents/Alon ouaknine/Uproduction Brand/מוזיקה/04 מוזיקה לסרטונים ומצגות")
MUSIC_SKIP = re.compile(r"explainer|loop|candidate|battle", re.I)  # UPE-owned beds only, upbeat ones
COMPOSIO = os.environ.get("COMPOSIO_BIN", os.path.expanduser("~/.composio/composio"))
FAL_PY = os.path.expanduser("~/dev/claude-code-video-toolkit/.venv/bin/python")


def candidates(state):
    """(event, [unused clips]) per event folder, newest years first. Listing only - no hydration."""
    skip = set(state["used"]) | set(state["rejected"])
    done_events = set(state.get("events", []))
    out = []
    for y in YEARS:
        ydir = os.path.join(ARCHIVE, y)
        if not os.path.isdir(ydir):
            continue
        events = sorted(os.listdir(ydir))
        random.shuffle(events)
        for ev in events:
            if EXCLUDE.search(ev) or f"{y}/{ev}" in done_events:
                continue
            clips = []
            for dp, _, fs in os.walk(os.path.join(ydir, ev)):
                clips += [os.path.join(dp, f) for f in fs if VIDEO.search(f) and os.path.join(dp, f) not in skip]
            if len(clips) >= 4:  # a montage needs at least 4 shots
                random.shuffle(clips)
                out.append((f"{y}/{ev}", ev, clips[:10]))
    return out


def probe(path):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).strip())


def contact_frames(clips, work):
    """One mid frame per usable clip (>= 2.5 s)."""
    keep = []
    for c in clips:
        try:
            d = probe(c)
        except Exception:
            continue
        if d < 2.5:
            continue
        p = os.path.join(work, f"k{len(keep)}.jpg")
        sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{d * 0.5:.2f}", "-i", c, "-frames:v", "1", "-vf", "scale=480:-2", p])
        keep.append((c, p))
    return keep


def write_copy(event, shots):
    sw = json.load(open(SWIPE))
    listing = "\n".join(f"  [{i}] {p}" for i, (_, p) in enumerate(shots))
    prompt = f"""You are the editor and copywriter of Instagram Reels for Uproduction Events (UPE): Israeli B2B
corporate events and incentive trips. Account @uproductionevents, Hebrew audience: HR, CEOs, sales managers.

Each image is the middle frame of one raw phone clip from the SAME real UPE production.
Event folder (client + destination): "{event}"
{listing}

Hook shapes that win on Instagram right now (copy the SHAPE, never words):
{chr(10).join('- ' + x for x in sw['winning_patterns'])}
Never open with:
{chr(10).join('- ' + x for x in sw['losing_patterns'])}

Your job:
1. pick: 4-6 clip indexes for a fast montage, in story order. Prefer people having fun, crowd energy,
   wow venues, action. pick[0] MUST be the most energetic shot with people moving (it carries the
   hook - Higgsfield scores it). Drop blurry/dark/empty frames, screens/slides, documents, passports,
   close-ups of children, anything embarrassing for a client. If fewer than 4 are good: usable=false.
2. opener: index of the single most cinematic frame (wide, beautiful, no close faces) - an AI camera
   move will be made from it.
3. hook: natural spoken Hebrew, max 8 words, about what is visible. Burned on screen. No hashtags,
   no emoji, no company name, no year or date.
4. captions: 3 punchy Hebrew on-screen words/short phrases (1-3 words each) that build the story.
5. cta: end-card line, Hebrew, max 7 words, inviting the HR/CEO viewer to message us.
6. caption: Hebrew post text. Line 1 = stronger version of the hook (works before "...more").
   1-2 short value lines for an HR/CEO reader. One soft ask (save / send to your HR / comment).
   Then "📷 רגע אמיתי מהפקה של Uproduction · <place>". Then max 4 hashtags
   (one of #נופשחברה #ימיגיבוש #אירועיחברה #כנסים + one destination tag).
7. opener_prompt: English, one sentence: the camera move for the opener (drone push-in, slow orbit,
   rising crane...). The scene and people must stay exactly as in the frame.
Never invent numbers, prices, quotes or names you cannot see. Client names from the folder are OK.

Return ONLY JSON: {{"usable": true|false, "reason": "...", "pick": [..], "opener": 0, "hook": "...",
"captions": ["..",".."], "cta": "...", "caption": "...", "place": "...", "opener_prompt": "..."}}"""
    out = subprocess.run([CLAUDE, "-p", "--allowedTools=Read", "--output-format", "text", prompt],
                         capture_output=True, text=True, timeout=600).stdout
    m = re.search(r"\{.*\}", out, re.S)
    if not m:  # infra failure (login, quota) - abort the run, never blame the clips
        raise SystemExit(f"reel_factory: claude CLI gave no JSON, aborting: {out.strip()[:200]}")
    return json.loads(m.group(0))


# ---------- hosting + Higgsfield (via Composio) ----------

def fal_upload(path):
    """Public URL with a real content-type (GitHub release assets are octet-stream; IG/Higgsfield reject them)."""
    code = ("import os,sys,fal_client;os.environ.setdefault('FAL_KEY',open(os.path.expanduser('~/.upe_fal_key'))"
            ".read().strip());print(fal_client.upload_file(sys.argv[1]))")
    return sh([FAL_PY, "-c", code, path]).strip().splitlines()[-1]


def hf(tool, data, timeout=900):
    r = subprocess.run([COMPOSIO, "execute", tool, "-d", json.dumps(data)], capture_output=True, text=True,
                       timeout=timeout)
    j = json.loads(r.stdout[r.stdout.index("{"):])
    if not j.get("successful"):
        raise RuntimeError(f"{tool}: {str(j.get('error'))[:200]}")
    return j["data"]


def hf_wait(job_id, tries=40):
    for _ in range(tries):
        d = hf("HIGGSFIELD_MCP_JOB_STATUS", {"jobId": job_id, "sync": True})
        s = json.dumps(d)
        st = re.search(r'"status": ?"(\w+)"', s)
        if st and st.group(1) == "completed":
            return d
        if st and st.group(1) in ("failed", "nsfw", "cancelled"):
            raise RuntimeError(f"higgsfield job {job_id} {st.group(1)}")
    raise RuntimeError(f"higgsfield job {job_id} timeout")


def hf_import(url, kind):
    return re.search(r'"media_id": ?"([^"]+)"', json.dumps(hf("HIGGSFIELD_MCP_MEDIA_IMPORT_URL",
                                                               {"url": url, "type": kind}))).group(1)


def ai_opener(clip, prompt, work):
    """Real frame from the event -> Seedance 2.0 4 s camera move. Returns local mp4 or None."""
    try:
        d = probe(clip)
        fr = os.path.join(work, "opener.jpg")
        sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{d * 0.5:.2f}", "-i", clip, "-frames:v", "1", "-q:v", "2", fr])
        mid = hf_import(fal_upload(fr), "image")
        job = hf("HIGGSFIELD_MCP_GENERATE_VIDEO", {"params": {
            "model": "seedance_2_0", "duration": 4, "resolution": "1080p", "mode": "std", "aspect_ratio": "9:16",
            "generate_audio": False, "medias": [{"role": "start_image", "value": mid}],
            "prompt": prompt + " Keep the scene and people exactly as in the image; only the camera moves. "
                               "Premium travel-commercial look."}})
        jid = job["results"][0]["id"]
        raw = re.search(r'"rawUrl": ?"([^"]+)"', json.dumps(hf_wait(jid))).group(1)
        src, out = os.path.join(work, "opener_raw.mp4"), os.path.join(work, "opener.mp4")
        sh(["curl", "-sL", "-o", src, raw])
        sh(["ffmpeg", "-y", "-v", "error", "-i", src, "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p",
            "-an", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", out])
        return out
    except Exception as e:
        print(f"  opener skipped: {e}")
        return None


def virality(url):
    """Higgsfield Virality Predictor score (0-100) or None."""
    try:
        mid = hf_import(url, "video")
        d = hf("HIGGSFIELD_MCP_VIRALITY_PREDICTOR", {"action": "create", "params": {
            "model": "virality_predictor", "medias": [{"role": "video", "id": mid}]}})
        s = json.dumps(hf_wait(d["job_id"], tries=80))
        m = re.search(r'"overall_score": ?([0-9.]+)', s)
        return round(float(m.group(1))) if m else None
    except Exception as e:
        print(f"  virality skipped: {e}")
        return None


def slots(n):
    """Next Sun/Tue/Thu dates (the cadence the 2026-08 batch used)."""
    d, out = dt.date.today() + dt.timedelta(days=1), []
    while len(out) < n:
        if d.weekday() in (6, 1, 3):
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def main():
    import reel_studio
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-opener", action="store_true")
    a = ap.parse_args()
    state = load_state()
    state.setdefault("events", [])
    os.makedirs(OUTDIR, exist_ok=True)
    tracks = sorted(os.path.join(MUSIC_DIR, f) for f in os.listdir(MUSIC_DIR)
                    if re.search(r"\.(mp3|wav|m4a)$", f, re.I) and not MUSIC_SKIP.search(f))
    made = []
    for key, event, clips in candidates(state):
        if len(made) >= a.count:
            break
        with tempfile.TemporaryDirectory() as work:
            try:
                shots = contact_frames(clips, work)
                if len(shots) < 4:
                    state["events"].append(key); continue
                copy = write_copy(event, shots)
                if not copy.get("usable") or len(copy.get("pick", [])) < 4:
                    print(f"skip {event}: {copy.get('reason')}")
                    state["events"].append(key); continue
                picked = [shots[i][0] for i in copy["pick"] if 0 <= i < len(shots)][:6]
                opener = None if a.no_opener else ai_opener(shots[copy.get("opener", 0)][0],
                                                             copy.get("opener_prompt", "Slow cinematic drone push-in."),
                                                             work)
                music = tracks[(state["seq"]) % len(tracks)]
                state["seq"] += 1
                name = f"upe-reel-{dt.date.today():%Y%m%d}-{state['seq']:04d}.mp4"
                out = os.path.join(OUTDIR, name)
                info = reel_studio.build(picked, music, copy["hook"], copy.get("captions", []),
                                         copy.get("cta", "רוצים כזה לחברה שלכם? שלחו הודעה"), out, work, opener)
            except SystemExit:
                raise
            except Exception as e:  # one bad event must not kill the batch
                print(f"error {event}: {e}")
                state["events"].append(key); continue
        state["used"] += picked
        state["events"].append(key)
        made.append({"name": name, "file": out, "event": event, "music": os.path.basename(music), **info, **copy})
        print(f"made {name}: {copy['hook']} ({info['duration']}s, {info['shots']} shots, opener={'yes' if opener else 'no'})")
        save_state(state)
    save_state(state)
    if a.dry_run or not made:
        print(json.dumps(made, ensure_ascii=False, indent=1)); return 0

    for m in made:
        m["url"] = fal_upload(m["file"])
        m["score"] = virality(m["url"])
        print(f"{m['name']}: {m['url']}  virality={m['score']}")
    qname = f"reels-{dt.date.today():%Y%m%d}-{state['seq']:04d}"
    queue = [{"id": m["name"][:-4],
              "headline": (f"[{m['score']}/100] " if m.get("score") is not None else "") + m["hook"],
              "caption": m["caption"], "video_url": m["url"],
              "accounts": ["uproductionevents"], "scheduled_date": s, "day": 80000 + int(m["name"][-8:-4]),
              "kind": "reel_factory", "source_event": m["event"]}
             for m, s in zip(made, slots(len(made)))]
    # write the queue file straight to main via the API: the local checkout may sit on any branch
    import base64
    body = json.dumps(queue, ensure_ascii=False, indent=1).encode()
    sh(["gh", "api", "-X", "PUT", f"repos/{REPO}/contents/content/sofia/queue/{qname}.json",
        "-f", f"message=chore(reels): queue {len(queue)} factory reels for approval",
        "-f", f"content={base64.b64encode(body).decode()}", "-f", "branch=main"])
    sh(["gh", "workflow", "run", "sofia-approve.yml", "-R", REPO, "-f", f"queue_file={qname}"])
    print(f"queued {len(queue)} reels -> approval emails dispatched ({qname})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
