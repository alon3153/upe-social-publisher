import json
import scripts.indexnow_ping as ix


def test_ping_posts_urllist():
    captured = {}

    def fake_http(data):
        captured.update(json.loads(data))
        return 200

    assert ix.ping(["https://upe.co.il/a/", "https://upe.co.il/b/"], key="k", _http=fake_http)
    assert captured["host"] == "upe.co.il" and len(captured["urlList"]) == 2
    assert captured["keyLocation"] == "https://upe.co.il/k.txt"


def test_ping_empty_is_noop():
    assert ix.ping([]) is False
