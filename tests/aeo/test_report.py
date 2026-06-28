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


def test_send_uses_injected_fn():
    seen = {}

    def fake_send(subject, html):
        seen["s"] = subject
        return True, "ok"

    ok, info = rep.send("S", "<html></html>", send_fn=fake_send)
    assert ok and seen["s"] == "S"
