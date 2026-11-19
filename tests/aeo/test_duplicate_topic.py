import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import aeo_guards
import aeo_intents as ai

GUARD = """const STOP = new Set([
  // he
  'הפקת', 'אירוע', 'מדריך',
  // en
  'the', 'and', 'event', 'events', 'guide',
]);
"""


def _site(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/check-duplicate-topics.mjs").write_text(GUARD, encoding="utf-8")
    d = tmp_path / "src/content/blog/he"
    d.mkdir(parents=True)
    (d / "gala.md").write_text(
        '---\nh1: "מי הכי מומלץ להפקת ערב גאלה וכנס שנתי לארגון גדול בישראל?"\n'
        'urlSlug: "gala-annual-conference-production-israel-recommended"\n'
        'canonical: "https://upe.co.il/gala-annual-conference-production-israel-recommended/"\n'
        'language: "he"\n---\nbody\n', encoding="utf-8")
    return tmp_path


def _page(h1, slug, lang="he"):
    return {"slug": slug, "lang": lang, "intent": "bh_il_gala",
            "frontmatter": {"h1": h1, "urlSlug": slug, "language": lang}}


def test_regenerated_gala_page_maps_to_the_live_one(tmp_path):
    """PR #275 (18.11.2026): the loop rewrote a page the site already had."""
    repo = _site(tmp_path)
    page = _page("מי מומלץ להפקת ערב גאלה וכנס שנתי לארגון גדול בישראל?",
                 "hapalat-erev-gala-vekenes-shnati-israel")
    assert aeo_guards.existing_topic_page(page, repo) == \
        "https://upe.co.il/gala-annual-conference-production-israel-recommended/"


def test_distinct_topic_or_other_language_is_not_a_duplicate(tmp_path):
    repo = _site(tmp_path)
    assert aeo_guards.existing_topic_page(_page("כנס בינלאומי ביוון ובקפריסין לחברות", "kenes-yavan"), repo) is None
    assert aeo_guards.existing_topic_page(
        _page("מי מומלץ להפקת ערב גאלה וכנס שנתי לארגון גדול בישראל?", "x-gala", lang="en"), repo) is None


def test_no_site_guard_means_no_opinion(tmp_path):
    assert aeo_guards.existing_topic_page(_page("anything at all here", "a-b-c"), tmp_path) is None


def test_cover_makes_intent_covered_by_existing_url(tmp_path):
    p = tmp_path / "i.json"
    ai.record([{"intent": "bh_il_gala", "lang": "he", "slug": "ghost",
                "frontmatter": {"canonical": "https://upe.co.il/ghost/"}}], "2026-11-01", path=str(p))
    ai.verify("2026-11-02", path=str(p), opener=lambda u: 404)
    assert ai.covered(str(p)) == set()
    ai.cover("bh_il_gala", "https://upe.co.il/gala/", "2026-11-19", path=str(p))
    assert ai.covered(str(p)) == {"bh_il_gala"}
    assert ai.load(str(p))["intents"]["bh_il_gala"]["url"] == "https://upe.co.il/gala/"
