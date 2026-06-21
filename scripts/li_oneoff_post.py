#!/usr/bin/env python3
"""One-off LinkedIn post to a specific org/page using the stored token.
Caption is passed base64-encoded in LI_CAPTION_B64; target org in LI_ORG_URN
(empty -> personal profile). Used for verification posts; not part of the cron."""
import os, sys, base64
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from publishers import linkedin


def _diag():
    import json, urllib.request, urllib.error
    from publishers import linkedin as L
    tok = L._token()
    UA = L.UA
    # member identity
    try:
        print("member:", L.member_urn(tok))
    except Exception as e:
        print("member err:", e)
    # full ACL roles + states
    url = ("https://api.linkedin.com/v2/organizationAcls?q=roleAssignee"
           "&projection=(elements*(role,state,organization~(localizedName)))")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}",
        "User-Agent": UA, "X-Restli-Protocol-Version": "2.0.0"})
    try:
        d = json.loads(urllib.request.urlopen(req).read().decode())
        for el in d.get("elements", []):
            nm = (el.get("organization~", {}) or {}).get("localizedName", "?")
            print(f"  {el.get('organization')} | role={el.get('role')} state={el.get('state')} | {nm}")
    except urllib.error.HTTPError as e:
        print("acls err:", e.code, e.read().decode()[:200])
    return 0


def main():
    cap = base64.b64decode(os.environ.get("LI_CAPTION_B64", "")).decode("utf-8")
    if cap.strip() == "__DIAG__":
        return _diag()
    org = os.environ.get("LI_ORG_URN") or None
    img = os.environ.get("LI_IMAGE_URL") or None
    if not cap.strip():
        print("no caption"); return 1
    print(f"posting to org={org or 'PERSONAL'} ({len(cap)} chars)")
    res = linkedin.publish_post(cap, image_url=img, org_urn=org)
    print(res)
    return 0 if res.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
