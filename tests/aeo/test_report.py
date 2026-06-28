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
