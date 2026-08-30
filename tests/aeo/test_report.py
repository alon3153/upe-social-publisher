import scripts.aeo_report as rep


def sc(ps, cmp_, rep_):
    return {"date": "2026-06-28",
            "models": {"claude": {"product_search": ps, "comparison": cmp_, "reputation": rep_,
                                  "aeo": round((ps + cmp_ + rep_) / 3)}}}


def test_build_email_rtl_and_delta():
    subject, html = rep.build_email(sc(50, 45, 100), sc(40, 45, 100),
                                    shipped=[{"title": "Guide", "url": "https://upe.co.il/x/"}],
                                    queued=1, failures=[], pr_url="https://github.com/x/y/pull/3")
    assert 'dir="rtl"' in html and 'lang="he"' in html
    assert "▲" in html            # product_search rose 40->50
    assert '<span dir="ltr">https://upe.co.il/x/</span>' in html
    assert "1" in subject or "1" in html   # queued count visible
    assert "github.com/x/y/pull/3" in html


def test_build_email_notes_failures():
    _, html = rep.build_email(sc(50, 45, 100), None, shipped=[], queued=0,
                              failures=["chatgpt: no key", "build failed"], pr_url=None)
    assert "chatgpt: no key" in html
    assert "build failed" in html


def test_build_daily_email_rtl_status_and_keywords():
    kw = {"he": ["הפקת כנסים בינלאומיים"], "en": ["international conference production"],
          "competitors": ["BCD", "Maritz"], "priority_actions": ["publish HE category guide"]}
    subject, html = rep.build_daily_email(sc(60, 55, 100), sc(50, 55, 100), kw, failures=[], target=90)
    assert 'dir="rtl"' in html and 'lang="he"' in html
    assert "▲" in html                       # product_search 50->60
    assert "international conference production" in html
    assert "הפקת כנסים בינלאומיים" in html
    assert "BCD" in html
    assert "מעקב" in subject or "AEO" in subject


def test_build_daily_email_says_number_one_when_at_target():
    subject, html = rep.build_daily_email(sc(95, 92, 100), None, {"he": [], "en": [], "competitors": [], "priority_actions": []}, failures=[], target=90)
    assert "#1" in html or "מוביל" in html or "ראשון" in html


def test_send_uses_injected_fn():
    seen = {}

    def fake_send(subject, html):
        seen["s"] = subject
        return True, "ok"

    ok, info = rep.send("S", "<html></html>", send_fn=fake_send)
    assert ok and seen["s"] == "S"


# --- honest reporting ---------------------------------------------------------

def _block(**kw):
    b = {"mention_rate": 31, "citation_rate": 44, "product_search": 12, "comparison": 23,
         "reputation": 76, "aeo": 37, "mention_rate_nonbranded": 8, "citation_rate_nonbranded": 8,
         "brand_recall": 100, "n_nonbranded": 32, "mentioned_nonbranded": 3, "n_branded": 4,
         "grounded_rate": 100, "degraded": False, "answers": []}
    b.update(kw)
    return b


def _sc(models, date="2026-09-06", bv="2026-08-30.1"):
    return {"date": date, "battery_version": bv, "models": models, "errors": []}


def test_headline_is_the_non_branded_rate_with_its_fraction():
    import aeo_report as r
    _, html = r.build_email(_sc({"claude": _block()}), None, [], 0, [], None)
    assert "אזכור לא-ממותג (KPI ראשי)" in html
    assert "(3/32)" in html                      # the reader can see what one question is worth
    assert "זיהוי מותג (ממותג — לא KPI)" in html


def test_single_question_movement_is_shown_as_noise():
    import aeo_report as r
    cur = _sc({"claude": _block(mention_rate_nonbranded=9)})
    prev = _sc({"claude": _block(mention_rate_nonbranded=6)}, date="2026-08-30")
    _, html = r.build_email(cur, prev, [], 0, [], None)
    assert "רעש" in html                          # 3 points < 2 questions (7)
    assert "▲ +3" not in html


def test_real_movement_still_gets_an_arrow():
    import aeo_report as r
    cur = _sc({"claude": _block(mention_rate_nonbranded=25)})
    prev = _sc({"claude": _block(mention_rate_nonbranded=6)}, date="2026-08-30")
    _, html = r.build_email(cur, prev, [], 0, [], None)
    assert "▲ +19" in html


def test_degraded_engine_is_flagged_as_a_broken_instrument():
    import aeo_report as r
    sc = _sc({"chatgpt": _block(degraded=True, grounded_rate=0,
                                degraded_reason="RuntimeError: HTTP 404 model retired",
                                mention_rate_nonbranded=0, citation_rate_nonbranded=0)})
    _, html = r.build_email(sc, None, [], 0, [], None)
    assert "מכשיר תקול" in html
    assert "אל תסיק מכאן ירידה בנראות" in html
    assert "model retired" in html


def test_pages_that_are_not_live_are_not_reported_as_published():
    import aeo_report as r
    subject, html = r.build_email(
        _sc({"claude": _block()}), None,
        shipped=[{"title": "Live one", "url": "https://upe.co.il/live/"}], queued=4, failures=[],
        pr_url=None, not_live=[{"title": "Ghost", "url": "https://upe.co.il/ghost/"}])
    assert "אינם חיים" in html and "ghost" in html.lower()
    assert "1 עמודים חיים" in subject


def test_baseline_note_is_actually_rendered_on_a_battery_change():
    """It was computed and then dropped on the floor — the reader never saw it."""
    import aeo_report as r
    cur = _sc({"claude": _block()}, bv="2026-08-30.1")
    prev = _sc({"claude": _block()}, date="2026-08-23", bv="2026-07-05.1")
    _, html = r.build_email(cur, prev, [], 0, [], None)
    assert "baseline חדש" in html


def test_comparative_pages_are_disclosed():
    import aeo_report as r
    _, html = r.build_email(_sc({"claude": _block()}), None, [], 0, [], None,
                            comparative=[{"slug": "top-event-companies", "competitors": ["Freeman"]}])
    assert "עמודי השוואה שפורסמו" in html and "Freeman" in html
