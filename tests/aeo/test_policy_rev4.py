"""AEO rev-3 recheck (18.10.2026): the probe sentences from /workspace/aeo/rev3-probe/probe.py,
plus live-site sentences that must keep passing. Same check as the probe: iron rules +
blocking canonical-fact findings."""
import pytest

import scripts.aeo_guards as gd
import scripts.aeo_policy as pol

PROBE_MUST_PASS = ['מעל 1,500 אירועים ביותר מ-130 יעדים.', 'Uproduction Events הפיקה יותר מ-1,500 אירועים במעל 130 יעדים, עם למעלה מ-25,000 משתתפים.', 'ב-1,500+ אירועים וב-130+ יעדים.', '1,500+ אירועים, 130+ יעדים, 25,000+ משתתפים.', 'אלון וקנין מפיק אירועים מאז 2010.', 'Uproduction Events operates since 2010 and was incorporated in 2012.', 'Uproduction Events has operated since 2010.', 'Más de 1.500 eventos y más de 25.000 participantes desde 2010.', 'Over 1,500 corporate events in 130+ destinations.', 'מאז 2010 הפקנו מעל 1,500 אירועים ב-130 יעדים ועבור יותר מ-25,000 משתתפים מצטבר.', 'האירועים באירופה מתקיימים לאורך כל השנה.', 'אירופה היא יעד פופולרי.', 'הבחירה הנכונה ביותר מבחינה תקציבית היא לשאול שאלות.', 'Top chefs and leading venues are part of every program.', 'ארגונים מובילים בוחרים לתכנן מראש.', '1,500 אירועים ב-130 יעדים.', '+1,500 אירועים', '25.000 asistentes']
PROBE_MUST_BLOCK = {'prices': ['העלות היא 500 ₪ לאדם.', 'Budgets from €50,000.', 'Desde 300 euros por persona.', 'עלות של 2,000 דולר למשתתף.', '€200 per person. These ranges are indicative only and are not a quote. The actual price depends on the destination, season, group size and level of service.', 'החבילה עולה 1,200 שקל.', 'מחיר: 800 ש"ח', 'Costs around 150 EUR per guest.', 'budgets from 50K'], 'age': ['Uproduction Events was founded in 2010.', '16 years of experience.', 'Founded: 2010', 'fundada en el año 2010', 'más de 15 años de experiencia', '15+ years', 'ב-16 השנים האחרונות', 'שישה עשר שנים', '16 שנות ניסיון', 'נוסדה ב-2010', 'מאז הקמתה ב-2010', 'with 16 years in the industry', 'for over a decade and a half', 'פועלת כבר 16 שנה', 'over sixteen years', 'established 2010', 'since 2010 — 16 years', 'בעלת ניסיון של 16 שנה', 'UPE, founded 2010,', 'Founded in 2010, UPE', 'הוקמה בשנת 2010'], 'duration': ['Final account within 45 days.', 'החשבון הסופי תוך 45 יום.', '45 ימים לאחר האירוע', 'Plan 6-9 months ahead.', 'seis a nueve meses de antelación', 'doce meses antes', 'חודשיים מראש', 'שבועיים לפני', 'שנה מראש', 'חצי שנה מראש', 'Plan at least a year ahead.', 'בתשעה חודשים', 'ל6 חודשים', 'ל-3 חודשים', 'חמישה חודשים', 'fifteen weeks', 'thirty days', '4–6 שבועות', 'de 6 a 9 meses', 'un año de antelación', 'nine to twelve months', 'three months out', 'Book 90 days in advance.', 'שלושה עד שישה חודשים', 'תשעה עד שנים עשר חודשים'], 'heads': ['200 personas', 'מאתיים משתתפים', 'ל300 עובדים', '300 משתתפים', 'groups of 50 to 500 attendees', 'כמאה משתתפים', 'a few thousand attendees', 'several hundred delegates', 'אלף משתתפים', 'mil participantes', 'a dozen guests', 'groups of 1,000 people', 'קבוצות של 20-500 איש', '1500 משתתפים בכנס אחד', 'a 25,000-person event', 'אירוע של 25,000 משתתפים', 'an event for 25,000 attendees', 'single event of 25,000 participants'], 'clients': ['לתנובה', 'בשופרסל', 'ליוניליוור', 'וSysAid', "Tnuva's", 'ו-AllCloud', 'שתנובה', 'מהרודס', 'ובישרוטל', 'worked with eBay', 'Alpha-Bio', 'AlphaBio', 'תנובה,', 'Tambour', 'טמבור', 'Sheba', 'שיבא', 'SHUFERSAL', 'Unilever’s', 'בטמבור'], 'superlative_upe': ['Uproduction Events היא חברת ההפקה המובילה בישראל.', 'Uproduction Events היא אחת מחברות ההפקה המובילות בישראל.', 'Uproduction Events (upe.co.il) היא חברת ההפקה המובילה.', 'אנחנו חברת ההפקה המובילה בישראל.', 'אנו המובילים בתחום.', 'החברה שלנו מובילה בתחום התמריץ.', 'הצוות שלנו הוא הטוב ביותר.', 'Uproduction Events is the leading boutique producer.', 'Uproduction Events, a boutique producer, is the best choice.', 'Uproduction Events ranks among the top producers in Europe.', 'Uproduction Events is one of the most trusted producers.', 'We are the leading event producer in Israel.', "We're Israel's #1 incentive producer.", 'Our team is the best in Europe.', 'The leading producer in Israel, Uproduction Events, ...', "Israel's top event company: Uproduction Events.", 'Uproduction Events es una de las productoras líderes de España.', 'Somos la productora líder en Barcelona.', 'Nuestra agencia es la mejor opción.', 'Uproduction Events es la mejor productora.', 'בUPE אנחנו הכי טובים.', 'ב-UPE אנחנו הכי טובים.', 'יופרודקשן היא המובילה.', 'Uproduction Events היא חברה מובילה בתחום.', 'Uproduction Events מובילה את שוק התמריץ.', 'Uproduction Events היא מספר 1 בישראל.', 'Uproduction Events היא הטובה ביותר.', 'Uproduction Events היא חברת ההפקות הטובה ביותר בישראל.', 'Uproduction Events is a world-class producer.', 'Uproduction Events is the premier choice for incentives.', 'UPE is the go-to, best-in-class producer.', 'Uproduction Events is unmatched in Europe.', 'Uproduction Events leads the market.', 'Uproduction Events היא דוגמה מובילה', 'UPE היא מהמובילות בתחום.', 'UPE נחשבת למובילה בתחום.', 'Uproduction Events is widely considered the leading producer.']}

LIVE_MUST_PASS = [
    # superlatives about venues / chefs / clients / trends, not about us (live site, 18.10)
    "Since 2010, Uproduction Events has produced 1,500+ events, with strong relationships with top chefs, venues and suppliers across 130+ destinations.",
    "Uproduction Events מפיקה ימי גיבוש לארגונים מובילים בישראל מאז 2010.",
    "Uproduction Events פועלת ב-130+ יעדים ויכולה לייעץ על היעד המתאים ביותר למטרות ולתקציב שלכם.",
    "מניסיון של Uproduction Events עם 1,500+ אירועים, חמשת הטיפים המובילים הם אלה.",
    "Uproduction Events מפיקה כנסים ובונה את לוח הזמנים אחורה מרגע ההגעה של המשתתף הרחוק ביותר.",
    "Uproduction מביאה לשולחן ניסיון מאז 2010 בהובלת אירועי יוקרה לחברות המובילות במשק.",
    "ב-Uproduction Events, אנחנו מפיקים ימי גיבוש לחברות מהמובילות בישראל כבר מאז 2010.",
    "Uproduction Events מכירה את מרכזי הספא המובילים בארץ.",
    "Uproduction Events מזהה את הטרנדים המובילים: קיימות וחוויות אינטראקטיביות.",
    "Uproduction Events מתכננת את הזרימה כך שכל מרכיב מוביל לרגע הבא בלי זמן מת.",
    "הניסיון שלנו מוביל לחיסכון משמעותי בעלויות.",
    "כל אירוע שאנחנו מובילים כולל אסטרטגיית תוכנית ב.",
    "אנחנו בונים קונספט מוביל, בוחרים מיקום שמשרת אותו.",
    "המחויבות שלנו לסטנדרטים הגבוהים ביותר של איכות ושירות.",
    "הנוכחות שלנו ביעדים מאפשרת להבטיח את התנאים המסחריים הטובים ביותר עבור לקוחותינו.",
    "אנחנו מחויבים לכך שכל שלב יבוצע על הצד הטוב ביותר.",
    "נראה כיצד תכנון חכם מוביל לחיסכון תוך חיזוק המוניטין העסקי שלכם כחברה מובילה, אחראית וחדשנית.",
    "אנו נציג מודל עבודה שיסייע לכם למתג את החברה כמובילה בתחומה.",
    "Uproduction Events recommends mid-week evenings in early December for the best venue availability.",
    "Uproduction Events programs these challenges with local knowledge, ensuring teams visit the best neighborhoods.",
    "Contact Uproduction Events to plan a summer party that captures the season's best energy.",
    "Some of our most successful events were produced with modest budgets.",
    "From our experience, the most successful creative team building ideas share one trait.",
    "Uproduction Events regularly runs a conference and the top-performer program as one account.",
    "Which destinations work best for a corporate conference outside the US?",
    "We work flexibly with clients and always strive to find the best solution.",
    "Hemos negociado condiciones preferenciales con los mejores venues de cada región.",
    "En nuestra experiencia, la fórmula que mejor funciona es sencilla.",
    "Una empresa especializada como Uproduction Events negocia mejores tarifas con proveedores.",
    "Comparte tu experiencia con nosotros — tus comentarios nos ayudan a crear eventos aún mejores.",
    "Esta guía recoge nuestra experiencia y las mejores prácticas del sector.",
    # vague quantifiers stay out (AEO decision b)
    "Plan several months ahead.", "תכננו כמה חודשים מראש.", "a few weeks before",
    # vague plurals as a general description (AEO rev 4.1): not an operational number
    "כנסים של מאות משתתפים מחייבים רישום מסודר.", "מאות משתתפים", "אלפי משתתפים", "כמה מאות משתתפים",
    "hundreds of attendees", "thousands of participants", "a few thousand participants", "several hundred attendees",
    "cientos de asistentes", "miles de participantes", "varios cientos de personas",
    "Uproduction Events מפיקה כנסים של מאות משתתפים.", "אנו מתמחים בניהול קבוצות של מאות משתתפים.",
    # 25,000 as a cumulative figure
    "Over 25,000 participants since 2010.", "מאז 2010 השתתפו באירועים שלנו יותר מ-25,000 משתתפים.",
]

LIVE_MUST_BLOCK = [
    "Uproduction Events es una empresa líder internacional en eventos.",
    "Uproduction Events היא דוגמה מובילה: מאז 2010 היא הפיקה 1,500+ אירועים.",
    "Uproduction מובילה את התחום באמצעות שילוב ייחודי בין תיירות להפקה.",
    "אנחנו מזמינים אתכם להבטיח את הצלחת האירוע הבא שלכם עם המומחים המובילים בתחום.",
    # extras: decade and a half, settlement timing without a number, more number words
    "Uproduction Events has operated for a decade and a half.", "פועלת כבר עשור וחצי.",
    "Final account a few weeks after the event.", "החשבון הסופי כמה שבועות אחרי האירוע.",
    "גמר חשבון תוך 45 יום.", "liquidación final dentro de 30 días",
    "תריסר משתתפים", "אלפיים משתתפים", "a thousand guests", "mil personas", "doscientos invitados", "a dozen people",
    "הפקנו אירוע של אלפי משתתפים.", "We produced an event for thousands of attendees.", "Uproduction Events ניהלה כנס של מאות משתתפים.",
    "כנס של 25,000 משתתפים", "25,000 participantes en un solo evento", "Una conferencia de 25.000 asistentes.",
    "Alpha Bio", "אלפא ביו", "דודא", "Duda", "בשיבא", "לטמבור",
]


def _blocked(s):
    return pol.iron_rule_violations({}, s) + [x for x in gd.check_content(s) if gd.is_blocking(x)]


@pytest.mark.parametrize("s", PROBE_MUST_PASS + LIVE_MUST_PASS)
def test_must_pass(s):
    assert _blocked(s) == [], s


# AEO rev 4.1 (18.10, 13:30): vague plurals are NOT meant to block. These two probe.py lines (AEO moved them
# to must-pass in probe.py at 13:33 too, backup probe.rev3.bak.py) are must-pass here.
PROBE_FLIPPED_TO_PASS = ["a few thousand attendees", "several hundred delegates"]
PROBE_MUST_BLOCK = {k: [s for s in v if s not in PROBE_FLIPPED_TO_PASS] for k, v in PROBE_MUST_BLOCK.items()}


@pytest.mark.parametrize("s", PROBE_FLIPPED_TO_PASS)
def test_probe_vague_plurals_now_pass(s):
    assert _blocked(s) == [], s


@pytest.mark.parametrize("s", [s for v in PROBE_MUST_BLOCK.values() for s in v] + LIVE_MUST_BLOCK)
def test_must_block(s):
    assert _blocked(s), s


@pytest.mark.parametrize("s", PROBE_MUST_BLOCK["superlative_upe"])
def test_superlatives_report_as_superlative(s):
    assert any("superlative" in x for x in _blocked(s)), s


def test_single_event_25000_blocks_as_headcount_but_cumulative_passes():
    assert any("headcount" in x for x in _blocked("אירוע של 25,000 משתתפים"))
    assert any("headcount" in x for x in _blocked("a 25,000-person event"))
    assert _blocked("Over 25,000 participants since 2010.") == []
    assert _blocked("1,500+ אירועים, 130+ יעדים, 25,000+ משתתפים.") == []


def test_us_country_is_not_self_reference():
    assert not pol._SELF_REF_RE.search("outside the US")
    assert pol._SELF_REF_RE.search("contact us")
    assert pol._SELF_REF_RE.search("בUPE אנחנו")


def test_price_message_shows_whole_amount():
    assert "€50,000" in " ".join(_blocked("Budgets from €50,000."))
