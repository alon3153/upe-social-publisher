"""AEO final adversarial cases for rev 5.3 (/workspace/aeo/rev53-probe/adv8.py, 18.10.2026), copied verbatim,
plus rev-5.4 regression cases (closed possessive list, first-person verbs, nimnim/as-leading rules,
new phrases, «יוצא דופן» only on our own service/team/company)."""
import pytest

import scripts.aeo_guards as gd
import scripts.aeo_policy as pol

ADV8_MUST_BLOCK = {'family': ['אין כמונו בתחום ההפקות.', 'UPE היא חברה בלתי מעורערת בתחום.', 'UPE מציעה שירות יוצא דופן.', 'אנחנו ברמה אחרת.', 'UPE בליגה משלה.', 'אנחנו הראשונים בתחום התמריץ.', 'UPE היא חלוצה בתחום.', 'אנו המומחים מספר 1 לכנסים.', 'UPE פורצת דרך בהפקות.', 'UPE היא מהמובילות בתחום.', 'UPE היא אחת המובילות בישראל.', 'UPE is in a league of its own.', 'Uproduction is second to none.', 'UPE is an industry-leading producer.', 'We are a world-class DMC.', 'UPE offers best-in-class service.', 'UPE is an award-winning agency.', 'UPE is one of the leading producers.', 'We are pioneers in incentive travel.', 'UPE ofrece un servicio sin igual.', 'Somos una agencia inigualable.', 'Somos líderes del sector.', 'UPE es una de las principales agencias.'], 'possessive': ['מעמדנו כמובילים בתחום ידוע.', 'נסיוננו הוא הרב ביותר בישראל.', 'צוותנו הוא הטוב ביותר.', 'חברתנו מובילה בתחום.', 'שירותנו ללא תחרות.', 'הפקותינו הן הטובות ביותר.', 'מומחינו המובילים בתחום.', 'לקוחותינו בוחרים בנו כי אנחנו המובילים.'], 'verbs': ['הפקנו את האירועים הגדולים ביותר בישראל כחברה המובילה.', 'נמנים עם החברות המובילות בתחום.', 'עבדנו כחברת ההפקה המובילה.', "We're proud to be the leading DMC in Israel."], 'rules': ['העלות 500 ₪ לאדם. הטווחים הם אינדיקטיביים בלבד ואינם הצעת מחיר. המחיר בפועל תלוי ביעד, בעונה, בגודל הקבוצה וברמת השירות.', 'הפקנו לטמבור כנס.', 'עבור שיבא', 'Alpha-Bio', 'ודודא', 'Duda', 'הפקנו אירוע של 25,000 משתתפים.', 'גמר חשבון תוך 45 יום.', 'מומלץ לתכנן 4-6 חודשים מראש.', '16 שנות ניסיון.', 'Founded in 2010.', 'יש לנו משרד בברצלונה.', 'Our Barcelona office handles Spain.', 'Tenemos oficina en Barcelona.', 'UPE has an office in Barcelona.']}

ADV8_MUST_PASS = ['מעל 1,500 אירועים ביותר מ-130 יעדים.', '1,500+ אירועים, 130+ יעדים, 25,000+ משתתפים.', 'Uproduction Events operates since 2010 and was incorporated in 2012.', 'info@upe.co.il', 'המשרד הראשי ברחובות.', 'כנסים בברצלונה', 'Corporate events in Barcelona.', 'Congresos en Barcelona.', 'שפים מובילים', 'מלונות מובילים בברצלונה.', 'The venue is world-class.', "Lisbon's award-winning restaurants.", 'המקום אינו מתאים לקבוצות.', 'האתר הינו מדריך.', 'בחרו בנו לפי הצורך.', 'המשתתפים קנו מזכרות.', 'הספקים ענו מהר.', 'חברות הביטוח המובילות.', 'פורצי דרך בטכנולוגיה מציגים בכנס.']

REV54_MUST_BLOCK = [
    "ספק DMC מוביל ב-130+ יעדים.", "UPE נמנית עם החברות המובילות בתחום.", "נמנים עם מפיקי האירועים המובילים בישראל.",
    "ארגנו את הכנס כחברת ההפקה המובילה בתחום.", "אנשינו הם הטובים ביותר.", "פתרונותינו ללא תחרות.", "UPE היא חברה יוצאת דופן.",
    "Somos pioneros en viajes de incentivo.",
]
REV54_MUST_PASS = [
    # live-site sentences with the new words that must keep passing
    "מניסיוננו ב-1,500+ אירועים, השקה פנימית מצוינת הופכת עובדים לשגרירי מותג — הם המשווקים הכי אמינים שיש.",
    "לקוחותינו בוחרים יעד לפי עונה.", "האתר אינו מדריך מחירים.", "סלקום נמנית עם החברות המובילות במשק.",
    "אנו מזמינים אתכם להצטרף למעגל הלקוחות שנהנים משקט נפשי ומתוצאות יוצאות דופן.",
    "מאפשר לנו להפוך כל אתגר לוגיסטי להזדמנות ליצירת חוויה ארגונית יוצאת דופן.",
    "אנחנו נסקור כיצד תכנון חכם מחזק את המוניטין העסקי שלכם כחברה המובילה בתחומה.",
    "הפקנו כנס עם דוברים פורצי דרך בטכנולוגיה.", "We hosted award-winning chefs at the gala.",
]


def _blocked(s):
    return pol.iron_rule_violations({}, s) + [x for x in gd.check_content(s) if gd.is_blocking(x)]


@pytest.mark.parametrize("s", [s for v in ADV8_MUST_BLOCK.values() for s in v] + REV54_MUST_BLOCK)
def test_adv8_must_block(s):
    assert _blocked(s), s


@pytest.mark.parametrize("s", ADV8_MUST_PASS + REV54_MUST_PASS)
def test_adv8_must_pass(s):
    assert _blocked(s) == [], s
