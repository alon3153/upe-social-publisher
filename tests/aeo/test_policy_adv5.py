"""AEO adversarial cases for rev 5 (/workspace/aeo/rev4-probe/adv5.py, 18.10.2026), copied verbatim,
plus the decision-(b) cases from AEO's rev-5 recheck. Same check as adv5.py."""
import pytest

import scripts.aeo_guards as gd
import scripts.aeo_policy as pol

ADV5_MUST_BLOCK = ['אנחנו באמת החברה המובילה בישראל.', 'UPE is, without doubt, the leading producer in Israel.', 'We are proud to be the best in Israel.', 'Uproduction Events is, quite simply, the best.', 'UPE היא חברת המיתוג המובילה.', 'UPE היא חברת ה-MICE המובילה בישראל.', 'Uproduction היא חברת DMC מובילה.', 'UPE היא חברת הנופשים המובילה.', 'UPE היא חברת הגיבוש המובילה בארץ.', 'The leading MICE agency, UPE, plans every detail.', 'Uproduction is the leading DMC in Spain.', 'We produced a twenty-five-thousand-attendee event.', 'a 25k participant gala', 'UPE הפיקה אירוע ל-25 אלף איש.', 'Somos, sin duda, la mejor agencia.', 'Our company is unrivalled in Israel.']

ADV5_MUST_PASS = ['חברות הביטוח המובילות דורשות פוליסה.', 'one participant database for all events', 'הספקים המובילים ביעד עובדים איתנו.', 'We work with the leading hotels in Lisbon.', 'מאות משתתפים', 'the best time to visit Lisbon']

RECHECK5_MUST_BLOCK = [
    "UPE היא חברת המיתוג המובילה", "חברת ה-MICE המובילה בישראל", "חברת ה־MICE המובילה בישראל", "חברת הנופשים המובילה",
    "חברת הגיבוש המובילה בארץ", "Uproduction היא חברת DMC מובילה", "חברת ימי הכיף המובילה.", "UPE היא אחת מחברות המיתוג המובילות.",
    "אנחנו חברת הלוגיסטיקה הגדולה בישראל.", "twenty-five attendees", "a two-hundred-person event",
]
RECHECK5_MUST_PASS = [
    "חברות הביטוח המובילות דורשות פוליסה.", "Uproduction Events מלווה את חברת הביטוח המובילה.",
    "בוטיק מול סוכנות אירועים גדולה: מה מתאים לכם?", "חברת הפקה מובילה חייבת להפעיל פלטפורמות רישום מתקדמות.",
    "רשימת חברות הפקה מובילות לגאלות וכנסים ארגוניים בישראל", "a multi-thousand-attendee gala",
]


def _blocked(s):
    return pol.iron_rule_violations({}, s) + [x for x in gd.check_content(s) if gd.is_blocking(x)]


@pytest.mark.parametrize("s", ADV5_MUST_BLOCK + RECHECK5_MUST_BLOCK)
def test_adv5_must_block(s):
    assert _blocked(s), s


@pytest.mark.parametrize("s", ADV5_MUST_PASS + RECHECK5_MUST_PASS)
def test_adv5_must_pass(s):
    assert _blocked(s) == [], s
