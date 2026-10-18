"""AEO adversarial cases for rev 5.2 (/workspace/aeo/rev52-probe/adv7.py, 18.10.2026), copied verbatim,
plus the rev-5.3 sweep of the "no competition / without equal" family (HE/EN/ES) and «ספק»."""
import pytest

import scripts.aeo_guards as gd
import scripts.aeo_policy as pol

ADV7_MUST_BLOCK = ['באפרודקשיין אנחנו הצוות המוביל.', 'ואפרודקשיין היא חברת ההפקה המובילה.', 'שאפרודקשיין היא המובילה בתחום.', 'לאפרודקשיין יש את צוות ההפקה הטוב ביותר.', 'א. אפרודקשיין היא חברת ההפקות הגדולה בישראל.', 'כאפרודקשיין, אנו המובילים.', 'מאפרודקשיין, חברת ההפקה מספר 1.', 'סוכנות מובילה עם 1,500+ אירועים.', 'מפיקה מובילה מאז 2010.', 'מפיק האירועים המנוסה ביותר, עם 130+ יעדים.', 'ספק DMC מוביל ב-130+ יעדים.', 'משרד הפקות מוביל עם 25,000+ משתתפים.', 'צוות הפקה ללא תחרות, 1,500+ אירועים.', 'בית הפקות מוביל מאז 2010.', '1,500+ אירועים: חברת ההפקה הגדולה בישראל.', 'אלון וקנין, המפיק המוביל בישראל.', 'A leading events agency with 1,500+ events.', 'The #1 DMC in 130+ destinations.', 'Since 2010, the premier event producer in Israel.', 'An unmatched event organizer: 1,500+ events.', 'The best production team, with 25,000+ participants.', 'Top event producer since 2010.', 'Agencia líder con más de 1.500 eventos.', 'Desde 2010, la mejor organizadora de eventos.', 'Organizadora líder en 130+ destinos.']

ADV7_MUST_PASS = ['המשווקים הכי אמינים שיש בשוק, עם 130+ יעדים לבחירה.', 'הסיכון #1 באירוע של 1,500+ אירועים הוא מזג האוויר.', '1,500+ אירועים, 130+ יעדים, 25,000+ משתתפים.', 'The best time to book is spring, across 130+ destinations.', 'Since 2010 we have produced 1,500+ events.', 'מאז 2010 הפקנו מעל 1,500 אירועים.', 'שפים מובילים בכל אחד מ-130+ היעדים.']

# adv7 "R" lines are informational in AEO's script (printed, not scored); kept here as must-pass
ADV7_INFO = ['We see weather as the #1 risk.', 'אנחנו רואים במזג האוויר את הסיכון מספר 1.']

SWEEP53_MUST_BLOCK = ['UPE היא ללא תחרות בתחום.', 'השירות שלנו ללא תחרות.', 'אנחנו ללא מתחרים.', 'צוות הפקה ללא תחרות, 1,500+ אירועים.', 'לUPE אין מתחרים בתחום.', 'אין לנו מתחרים בישראל.', 'Uproduction היא חברה שאין כמוה.', 'אין כמונו בהפקת כנסים.', 'אין שני לUPE בהפקת אירועים.', 'UPE היא המובילה הבלתי מעורערת.', 'UPE היא מהטובים בעולם.', 'אנחנו מהטובים בעולם בהפקות.', 'אנחנו הכי טובים.', 'UPE נמצאת בליגה משלה.', 'Uproduction Events has no competition.', 'We are without equal in Israel.', 'UPE is beyond compare.', 'Uproduction Events is in a league of its own.', 'Our service is in a class of its own.', 'No one does it better than Uproduction Events.', 'UPE is the undisputed leader.', 'Our team is peerless.', 'Uproduction Events no tiene competencia.', 'Somos inigualables.', 'Nuestro servicio es sin igual.', 'UPE, sin rival en Israel.', 'Uproduction Events es insuperable.', 'Since 2010, in a league of its own.', 'Desde 2010, sin competencia.', 'ספק DMC מוביל ב-130+ יעדים.', 'אנחנו ספק הקרקע המוביל בספרד.']

SWEEP53_MUST_PASS = ['השוק בברצלונה ללא תחרות אמיתית על מלונות בקיץ.', 'The venue is beyond compare.', 'אנחנו עובדים עם ספקי הקרקע המובילים ביעד.', 'מאז 2010 אנחנו עובדים עם ספקים מקומיים מובילים.', 'אנחנו בוחרים ספק מקומי מוביל בכל יעד?'] + [
    # live-site generic supplier sentences must keep passing
    "אנחנו עובדים עם ספקי הקרקע המובילים ביעד.", "אנו בוחרים ספקים מקומיים מובילים בכל יעד.",
]


def _blocked(s):
    return pol.iron_rule_violations({}, s) + [x for x in gd.check_content(s) if gd.is_blocking(x)]


@pytest.mark.parametrize("s", ADV7_MUST_BLOCK + SWEEP53_MUST_BLOCK)
def test_adv7_must_block(s):
    assert _blocked(s), s


@pytest.mark.parametrize("s", ADV7_MUST_PASS + ADV7_INFO + SWEEP53_MUST_PASS)
def test_adv7_must_pass(s):
    assert _blocked(s) == [], s


@pytest.mark.parametrize("s", ["צוות הפקה ללא תחרות, 1,500+ אירועים.", "Since 2010, in a league of its own.", "Desde 2010, sin competencia."])
def test_peerless_blocks_with_canon_fact_as_self_reference(s):
    assert any("superlative" in x for x in _blocked(s)), s
