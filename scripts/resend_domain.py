#!/usr/bin/env python3
"""Resend domain setup helper.

Lists Resend domains; if upe.co.il is absent, creates it; then prints the
exact DNS records to add (SPF / DKIM / DMARC) and the current verification
status. Run via the resend-domain GitHub Action so RESEND_API_KEY stays a
secret.

Env:
  RESEND_API_KEY   (required)
  RESEND_DOMAIN    domain to ensure, default upe.co.il
  RESEND_REGION    create region, default eu-west-1
"""
import os
import sys
import json
import urllib.request
import urllib.error

API = "https://api.resend.com"
KEY = os.environ.get("RESEND_API_KEY", "")
DOMAIN = os.environ.get("RESEND_DOMAIN", "upe.co.il")
REGION = os.environ.get("RESEND_REGION", "eu-west-1")


def _req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method,
                                 headers={"Authorization": f"Bearer {KEY}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:400]}


def find_domain():
    status, body = _req("GET", "/domains")
    if status != 200:
        print(f"❌ list domains HTTP {status}: {body}")
        sys.exit(1)
    for d in body.get("data", []):
        if d.get("name") == DOMAIN:
            return d
    return None


def print_records(detail):
    print(f"\nDomain: {detail.get('name')}  |  status: {detail.get('status')}  |  region: {detail.get('region')}")
    recs = detail.get("records", [])
    if not recs:
        print("(no records returned)")
        return
    print("\n--- DNS records to add at your registrar ---")
    for rec in recs:
        rtype = rec.get("type", "")
        name = rec.get("name", "")
        value = rec.get("value", "")
        ttl = rec.get("ttl", "Auto")
        priority = rec.get("priority", "")
        status = rec.get("status", "")
        print(f"\n  TYPE     : {rtype}")
        print(f"  NAME/HOST: {name}")
        print(f"  VALUE    : {value}")
        if priority != "":
            print(f"  PRIORITY : {priority}")
        print(f"  TTL      : {ttl}")
        print(f"  STATUS   : {status}")


def main():
    if not KEY:
        print("❌ Missing RESEND_API_KEY")
        return 1
    d = find_domain()
    if d is None:
        print(f"Domain {DOMAIN} not found — creating (region {REGION})…")
        status, body = _req("POST", "/domains", {"name": DOMAIN, "region": REGION})
        if status not in (200, 201):
            print(f"❌ create HTTP {status}: {body}")
            return 1
        d = body
    else:
        # fetch full detail (records) by id
        status, body = _req("GET", f"/domains/{d['id']}")
        if status == 200:
            d = body
    print_records(d)
    # trigger verification (idempotent)
    if d.get("status") != "verified":
        vs, vb = _req("POST", f"/domains/{d['id']}/verify")
        print(f"\nVerification triggered: HTTP {vs}")
    print(f"\nAfter adding the records, re-run this workflow to confirm status=verified.")
    print(f"Then set the RESEND_FROM secret to: noreply@{DOMAIN}  (e.g. 'Uproduction <noreply@{DOMAIN}>')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
