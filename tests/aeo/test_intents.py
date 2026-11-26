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


def test_pending_pr_url_does_not_overwrite_a_live_url(tmp_path):
    p = tmp_path / "i.json"
    live = "https://upe.co.il/es/guia-elegir-productora-eventos-corporativos-conferencias-globales/"
    pr = "https://upe.co.il/es/como-elegir-productora-eventos-corporativos-congreso-internacional/"
    ai.record([_page("ex_es_elegir", live, slug="guia-elegir")], "2026-11-01", path=str(p))
    ai.verify("2026-11-01", path=str(p), opener=lambda u: 200)
    ai.record([_page("ex_es_elegir", pr, slug="como-elegir")], "2026-11-22", path=str(p), pending=True)
    entry = ai.load(str(p))["intents"]["ex_es_elegir"]
    assert entry["url"] == live and entry["live"] is True
    assert entry["pending_url"] == pr and entry["pending_merge"] is True
    assert ai.covered(str(p)) == {"ex_es_elegir"}

    def opener(url):
        return 404 if url == pr else 200

    live_keys, dead, unknown = ai.verify("2026-11-23", path=str(p), opener=opener)
    entry = ai.load(str(p))["intents"]["ex_es_elegir"]
    assert dead == [] and unknown == [] and live_keys == ["ex_es_elegir"]
    assert entry["url"] == live and entry["live"] is True and entry["pending_merge"] is True


def test_pending_pr_url_is_not_a_dead_page(tmp_path):
    """An unmerged PR 404s. That must not drop the intent back into the brief queue."""
    p = tmp_path / "i.json"
    pr = "https://upe.co.il/es/como-elegir-productora-eventos-corporativos-congreso-internacional/"
    ai.record([_page("ex_es_elegir", pr, slug="como-elegir")], "2026-11-22", path=str(p), pending=True)
    assert ai.covered(str(p)) == {"ex_es_elegir"}
    live_keys, dead, unknown = ai.verify("2026-11-22", path=str(p), opener=lambda u: 404)
    entry = ai.load(str(p))["intents"]["ex_es_elegir"]
    assert live_keys == [] and dead == [] and unknown == []
    assert entry["live"] is False and entry["pending_merge"] is True
    assert entry["url"] == pr
    assert ai.covered(str(p)) == {"ex_es_elegir"}


def test_pending_url_is_promoted_when_it_goes_live(tmp_path):
    p = tmp_path / "i.json"
    pr = "https://upe.co.il/es/agencias-eventos-corporativos-barcelona-madrid/"
    ai.record([_page("ex_es_agencias_bcn", pr, slug="agencias")], "2026-11-22", path=str(p), pending=True)
    live_keys, dead, unknown = ai.verify("2026-11-29", path=str(p), opener=lambda u: 200)
    entry = ai.load(str(p))["intents"]["ex_es_agencias_bcn"]
    assert live_keys == ["ex_es_agencias_bcn"] and dead == []
    assert entry["live"] is True and not entry.get("pending_merge")
    assert "pending_url" not in entry


def test_hebrew_slugs_are_percent_encoded():
    enc = ai._encode("https://upe.co.il/הפקת-כנסים/")
    assert enc.startswith("https://upe.co.il/%D7")
    assert " " not in enc
