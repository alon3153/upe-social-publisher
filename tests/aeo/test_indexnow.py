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


SITEMAP = """<urlset><url><loc>https://upe.co.il/a/</loc></url>
<url><loc>https://upe.co.il/b/</loc></url></urlset>"""


def test_sitemap_urls_parses_locs():
    assert ix.sitemap_urls(_fetch=lambda h: SITEMAP) == ["https://upe.co.il/a/", "https://upe.co.il/b/"]


def test_sitemap_delta_first_run_records_but_pings_nothing(tmp_path):
    # Pinging every already-indexed URL as "new" is spam, not a win.
    state = tmp_path / "seen.json"
    assert ix.sitemap_delta(state_path=state, _fetch=lambda h: SITEMAP) == []
    assert state.exists()


def test_sitemap_delta_returns_only_added_urls(tmp_path):
    # This is the publisher-agnostic hook: ANY route that ships a page (AEO loop,
    # generate-articles, the pending publisher, a manual merge) shows up here.
    state = tmp_path / "seen.json"
    ix.sitemap_delta(state_path=state, _fetch=lambda h: SITEMAP)
    grown = SITEMAP.replace("</urlset>", "<url><loc>https://upe.co.il/c/</loc></url></urlset>")
    assert ix.sitemap_delta(state_path=state, _fetch=lambda h: grown) == ["https://upe.co.il/c/"]
    # and it is not re-reported on the next check
    assert ix.sitemap_delta(state_path=state, _fetch=lambda h: grown) == []


def test_cli_dry_run_never_posts(capsys):
    rc = ix.main(["--urls", "https://upe.co.il/a/", "--dry-run"])
    assert rc == 0 and "dry-run" in capsys.readouterr().out
