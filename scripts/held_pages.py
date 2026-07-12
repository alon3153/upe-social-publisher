"""Founder-veto window for competitor-naming pages (council decision 05.07).

A page that names a competitor carries brand/legal risk, so it is not
auto-merged on the spot. Instead it is HELD here with a timestamp, surfaced in
the weekly approval digest, and merged automatically once the veto window
elapses — unless Alon vetoes it first. This implements the "חלון וטו 24 שעות
לפני merge" the master plan describes; previously such pages were silently
dropped every run and could never publish.

States: awaiting_veto -> (merged | vetoed).
- hold(pages, today): persist newly-held pages (keeps the original held_since
  so the window can't be reset by re-generation).
- due_for_merge(today): pages whose window elapsed and were not vetoed.
- release(slugs): drop merged pages from the store.
- veto(slug): block a page permanently.
- digest_html(today): RTL section for the weekly email.
"""
import json, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT.parent / "state" / "held_pages.json"
VETO_DAYS = 1  # council: 24h founder-veto window before auto-merge


def load(path=None):
    p = Path(path) if path else STATE
    if not p.exists():
        return {"updated": "", "held": [], "vetoed": []}
    return json.loads(p.read_text(encoding="utf-8"))


def save(data, path=None):
    p = Path(path) if path else STATE
    p.parent.mkdir(parents=True, exist_ok=True)
    data["updated"] = datetime.date.today().isoformat()
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _slugs(items):
    return {i["slug"] for i in items}


def hold(pages, today, path=None):
    """Persist newly-held competitor-naming pages. Idempotent by slug: an
    already-held page keeps its original held_since (the window never resets),
    and a vetoed page is never re-held."""
    data = load(path)
    held_slugs = _slugs(data["held"])
    vetoed = set(data.get("vetoed", []))
    added = []
    for page in pages:
        slug = page["slug"]
        if slug in held_slugs or slug in vetoed:
            continue
        data["held"].append({
            "slug": slug,
            "frontmatter": page.get("frontmatter", {}),
            "body": page.get("body", ""),
            "violations": page.get("violations", []),
            "competitors": page.get("_competitors", page.get("competitors", [])),
            "held_since": today,
            "state": "awaiting_veto",
        })
        added.append(slug)
    if added:
        save(data, path)
    return added


def _days_between(a, b):
    return (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days


def due_for_merge(today, path=None, window_days=VETO_DAYS):
    data = load(path)
    vetoed = set(data.get("vetoed", []))
    out = []
    for h in data["held"]:
        if h["state"] != "awaiting_veto" or h["slug"] in vetoed:
            continue
        if _days_between(h["held_since"], today) >= window_days:
            # shape it back into a publishable page dict
            out.append({"slug": h["slug"], "frontmatter": h["frontmatter"],
                        "body": h["body"], "violations": h.get("violations", [])})
    return out


def release(slugs, path=None):
    """Remove merged pages from the store."""
    data = load(path)
    slugs = set(slugs)
    before = len(data["held"])
    data["held"] = [h for h in data["held"] if h["slug"] not in slugs]
    if len(data["held"]) != before:
        save(data, path)
    return before - len(data["held"])


def veto(slug, path=None):
    data = load(path)
    data.setdefault("vetoed", [])
    if slug not in data["vetoed"]:
        data["vetoed"].append(slug)
    data["held"] = [h for h in data["held"] if h["slug"] != slug]
    save(data, path)
    return True


def digest_html(today, path=None):
    """RTL section for the weekly email: what's held, when it auto-merges,
    and how to veto."""
    data = load(path)
    awaiting = [h for h in data["held"] if h["state"] == "awaiting_veto"
                and h["slug"] not in set(data.get("vetoed", []))]
    if not awaiting:
        return ""

    def row(h):
        merge_on = (datetime.date.fromisoformat(h["held_since"])
                    + datetime.timedelta(days=VETO_DAYS)).isoformat()
        due = "עכשיו" if _days_between(h["held_since"], today) >= VETO_DAYS else merge_on
        comps = ", ".join(h.get("competitors", []))
        title = h.get("frontmatter", {}).get("title", h["slug"])
        return (f'<tr><td dir="rtl" style="padding:4px 8px;">{title}</td>'
                f'<td dir="rtl" style="padding:4px 8px;"><span dir="ltr">{comps}</span></td>'
                f'<td dir="rtl" style="padding:4px 8px;">{due}</td></tr>')

    head = ('<tr><th dir="rtl" style="padding:4px 8px;">עמוד (מזכיר מתחרים)</th>'
            '<th dir="rtl" style="padding:4px 8px;">מתחרים שהוזכרו</th>'
            '<th dir="rtl" style="padding:4px 8px;">מתמזג ב־</th></tr>')
    return ('<h4 dir="rtl">⚖️ עמודים בחלון וטו־מייסד (מתמזגים אוטומטית אלא אם תווטא)</h4>'
            f'<table dir="rtl" style="border-collapse:collapse;border:1px solid #ddd;">{head}'
            + "".join(row(h) for h in awaiting) + "</table>"
            '<p dir="rtl" style="color:#946200;">לווטו על עמוד: '
            '<span dir="ltr">python scripts/held_pages.py veto &lt;slug&gt;</span></p>')


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "veto":
        veto(sys.argv[2])
        print(f"vetoed: {sys.argv[2]}")
    else:
        d = load()
        print(f"held: {len(d['held'])} · vetoed: {len(d.get('vetoed', []))}")
        for h in d["held"]:
            print(f"  {h['state']:14} {h['slug']} (since {h['held_since']})")
