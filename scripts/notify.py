#!/usr/bin/env python3
"""
Send a notification email — used by GitHub Actions on failure.

Two backends supported (auto-detected based on env vars):
  1. Microsoft Graph (preferred — uses existing UPE Outlook OAuth)
     Requires: MS_GRAPH_TENANT_ID, MS_GRAPH_CLIENT_ID, MS_GRAPH_CLIENT_SECRET, MS_GRAPH_FROM
  2. Resend HTTP API
     Requires: RESEND_API_KEY, NOTIFY_FROM, NOTIFY_TO

Usage:
  echo "body" | python3 scripts/notify.py --subject "alert subject"
  python3 scripts/notify.py --subject "alert" --body "..."
"""

import os
import sys
import json
import argparse
import requests

DEFAULT_TO = "alon@uproduction.co.il"


def send_via_graph(subject: str, body: str) -> bool:
    tenant = os.environ.get("MS_GRAPH_TENANT_ID")
    client_id = os.environ.get("MS_GRAPH_CLIENT_ID")
    secret = os.environ.get("MS_GRAPH_CLIENT_SECRET")
    sender = os.environ.get("MS_GRAPH_FROM")
    if not all([tenant, client_id, secret, sender]):
        return False

    # Client-credentials OAuth flow
    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    r = requests.post(token_url, data={
        "client_id": client_id,
        "client_secret": secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }, timeout=30)
    if r.status_code != 200:
        print(f"[notify] OAuth failed: HTTP {r.status_code}", file=sys.stderr)
        return False
    access_token = r.json().get("access_token")

    send_url = f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail"
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": os.environ.get("NOTIFY_TO", DEFAULT_TO)}}],
        },
        "saveToSentItems": True,
    }
    r = requests.post(send_url, headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}, json=payload, timeout=30)
    if r.status_code in (200, 202):
        print(f"[notify] Email sent via Graph to {os.environ.get('NOTIFY_TO', DEFAULT_TO)}")
        return True
    print(f"[notify] Graph sendMail failed: HTTP {r.status_code}: {r.text[:300]}", file=sys.stderr)
    return False


def send_via_resend(subject: str, body: str) -> bool:
    key = os.environ.get("RESEND_API_KEY")
    sender = os.environ.get("NOTIFY_FROM")
    if not key or not sender:
        return False

    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "from": sender,
            "to": [os.environ.get("NOTIFY_TO", DEFAULT_TO)],
            "subject": subject,
            "text": body,
        },
        timeout=30,
    )
    if r.status_code in (200, 201):
        print(f"[notify] Email sent via Resend to {os.environ.get('NOTIFY_TO', DEFAULT_TO)}")
        return True
    print(f"[notify] Resend failed: HTTP {r.status_code}: {r.text[:300]}", file=sys.stderr)
    return False


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--subject", required=True)
    p.add_argument("--body", help="Body text (or pipe via stdin)")
    args = p.parse_args()

    body = args.body if args.body else sys.stdin.read()

    # Try Graph first, fall back to Resend
    if send_via_graph(args.subject, body):
        return 0
    if send_via_resend(args.subject, body):
        return 0

    print("[notify] No notification backend configured. Set MS_GRAPH_* or RESEND_API_KEY.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
