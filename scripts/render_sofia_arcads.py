#!/usr/bin/env python3
"""Render a Sofia UGC batch through the Arcads external API (Seedance 2.0).

Reads a batch spec from content/sofia/prompts/<batch>.json, generates one
vertical 9:16 clip per ad, polls until each asset is ready, and writes
content/sofia/queue/<batch>.json in the shape scripts/enqueue_sofia.py expects.

    python3 scripts/render_sofia_arcads.py week2 --dry-run   # payloads + cost, no calls
    python3 scripts/render_sofia_arcads.py week2             # generate for real

Auth comes from .env (gitignored) or the environment:
    ARCADS_BASIC_AUTH='Basic <base64>'   preferred — avoids encoding issues
    ARCADS_API_KEY=<key>                 used as HTTP Basic username, empty password
    ARCADS_PRODUCT_ID=<uuid>             target Arcads product

Seedance 2.0 is billed per second and is not cheap. Nothing is generated
without --yes or an interactive confirmation.
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL = os.environ.get("ARCADS_BASE_URL", "https://external-api.arcads.ai")
LOG_PATH = os.path.join(ROOT, "logs", "arcads-api.jsonl")

# Seedance 2.0 image-to-video at 720p, re-validated upstream 2026-05-19 across 8
# production runs. The older ~0.06/sec figure in the vendor summary table was off
# by two orders of magnitude. Treat this as an ESTIMATE and confirm in-platform.
CREDITS_PER_SECOND = 48.0

POLL_INTERVAL_SEC = 15
POLL_TIMEOUT_SEC = 900  # Seedance runs 2-6 min; allow headroom


def load_dotenv():
    """Minimal .env reader — no dependency on python-dotenv."""
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
                val = val[1:-1]
            os.environ.setdefault(key, val)


def auth_header():
    pre = os.environ.get("ARCADS_BASIC_AUTH", "").strip()
    if pre:
        return pre if pre.lower().startswith("basic ") else f"Basic {pre}"
    key = os.environ.get("ARCADS_API_KEY", "").strip()
    if key:
        return "Basic " + base64.b64encode(f"{key}:".encode()).decode()
    sys.exit(
        "No Arcads credentials. Copy .agents/shared/arcads.env.example to .env and set\n"
        "ARCADS_BASIC_AUTH (preferred) or ARCADS_API_KEY. Key: app.arcads.ai/settings/api\n"
        "No account yet: https://arcads.ai/?via=claude-code"
    )


def api(method, path, payload=None, timeout=60):
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", auth_header())
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()[:400]
        hint = {
            401: "check ARCADS_API_KEY / ARCADS_BASIC_AUTH",
            403: "key rejected — try the pre-encoded ARCADS_BASIC_AUTH form",
            404: "wrong id — re-fetch the product list",
            422: "validation or moderation — check duration/aspectRatio and tighten the prompt",
        }.get(exc.code, "")
        sys.exit(f"HTTP {exc.code} on {method} {path}{' — ' + hint if hint else ''}\n{body}")


def log_event(record):
    """Append one JSONL row. Never logs prompt text, keys or auth headers."""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_payload(ad, product_id, project_id=None):
    r = ad["render"]
    payload = {
        "model": r["model"],
        "productId": product_id,
        "prompt": r["prompt"],
        "duration": r["duration"],
        "resolution": r["resolution"],
        "aspectRatio": r["aspectRatio"],
        "audioEnabled": r["audioEnabled"],
    }
    refs = [x for x in r.get("referenceImages") or [] if x]
    if refs:
        # Seedance 2.0 rejects referenceImages + referenceVideos together (HTTP 500).
        if r.get("referenceVideos"):
            sys.exit(f"{ad['id']}: Seedance 2.0 cannot combine referenceImages and referenceVideos")
        payload["referenceImages"] = refs[:3]
    if project_id:
        payload["projectId"] = project_id
    return payload


def poll_asset(asset_id):
    waited = 0
    while waited < POLL_TIMEOUT_SEC:
        asset = api("GET", f"/v1/assets/{asset_id}")
        status = asset.get("status")
        if status == "generated":
            return asset
        if status == "failed":
            return asset
        time.sleep(POLL_INTERVAL_SEC)
        waited += POLL_INTERVAL_SEC
    return {"status": "timeout", "id": asset_id}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch", nargs="?", default="week2")
    ap.add_argument("--dry-run", action="store_true", help="print payloads and cost, call nothing")
    ap.add_argument("--yes", action="store_true", help="skip the interactive cost confirmation")
    ap.add_argument("--only", help="comma-separated ad ids to render")
    args = ap.parse_args()

    load_dotenv()
    spec_path = os.path.join(ROOT, "content", "sofia", "prompts", f"{args.batch}.json")
    spec = json.load(open(spec_path, encoding="utf-8"))
    ads = spec["ads"]
    if args.only:
        wanted = {x.strip() for x in args.only.split(",")}
        ads = [a for a in ads if a["id"] in wanted]
        if not ads:
            sys.exit(f"No ads matched --only {args.only}")

    total_sec = sum(a["render"]["duration"] for a in ads)
    est = total_sec * CREDITS_PER_SECOND
    print(f"Batch {args.batch}: {len(ads)} clips, {total_sec}s total")
    for a in ads:
        r = a["render"]
        print(f"  {a['id']:22} {r['model']} {r['duration']}s {r['resolution']} {r['aspectRatio']} "
              f"audio={r['audioEnabled']}  ~{r['duration'] * CREDITS_PER_SECOND:.0f} credits")
    print(f"\nEstimated total: ~{est:.0f} credits at ~{CREDITS_PER_SECOND:.0f}/sec (Seedance 2.0 720p).")
    print("ESTIMATE ONLY — Arcads exposes no billing endpoint. Confirm in-platform before generating.")

    if args.dry_run:
        print("\n--dry-run: no API calls made. First payload:\n")
        print(json.dumps(build_payload(ads[0], "<ARCADS_PRODUCT_ID>"), indent=2, ensure_ascii=False)[:1400])
        return

    if not args.yes:
        if input("\nProceed and spend these credits? (yes/no) ").strip().lower() not in ("yes", "y"):
            sys.exit("Aborted — nothing generated.")

    product_id = os.environ.get("ARCADS_PRODUCT_ID", "").strip()
    if not product_id:
        products = api("GET", "/v1/products")
        items = products if isinstance(products, list) else products.get("data", [])
        if len(items) == 1:
            product_id = items[0]["id"]
            print(f"Using the only product: {items[0].get('name')} ({product_id})")
        else:
            for p in items:
                print(f"  {p.get('id')}  {p.get('name')}")
            sys.exit("Several products found. Set ARCADS_PRODUCT_ID in .env to the one you want.")

    project_id = os.environ.get("ARCADS_PROJECT_ID", "").strip() or None

    created = []
    for ad in ads:
        payload = build_payload(ad, product_id, project_id)
        resp = api("POST", "/v2/videos/generate", payload)
        asset_id = resp.get("id") or resp.get("assetId")
        r = ad["render"]
        log_event({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "batch": args.batch, "adId": ad["id"], "assetId": asset_id,
            "model": r["model"], "duration": r["duration"], "resolution": r["resolution"],
            "aspectRatio": r["aspectRatio"], "audioEnabled": r["audioEnabled"],
            "referenceImagesCount": len(payload.get("referenceImages", [])),
            "promptWordCount": len(r["prompt"].split()),
            "type": resp.get("type"),
        })
        print(f"  queued {ad['id']} -> asset {asset_id} (type={resp.get('type')})")
        created.append((ad, asset_id))

    print("\nPolling (Seedance typically takes 2-6 min per clip)...")
    queue_rows, failures = [], []
    for ad, asset_id in created:
        asset = poll_asset(asset_id)
        status = asset.get("status")
        video_url = asset.get("url")
        log_event({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "batch": args.batch, "adId": ad["id"], "assetId": asset_id,
            "response": {
                "status": status,
                "creditsCharged": asset.get("creditsCharged"),
                "videoUrl": video_url,
                "thumbnailUrl": asset.get("thumbnailUrl"),
                "error": asset.get("error"),
            },
        })
        if status == "generated" and video_url:
            print(f"  ok      {ad['id']}  {asset.get('creditsCharged')} credits")
            queue_rows.append({
                "day": ad["day"],
                "headline": ad["headline"],
                "video_url": video_url,
                "accounts": ad["accounts"],
                "scheduled_date": ad["scheduled_date"],
                "caption": ad["caption"],
            })
        else:
            print(f"  FAILED  {ad['id']}  status={status} {asset.get('error') or ''}")
            failures.append(ad["id"])

    if queue_rows:
        out = os.path.join(ROOT, "content", "sofia", "queue", f"{args.batch}.json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(queue_rows, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"\nWrote {len(queue_rows)} rows to {os.path.relpath(out, ROOT)}")
        print("Next, per clip:")
        print(f"  python3 scripts/brand_video_overlay.py <raw.mp4> <branded.mp4> --batch {args.batch} --ad <id>")
        print(f"Then: python3 scripts/enqueue_sofia.py {args.batch}")
    if failures:
        print(f"Failed: {', '.join(failures)} — rerun with --only {','.join(failures)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
