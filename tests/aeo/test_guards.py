import scripts.aeo_guards as gd


def test_clean_text_passes():
    assert gd.check_content("Uproduction Events: 16 years, 1,500+ events across 130+ destinations.") == []


def test_forbidden_stat_flagged():
    v = gd.check_content("With 200+ events and over 2000 participants since 2010.")
    assert any("200+" in x for x in v)
    assert any("2000" in x for x in v)


def test_event_year_flagged_en():
    v = gd.check_content("We produced this flagship conference in 2019 for the client.")
    assert any("event year" in x.lower() for x in v)


def test_event_year_flagged_he():
    v = gd.check_content("הפקנו את הכנס הזה ב-2018 עבור הלקוח.")
    assert any("event year" in x.lower() for x in v)


def test_founding_year_2010_allowed():
    assert gd.check_content("Founded in 2010, Uproduction Events has 16 years of experience.") == []
