#!/usr/bin/env python3
"""
Lead measurement for the daily council — turns the PRIMARY KPI (10 real new
qualified leads/month) from "not connected" into a measured number.

Source: Salesforce REST (client-credentials flow — matches UPE's existing SF
integration). Counts NEW Leads + NEW Opportunities created in the period.

Credentials (env / GH secrets — add to upe-social-publisher to activate in cloud):
  SALESFORCE_INSTANCE_URL   e.g. https://upe.my.salesforce.com
  SALESFORCE_CLIENT_ID
  SALESFORCE_CLIENT_SECRET
  SALESFORCE_API_VERSION    optional, default v60.0

Degrades gracefully: if creds are absent or SF errors, returns ok=False with a
reason and the council shows the KPI as still-unwired (never fabricates a number).

CLI:  python3 scripts/leads_source.py --days 30
"""
import os, sys, json, argparse, urllib.request, urllib.parse, urllib.error

INSTANCE = os.environ.get("SALESFORCE_INSTANCE_URL", "").rstrip("/")
CID = os.environ.get("SALESFORCE_CLIENT_ID", "")
SECRET = os.environ.get("SALESFORCE_CLIENT_SECRET", "")
APIV = os.environ.get("SALESFORCE_API_VERSION", "v60.0")


def _token():
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": CID, "client_secret": SECRET}).encode()
    req = urllib.request.Request(f"{INSTANCE}/services/oauth2/token", data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=60) as r:
        j = json.loads(r.read().decode())
    return j["access_token"], j.get("instance_url", INSTANCE).rstrip("/")


def _soql_count(query, token, base):
    url = f"{base}/services/data/{APIV}/query?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode()).get("totalSize", 0)


def count(days=30):
    if not (INSTANCE and CID and SECRET):
        return {"ok": False, "reason": "SALESFORCE_* secrets not set",
                "qualified_leads": None, "new_opportunities": None, "source": "salesforce"}
    n = max(int(days), 1)
    try:
        token, base = _token()
        # NEW inbound leads in the window (not yet converted) + NEW opportunities created.
        leads = _soql_count(
            f"SELECT COUNT() FROM Lead WHERE CreatedDate = LAST_N_DAYS:{n} AND IsConverted = false",
            token, base)
        opps = _soql_count(
            f"SELECT COUNT() FROM Opportunity WHERE CreatedDate = LAST_N_DAYS:{n}",
            token, base)
        return {"ok": True, "qualified_leads": leads, "new_opportunities": opps,
                "period_days": n, "source": "salesforce"}
    except urllib.error.HTTPError as e:
        return {"ok": False, "reason": f"SF HTTP {e.code}: {e.read().decode()[:160]}",
                "qualified_leads": None, "new_opportunities": None, "source": "salesforce"}
    except Exception as e:
        return {"ok": False, "reason": f"SF error: {e}",
                "qualified_leads": None, "new_opportunities": None, "source": "salesforce"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    a = ap.parse_args()
    print(json.dumps(count(a.days), ensure_ascii=False, indent=2))
