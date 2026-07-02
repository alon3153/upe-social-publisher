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


def _soql_records(query, token, base):
    url = f"{base}/services/data/{APIV}/query?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode()).get("records", [])


# Concentration in one of these buckets is a DATA-ENTRY artifact (the picklist default /
# blank) — the attribution is uninformative. Concentration in a REAL chosen source
# (Web, Linkedin, Word of mouth...) is a market SIGNAL, not a gap. Ported from the
# retired Dropbox council 02.07 so the cloud council reasons about it identically.
_UNATTRIBUTED = {"Advertisement", "(none)", "Other"}


def _attribution(records):
    by_source = {}
    for r in records:
        s = r.get("LeadSource") or "(none)"
        by_source[s] = by_source.get(s, 0) + 1
    total = len(records)
    if not total:
        return {"by_source": {}, "dominant_source": None, "dominant_share_pct": 0,
                "attribution_gap": False, "attribution_note": "no opportunities in window"}
    dom = max(by_source.items(), key=lambda x: x[1])
    concentrated = dom[1] / total >= 0.8
    gap = bool(concentrated and dom[0] in _UNATTRIBUTED)
    if gap:
        note = (f"{dom[1]}/{total} תויגו '{dom[0]}' (ברירת-מחדל / לא-מיוחס) — הייחוס לא אינפורמטיבי. "
                "להקפיד לתייג מקור אמיתי בכל עסקה חדשה.")
    elif concentrated:
        note = (f"{dom[1]}/{total} מקורם '{dom[0]}' — זה הערוץ הממיר. להכפיל בו את ההשקעה"
                + (" — להאיץ SEO/תוכן אורגני מסחרי בעברית." if dom[0] == "Web" else "."))
    else:
        note = "הייחוס מפוזר בין מספר מקורות"
    return {"by_source": by_source, "dominant_source": dom[0],
            "dominant_share_pct": round(dom[1] / total * 100), "attribution_gap": gap,
            "attribution_note": note}


def count(days=30):
    if not (INSTANCE and CID and SECRET):
        return {"ok": False, "reason": "SALESFORCE_* secrets not set",
                "qualified_leads": None, "new_opportunities": None, "source": "salesforce"}
    n = max(int(days), 1)
    try:
        token, base = _token()
        # KPI definition (Alon's choice "א", 28.06): every NEW Opportunity created in
        # the window counts as a lead — UPE works in Opportunity, not the Lead object.
        # Fetch records (not just COUNT) so we can break down by LeadSource for attribution.
        recs = _soql_records(
            f"SELECT Id, LeadSource FROM Opportunity WHERE CreatedDate = LAST_N_DAYS:{n}",
            token, base)
        opps = len(recs)
        attr = _attribution(recs)
        # Lead-object count kept as a secondary signal (typically 0 — not used by UPE).
        leads_obj = _soql_count(
            f"SELECT COUNT() FROM Lead WHERE CreatedDate = LAST_N_DAYS:{n} AND IsConverted = false",
            token, base)
        return {"ok": True, "qualified_leads": opps, "new_opportunities": opps,
                "lead_object_count": leads_obj, "period_days": n, "source": "salesforce",
                "definition": "new Opportunities created (all)", **attr}
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
