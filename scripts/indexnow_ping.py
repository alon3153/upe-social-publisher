"""Ping IndexNow (Bing/Copilot and friends) the moment the loop ships new pages.
The key file is deployed at https://upe.co.il/<key>.txt (astro public/).

COVERAGE GAP (07.08.2026): ping() is called from exactly one place — aeo_run.py, i.e.
only for pages the weekly AEO loop itself generates. Every other route that puts a URL
on upe.co.il never pings:
  * uproduction-astro .github/workflows/generate-articles.yml (weekly SEO articles)
  * upe_astro_pending_publisher.py (SEO annual engine → PR → auto-merge)
  * any manually merged content PR
Those are the bulk of new URLs (238 blog files live), so Bing/Copilot discover them on
their own crawl schedule instead of within minutes — a free, immediate distribution
channel left on the table.

`sitemap_delta()` closes that gap publisher-agnostically: it diffs the live sitemap
against the last-seen set and returns only URLs that are genuinely new, so ONE caller
covers every publishing path, no matter who shipped the page. Wire it to a scheduler
only with Alon's approval — it makes an outbound request to a third party.

CLI:
  python3 scripts/indexnow_ping.py --urls https://upe.co.il/a/ https://upe.co.il/b/
  python3 scripts/indexnow_ping.py --from-sitemap --dry-run
"""
import os, re, json, argparse, urllib.request
from pathlib import Path

HOST = "upe.co.il"
DEFAULT_KEY = "602088c5a1792407df46dcfc3b814fdc"  # public by protocol design (served on the site)
SEEN_STATE = Path(__file__).resolve().parent.parent / "state" / "indexnow_seen.json"


def ping(urls, key=None, host=HOST, _http=None):
    if not urls:
        return False
    key = key or os.environ.get("INDEXNOW_KEY") or DEFAULT_KEY
    body = json.dumps({"host": host, "key": key,
                       "keyLocation": f"https://{host}/{key}.txt",
                       "urlList": list(urls)}).encode()

    def _post(data):
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=data,
                                     headers={"content-type": "application/json; charset=utf-8"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status

    status = (_http or _post)(body)
    return status in (200, 202)


def _fetch_sitemap(host=HOST):
    req = urllib.request.Request(f"https://{host}/sitemap.xml",
                                 headers={"User-Agent": "upe-indexnow"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", errors="replace")


def sitemap_urls(host=HOST, _fetch=None):
    xml = (_fetch or _fetch_sitemap)(host)
    return [u.strip() for u in re.findall(r"<loc>\s*(.*?)\s*</loc>", xml, re.S) if u.strip()]


def sitemap_delta(host=HOST, state_path=None, _fetch=None, record=True):
    """URLs in the live sitemap that were not there on the previous check.

    First ever run records the whole sitemap WITHOUT returning it: pinging 300 existing
    URLs as "new" is spam that buys nothing and risks the host being throttled."""
    p = Path(state_path) if state_path else SEEN_STATE
    try:
        seen = set(json.loads(p.read_text(encoding="utf-8")).get("urls", []))
    except (FileNotFoundError, ValueError):
        seen = set()
    current = sitemap_urls(host, _fetch=_fetch)
    new = [] if not seen else [u for u in current if u not in seen]
    if record:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"host": host, "urls": sorted(current)},
                                ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    return new


def main(argv=None):
    ap = argparse.ArgumentParser(description="Push URLs to IndexNow (Bing/Copilot).")
    ap.add_argument("--urls", nargs="*", default=[])
    ap.add_argument("--from-sitemap", action="store_true",
                    help="ping only URLs added to sitemap.xml since the last run")
    ap.add_argument("--dry-run", action="store_true", help="print what would be pinged")
    a = ap.parse_args(argv)

    urls = list(a.urls)
    if a.from_sitemap:
        urls += sitemap_delta(record=not a.dry_run)
    urls = sorted(set(urls))
    if not urls:
        print("indexnow: nothing new to submit")
        return 0
    if a.dry_run:
        print("indexnow (dry-run) would submit:\n  " + "\n  ".join(urls))
        return 0
    ok = ping(urls)
    print(f"indexnow: submitted {len(urls)} url(s) — {'accepted' if ok else 'REJECTED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
