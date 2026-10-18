"""AEO adversarial cases for rev 4 (/workspace/aeo/rev4-probe/adv4.py, 67-case version, 18.10.2026),
copied verbatim. Vague plurals are must-pass per AEO's rev-4.1 decision; adv4 already marks them so,
so no case is flipped. Same check as adv4.py: iron rules + blocking canonical-fact findings."""
import pytest

import scripts.aeo_guards as gd
import scripts.aeo_policy as pol

ADV4_MUST_BLOCK = ['אנחנו הכי טובים בתחום ההפקות.', 'אנו מפיקי האירועים המובילים בישראל.', 'We are the leading incentive travel company in Israel.', 'Somos la mejor agencia de eventos de Israel.', 'Somos líderes en viajes de incentivo.', 'ב-UPE אנחנו המובילות בתחום.', 'ובUPE תמצאו את צוות ההפקה הטוב ביותר.', 'ל-Uproduction יש את הצוות המוביל בארץ.', 'The leading producer, Uproduction Events, handles everything.', 'Uproduction Events is second to none.', 'Uproduction Events offers unmatched service.', "Uproduction Events is Israel's premier event company.", 'UPE היא מספר 1 בהפקת אירועים.', 'Uproduction Events היא חברת ההפקות הגדולה בישראל.', 'La mejor productora de eventos es Uproduction Events.', 'Our team is the best in the industry.', 'UPE is the top event producer in Israel.', 'Uproduction Events היא חברה מובילה.', 'וטמבור', 'לשיבא', "AlphaBio's team", 'ואלפא ביו', 'מטמבור', 'שיבא ותנובה', '25 אלף משתתפים באירוע אחד.', 'a 25K-attendee event', 'הפקנו אירוע של אלפי משתתפים.', 'We produced a conference for thousands of delegates.', 'Organizamos un evento para miles de personas.', 'UPE הפיקה כנס של מאות משתתפים.', 'Uproduction ran a gala for hundreds of guests.', 'הפקנו גאלה לאלפי אורחים.', 'Hemos producido un congreso de cientos de asistentes.', 'אירוע עם 25,000 משתתפים', 'הפקנו כנס של 25 אלף איש.', 'an event of 25000 guests', 'אלף משתתפים', 'אלפיים משתתפים', 'תריסר אורחים', 'a thousand attendees', 'a dozen attendees', 'mil personas']

ADV4_MUST_PASS = ['שפים מובילים מבשלים בערב.', 'top chefs cook live.', 'מלונות מובילים באירופה.', 'האטרקציה המובילה בעיר היא המוזיאון.', 'Los mejores restaurantes de la ciudad.', '1,500+ אירועים', '130+ יעדים', '25,000+ משתתפים מצטבר', 'Uproduction Events operates since 2010 and was legally founded in 2012.', 'המותג פעיל מאז 2010 והחברה התאגדה ב-2012.', 'info@upe.co.il', 'המשרד הראשי ברחובות.', 'Headquartered in Rehovot, Israel.', 'מאות משתתפים', 'אלפי משתתפים', 'hundreds of attendees', 'thousands of participants', 'cientos de asistentes', 'miles de participantes', 'כמה מאות משתתפים', 'several hundred attendees', 'a few thousand participants', 'כנסים של מאות משתתפים דורשים תכנון.', 'Conferences with thousands of delegates need early venue booking.', 'Los congresos de miles de personas requieren logística.']


def _blocked(s):
    return pol.iron_rule_violations({}, s) + [x for x in gd.check_content(s) if gd.is_blocking(x)]


@pytest.mark.parametrize("s", ADV4_MUST_BLOCK)
def test_adv4_must_block(s):
    assert _blocked(s), s


@pytest.mark.parametrize("s", ADV4_MUST_PASS)
def test_adv4_must_pass(s):
    assert _blocked(s) == [], s


@pytest.mark.parametrize("s", ["Uproduction Events offers unmatched service.", "Uproduction Events is second to none.",
                               "Uproduction Events delivers unparalleled quality.", "UPE's experience is unrivaled."])
def test_unmatched_family_always_blocks_with_self_reference(s):
    assert any("superlative" in x for x in _blocked(s)), s


@pytest.mark.parametrize("s", ["אנו מפיקי האירועים המובילים בישראל.", "Uproduction Events היא חברת ההפקות הגדולה בישראל.",
                               "UPE היא הותיקה בתחום.", "ובUPE תמצאו את צוות ההפקה הטוב ביותר."])
def test_hebrew_construct_and_largest_forms_block(s):
    assert any("superlative" in x for x in _blocked(s)), s


@pytest.mark.parametrize("s", ["אנחנו מלווים את לקוחותינו מול חברות הביטוח המובילות בישראל.",
                               "השוק הגדול בעולם לטיולי תמריץ הוא אירופה.", "אנחנו בונים קונספט מוביל."])
def test_hebrew_non_self_forms_pass(s):
    assert [x for x in _blocked(s) if "superlative" in x] == [], s


@pytest.mark.parametrize("s", ["a 25K-attendee event", "25k guests", "a 25 K participant gala", "un evento de 200 invitado"])
def test_k_suffix_and_singular_heads(s):
    assert any("headcount" in x for x in _blocked(s)), s


@pytest.mark.parametrize("s", ["all running against one participant database.",
                               "Uproduction Events has produced events from 30 executives to multi-thousand-participant global conferences.",
                               "Over 25,000 participants since 2010.", "25K+ participants."])
def test_singular_heads_need_a_numeral(s):
    assert [x for x in _blocked(s) if "headcount" in x] == [], s


@pytest.mark.parametrize("s", ["a 300-participant sales kick-off in Prague", "On-site staffing for 500+ attendee events.",
                               "a 60–500 participant international conference"])
def test_numeric_singular_heads_block(s):
    assert any("headcount" in x for x in _blocked(s)), s
