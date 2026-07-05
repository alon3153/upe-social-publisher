"""Ping IndexNow (Bing/Copilot and friends) the moment the loop ships new pages.
The key file is deployed at https://upe.co.il/<key>.txt (astro public/)."""
import os, json, urllib.request

HOST = "upe.co.il"
DEFAULT_KEY = "602088c5a1792407df46dcfc3b814fdc"  # public by protocol design (served on the site)


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
