#!/usr/bin/env python3
"""Golden-hour squad: advocates comment on Alon's fresh LinkedIn posts.

Alon chose fully-automatic operation (14.08.2026): comments go out without
passing the approval gate, because the gate's latency (hours to days) destroys
the only thing that makes a comment worth posting — arriving while the post is
still being distributed.

Guardrails, since nothing is reviewed before it goes live:
  · Only posts published in the last WINDOW_HOURS, so a backlog never floods.
  · One comment per advocate per post, recorded in state/engaged.json and
    committed by the workflow. Reading the post's comments back from LinkedIn
    would be the authoritative check, but advocate tokens only carry
    w_member_social and GET /v2/socialActions/.../comments answers 403 for them.
  · An advocate never comments on a post authored from her own profile.
  · Generation failure means no comment. There is no generic fallback text:
    "מסכימה!" from three profiles in a row is what a comment pod looks like.

Usage: linkedin_engage.py [--dry-run]
"""
import datetime
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from publishers import queue, linkedin

WINDOW_HOURS = float(os.environ.get("ENGAGE_WINDOW_HOURS", "6"))
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEN_MODEL = os.environ.get("GEN_MODEL", "claude-sonnet-4-6")
ADVOCATE_NAMES = {"li_danielle": "דניאל", "li_natalia": "נטליה"}
STATE_PATH = os.path.join(ROOT, "state", "engaged.json")
# Posts worth amplifying: Alon's own profile and the company pages.
TARGET_ACCOUNTS = {"li_personal", "alon3153", "li_english", "li_spain"}


def recent_posts():
    """Published LinkedIn posts inside the window that carry a real post id."""
    since = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(hours=WINDOW_HOURS)).isoformat()
    rows = queue._req("GET", "post_approvals", params={
        "select": "id,day,account,lang,post_id,published_at,caption",
        "network": "eq.linkedin", "status": "eq.published",
        "published_at": f"gte.{since}", "order": "published_at.desc"})
    return [r for r in rows
            if r.get("post_id") and r.get("account") in TARGET_ACCOUNTS]


LANGS = {"he": "עברית", "en": "אנגלית", "es": "ספרדית"}


def comment_text(base_text, advocate_name, lang="he"):
    """A short, specific comment in the advocate's own voice, in the post's own
    language — the Spain page posts in Spanish and the company page in English,
    and a Hebrew comment under either reads as an outsider."""
    if not ANTHROPIC_API_KEY or not base_text:
        return ""
    language = LANGS.get(lang, "עברית")
    prompt = (
        f"להלן פוסט LinkedIn של Uproduction Events:\n\n"
        f"\"\"\"\n{base_text}\n\"\"\"\n\n"
        f"כתבי תגובה קצרה לפוסט הזה בקול של {advocate_name}, אשת צוות ב-UPE.\n"
        f"כללים:\n"
        f"- 1-2 משפטים בלבד, {language} טבעית ומדוברת\n"
        f"- התגובה חייבת להיות ב{language}, כמו הפוסט עצמו\n"
        f"- להוסיף זווית או דוגמה מהשטח, לא לחזור על מה שכתוב בפוסט\n"
        f"- בלי שבחים גנריים ('מעולה!', 'מסכימה לגמרי'), בלי אימוג'ים, בלי האשטגים\n"
        f"- בלי לפנות לאלון בשמו ובלי לחשוף שזו תגובה מתואמת\n"
        f"החזירי אך ורק את טקסט התגובה."
    )
    try:
        body = json.dumps({"model": GEN_MODEL, "max_tokens": 300,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=body,
            headers={"x-api-key": ANTHROPIC_API_KEY,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read().decode())
        return "".join(b.get("text", "") for b in resp.get("content", [])).strip()
    except Exception as e:
        print(f"  generation failed for {advocate_name}: {e}")
        return ""


def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)


def connected_advocates():
    out = {}
    for row in queue.list_advocates():
        account = row.get("account")
        if account not in ADVOCATE_NAMES:
            continue
        if not (row.get("access_token") and row.get("member_urn")):
            print(f"SKIP {account}: not connected")
            continue
        out[account] = row
    return out


def main():
    dry = "--dry-run" in sys.argv
    posts = recent_posts()
    if not posts:
        print(f"no LinkedIn posts published in the last {WINDOW_HOURS:g}h")
        return 0
    advocates = connected_advocates()
    if not advocates:
        print("no connected advocates")
        return 0
    state = load_state()

    done = 0
    for post in posts:
        urn = post["post_id"]
        print(f"\npost {urn} (day {post.get('day')}, {post.get('account')})")
        for account, adv in advocates.items():
            name = ADVOCATE_NAMES[account]
            if post.get("account") == account:
                continue  # never comment on your own post
            if account in state.get(urn, []):
                print(f"  {name}: already commented")
                continue
            text = comment_text(post.get("caption") or "", name,
                                post.get("lang") or "he")
            if not text:
                print(f"  {name}: SKIP — no comment generated")
                continue
            if dry:
                print(f"  [DRY] {name}: {text[:110]}")
                continue
            res = linkedin.create_comment(urn, text, adv["access_token"],
                                          adv["member_urn"])
            if res.get("success"):
                # Record before anything else can fail: a lost record is a
                # duplicate comment on the next run.
                state.setdefault(urn, []).append(account)
                save_state(state)
                print(f"  OK  {name}: {res.get('comment_id')}")
                done += 1
            else:
                print(f"  ERR {name}: {res.get('error')}")
    print(f"\ncommented {done}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
