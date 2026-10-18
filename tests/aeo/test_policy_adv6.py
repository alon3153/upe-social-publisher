"""AEO adversarial cases for rev 5.1 (/workspace/aeo/rev51-probe/adv6.py, 18.10.2026), copied verbatim,
plus rev-5.2 regression cases (brand spelling «אפרודקשיין», canonical fact as implicit self-reference)."""
import pytest

import scripts.aeo_guards as gd
import scripts.aeo_policy as pol

ADV6_MUST_BLOCK = ['UPE היא חברת הגיבוש המובילה בארץ.', 'UPE היא חברת המיתוג המובילה.', 'UPE היא חברת ה-MICE המובילה בישראל.', 'Uproduction היא חברת ה־DMC המובילה.', 'UPE היא חברת הנופשים המובילה.', 'אנחנו חברת ימי הכיף המובילה.', 'אנו חברת הטיולים המובילה בישראל.', 'UPE היא חברת הלוגיסטיקה הטובה ביותר.', 'Uproduction היא חברת האירועים הגדולה בישראל.', 'אפרודקשיין היא חברת התיירות מספר 1.', 'UPE היא חברת הכנסים המובילה.', 'החברה שלנו היא חברת ההפקות המובילה.', 'UPE היא חברת גיבוש מובילה.', 'אנחנו חברת MICE מובילה.', 'Uproduction היא חברת DMC מובילה בספרד.', 'אפרודקשיין היא חברת הפקה מובילה.', 'UPE is the leading DMC in Israel.', 'UPE is the leading MICE company.', 'Uproduction is a leading DMC.', 'UPE es la empresa líder en eventos.', 'Somos la empresa DMC líder.', 'We produced a twenty-five-thousand-attendee event.', 'UPE ran a fifteen-hundred-guest gala.', 'חברת הפקה מובילה עם 1,500+ אירועים ו-130+ יעדים.', 'כחברת הפקה מובילה, אנו דואגים לכל פרט.', 'As a leading DMC, we handle everything.']

ADV6_MUST_PASS = ['multi-thousand-attendee congresses need early hotel blocks.', 'מאות משתתפים', 'thousands of delegates', 'miles de personas', 'מעל 1,500 אירועים ביותר מ-130 יעדים.', '1,500+ אירועים, 130+ יעדים, 25,000+ משתתפים.', 'Uproduction Events operates since 2010 and was incorporated in 2012.', 'Más de 1.500 eventos y más de 25.000 participantes desde 2010.', 'info@upe.co.il', 'המשרד הראשי ברחובות.', 'חברות הביטוח המובילות בישראל דורשות פוליסה.', 'בחרו חברת הפקה מובילה עם ניסיון ביעד.']

REV52_MUST_BLOCK = [
    "א. אפרודקשיין היא חברת הפקה מובילה.", "באפרודקשיין אנחנו הכי טובים.", "אפרודקשיין מובילה את שוק התמריץ.",
    "חברת הפקה מובילה מאז 2010.", "A leading production company with 1,500+ events in 130+ destinations.",
    "Una productora líder desde 2010.", "אלון וקנין מוביל את חברת ההפקה המובילה בישראל.",
    "הפקנו אירוע של אלפי משתתפים, אפרודקשיין.",
]
REV52_MUST_PASS = [
    "אפרודקשיין פועלת מאז 2010.", "Since 2010, Uproduction Events has produced 1,500+ events.",
    "מאז 2010 הפקנו מעל 1,500 אירועים ב-130 יעדים ועבור יותר מ-25,000 משתתפים מצטבר.",
    "מאז 2010 אנחנו עובדים עם ארגונים מובילים.", "Since 2010 we have worked with top chefs and leading venues.",
]


def _blocked(s):
    return pol.iron_rule_violations({}, s) + [x for x in gd.check_content(s) if gd.is_blocking(x)]


@pytest.mark.parametrize("s", ADV6_MUST_BLOCK + REV52_MUST_BLOCK)
def test_adv6_must_block(s):
    assert _blocked(s), s


@pytest.mark.parametrize("s", ADV6_MUST_PASS + REV52_MUST_PASS)
def test_adv6_must_pass(s):
    assert _blocked(s) == [], s


def test_brand_spelling_counts_for_structure():
    assert pol.BRAND_RE.search("א. אפרודקשיין מפיקה אירועים")


@pytest.mark.parametrize("s", ["מניסיוננו ב-1,500+ אירועים, השקה פנימית מצוינת הופכת עובדים לשגרירי מותג — הם המשווקים הכי אמינים שיש.",
                               "מתוך 1,500+ אירועים, הפתעות מכס הן הסיכון #1 — תכנון מוקדם קריטי.",
                               "Since 2010, the best time to visit Lisbon has been May."])
def test_canon_fact_alone_needs_a_producer_noun(s):
    assert [x for x in _blocked(s) if "superlative" in x] == [], s
