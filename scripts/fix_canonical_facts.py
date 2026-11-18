#!/usr/bin/env python3
"""Rewrite retired company facts in already-published posts to the canonical ones.

Canonical (locked 22.06.2026): 16 years, 1,500+ events, 130+ destinations.
Retired variants still live in old posts: 15 years, 200+ events, 120+/20+ countries.

Default is a dry run that prints before/after for every affected post.
  --apply            edit the live post (Facebook, LinkedIn) and the stored caption
  --network/--account/--limit   narrow the run (use --limit 1 to trial an account)
Instagram has no caption-edit API: those rows are listed and must be edited by hand.
"""
import argparse, json, os, re, sys, urllib.error, urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

RULES = [
    # --- years ---
    (r"\bFifteen years", "Sixteen years"),
    (r"\b15\+? years", "16 years"),
    (r"\bQuince años", "Dieciséis años"),
    (r"\bquince años", "dieciséis años"),
    (r"\b15 años", "16 años"),
    (r"(?<!\d)15\+? (?:שנה|שנים)", "16 שנה"),
    # --- events (only company-track-record nouns; "200 guests"/"200+ hours" stay) ---
    (r"\b200\+ (events|productions|times|of these)", r"1,500+ \1"),
    (r"\bover 200 of them", "over 1,500 of them"),
    (r"\+200 (eventos|experiencias)", r"+1.500 \1"),
    (r"\b200\+ eventos", "1.500+ eventos"),
    (r"([Mm])ás de 200 (eventos|experiencias)", r"\1ás de 1.500 \2"),
    (r"(?<!\d)200\+ אירועים", "1,500+ אירועים"),
    (r"(מעל |יותר מ-)200 (אירועים|חוויות)", r"\g<1>1,500 \2"),
    # --- countries -> destinations ---
    (r"\b1?20\+ countries", "130+ destinations"),
    (r"\+120 países", "+130 destinos"),
    (r"([Mm])ás de 120 países", r"\1ás de 130 destinos"),
    (r"\b120 países", "130 destinos"),
    (r"\b20\+ países", "130+ destinos"),
    (r"משתתפים מ-120\+ מדינות", "משתתפים ב-130+ יעדים"),
    (r"(?<!\d)120\+ מדינות", "130+ יעדים"),
    (r"יותר מ-120 מדינות", "יותר מ-130 יעדים"),
]
RULES = [(re.compile(p), r) for p, r in RULES]
STALE = re.compile(r"(?<![\d.,])(?:200\+|\+200|120\+|\+120)|(?:más de|over|מעל|יותר מ-) ?(?:200|120)\b"
                   r"|\b15\+? (?:years|años)|(?<!\d)15\+? (?:שנה|שנים)|[Qq]uince años|\b20\+ (?:countries|países)")


def fix(text):
    for pat, rep in RULES:
        text = pat.sub(rep, text)
    return text


def changed_lines(old, new):
    return [(a, b) for a, b in zip(old.split("\n"), new.split("\n")) if a != b]


# ---------- live edits ----------
def edit_facebook(row, text):
    import requests
    key = row["account"].upper()
    token = os.environ.get(f"FB_{key}_PAGE_TOKEN")
    if not token:
        return False, f"missing FB_{key}_PAGE_TOKEN"
    r = requests.post(f"https://graph.facebook.com/v22.0/{row['post_id']}",
                      data={"message": text, "access_token": token}, timeout=60)
    ok = r.ok and r.json().get("success", False)
    return ok, "" if ok else f"HTTP {r.status_code}: {r.text[:200]}"


_LI_RESERVED = re.compile(r"([\\|{}@\[\]()<>*_~])")


def li_commentary(text):
    """LinkedIn 'little text': escape reserved chars, keep hashtags as hashtags."""
    out, pos = [], 0
    for m in re.finditer(r"#(\w+)", text):
        out.append(_LI_RESERVED.sub(r"\\\1", text[pos:m.start()]).replace("#", r"\#"))
        out.append("{hashtag|\\#|%s}" % m.group(1))
        pos = m.end()
    out.append(_LI_RESERVED.sub(r"\\\1", text[pos:]).replace("#", r"\#"))
    return "".join(out)


def edit_linkedin(row, text):
    from publishers import linkedin
    from scripts.publish_approved import _linkedin_target
    target = _linkedin_target(row["account"])
    if not target.get("ok"):
        return False, target.get("message", "bad route")
    token = target.get("token") or linkedin._token()
    url = f"{linkedin.API}/rest/posts/{urllib.parse.quote(row['post_id'], safe='')}"
    body = {"patch": {"$set": {"commentary": li_commentary(text)}}}
    err = "no API version accepted"
    # ponytail: probes a few monthly API versions; pin one once a run shows which is live
    for version in os.environ.get("LINKEDIN_API_VERSIONS", "202611,202610,202609,202608,202607").split(","):
        try:
            linkedin._req("POST", url, token, body=body,
                          extra={"LinkedIn-Version": version, "X-RestLi-Method": "PARTIAL_UPDATE"})
            return True, ""
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code} (v{version}): {e.read().decode()[:200]}"
            if e.code not in (400, 426) or "version" not in err.lower():
                break
    return False, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--network")
    ap.add_argument("--account")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    from publishers import queue
    params = {"select": "id,network,account,lang,post_id,caption,published_at",
              "status": "eq.published", "order": "published_at.asc", "limit": "5000"}
    if a.network:
        params["network"] = f"eq.{a.network}"
    if a.account:
        params["account"] = f"eq.{a.account}"
    todo = [(r, fix(r["caption"] or "")) for r in queue._req("GET", "post_approvals", params=params)]
    todo = [(r, new) for r, new in todo if new != r["caption"]]
    if a.limit:
        todo = todo[:a.limit]
    done = failed = manual = 0
    for r, new in todo:
        label = f"{r['network']}/{r['account']} {str(r['published_at'])[:10]} {r['post_id']}"
        print(f"\n== {label}")
        for old_line, new_line in changed_lines(r["caption"], new):
            print(f"  - {old_line}\n  + {new_line}")
        if STALE.search(new):
            print("  WARN still contains a retired figure after rewrite")
        if not a.apply:
            continue
        if r["network"] == "instagram":
            manual += 1
            print("  MANUAL instagram has no caption-edit API")
            continue
        ok, err = (edit_facebook if r["network"] == "facebook" else edit_linkedin)(r, new)
        if ok:
            queue.mark(r["id"], caption=new)
            done += 1
            print("  EDITED")
        else:
            failed += 1
            print(f"  FAILED {err}")
    print(f"\n{len(todo)} post(s) need a rewrite; edited {done}, failed {failed}, manual {manual}"
          + ("" if a.apply else " (dry run)"))
    return 1 if failed else 0


def demo():
    assert fix("15 years, 200+ events, 120+ countries") == "16 years, 1,500+ events, 130+ destinations"
    assert fix("After 16 years, 200+ events, and 20+ countries") == "After 16 years, 1,500+ events, and 130+ destinations"
    assert fix("Tras +200 eventos en 120 países") == "Tras +1.500 eventos en 130 destinos"
    assert fix("Quince años, más de 200 eventos, más de 120 países") == "Dieciséis años, más de 1.500 eventos, más de 130 destinos"
    assert fix("15 שנה, 200+ אירועים, 120+ מדינות") == "16 שנה, 1,500+ אירועים, 130+ יעדים"
    assert fix("אחרי יותר מ-200 אירועים ביותר מ-120 מדינות") == "אחרי יותר מ-1,500 אירועים ביותר מ-130 יעדים"
    for keep in ("200+ internal hours", "200 guests arrive late", "1,500+ events across 130+ destinations",
                 "800 personas, 3 países", "16 years"):
        assert fix(keep) == keep, keep
    assert fix(fix("15+ years and 200+ events")) == fix("15+ years and 200+ events")
    assert li_commentary("a (b) #Tag_x") == r"a \(b\) {hashtag|\#|Tag_x}"
    print("self-check OK")


if __name__ == "__main__":
    demo() if sys.argv[1:] == ["--self-check"] else sys.exit(main())
