import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import aeo_intents as ai


def _page(intent, url, slug="s"):
    return {"intent": intent, "lang": "he", "slug": slug, "frontmatter": {"canonical": url}}


def test_record_then_covered(tmp_path):
    p = tmp_path / "i.json"
    ai.record([_page("bh_il_kenes", "https://upe.co.il/a/")], "2026-08-30", path=str(p))
    assert ai.covered(str(p)) == {"bh_il_kenes"}


def test_a_dead_page_stops_covering_its_intent(tmp_path):
    """PRs #99/#108/#112 were closed unmerged; their intents must come back as briefs."""
    p = tmp_path / "i.json"
    ai.record([_page("ghost", "https://upe.co.il/ghost/")], "2026-08-30", path=str(p))
    live, dead, unknown = ai.verify("2026-08-31", path=str(p), opener=lambda u: 404)
    assert dead == ["ghost"] and live == []
    assert ai.covered(str(p)) == set()


def test_a_flaky_fetch_never_demotes_an_intent(tmp_path):
    p = tmp_path / "i.json"
    ai.record([_page("ok", "https://upe.co.il/ok/")], "2026-08-30", path=str(p))

    def boom(url):
        raise TimeoutError("network")

    live, dead, unknown = ai.verify("2026-08-31", path=str(p), opener=boom)
    assert unknown == ["ok"] and dead == []
    assert ai.covered(str(p)) == {"ok"}


def test_filter_live_splits_reported_pages():
    shipped = [{"title": "real", "url": "https://upe.co.il/real/"},
               {"title": "ghost", "url": "https://upe.co.il/ghost/"}]
    ok, bad = ai.filter_live(shipped, opener=lambda u: 200 if "real" in u else 404)
    assert [s["title"] for s in ok] == ["real"]
    assert [s["title"] for s in bad] == ["ghost"]


def test_hebrew_slugs_are_percent_encoded():
    enc = ai._encode("https://upe.co.il/הפקת-כנסים/")
    assert enc.startswith("https://upe.co.il/%D7")
    assert " " not in enc
