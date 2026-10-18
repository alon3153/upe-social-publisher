"""UPE iron rules for generated pages (AEO review of PR #203, 18.10.2026).

Every violation here is prefixed "policy:" or "structure:" and BLOCKS the run
(aeo_guards.is_blocking). A generated page that breaks one is regenerated with
the violation fed back; if it still breaks it after MAX_GEN_ATTEMPTS, no PR opens.

Sources:
- client / hotel / promise list: uproduction-astro tests/aeo-b3-faq-text-match.test.mjs
  (P4_SCHEMA_BANNED, master b779c37) + eBay/Orgon (LEGAL, #188).
- C3e cost disclaimer: the approved Hebrew wording from P70-C3e (#214).
- intent -> URL owners: AEO plan-to-70 (09.10.2026) section 4, state/intent_owners.json.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OWNERS_PATH = ROOT.parent / "state" / "intent_owners.json"

# «אפרודקשיין» is the Hebrew spelling used on 9 live pages (also «א. אפרודקשיין»)
BRAND_RE = re.compile(r"Uproduction(?:\s+Events)?|\bUPE\b|יופרודקשן|אפרודקשיין")

# Hebrew attaches ו/ב/ל/מ/ה/כ/ש (up to three, optional maqaf/hyphen) to names and numbers:
# «לתנובה», «בשופרסל», «ל6 חודשים», «ל-300 עובדים», «בתשעה חודשים». _LB is a left
# boundary that tolerates those prefixes; _HE_END stops a Hebrew word from matching
# inside a longer one («אירו» inside «אירועים», «עשר» inside «עשרות»).
_HEB = "\u0590-\u05FF"
_LB = rf"(?<![\w{_HEB}])(?:[ובלמהכש]{{1,3}}[-\u05BE]?)?"
_HE_END = rf"(?![{_HEB}])"

# --- superlatives describing UPE ---------------------------------------------------
# Sentence level (AEO rev-3 recheck): a sentence that refers to UPE/us AND contains a
# superlative blocks: «אנחנו חברת ההפקה המובילה», «UPE היא מהמובילות», "We are the
# leading ...", "The leading producer in Israel, Uproduction Events", "Somos la
# productora líder". Before the check, a short allowlist of generic phrases where the
# superlative describes something else is blanked («ארגונים מובילים», "top chefs",
# "the best time to"). Production companies / producers / agencies / productoras are
# never allowlisted.
_POSS_HE = r"(?:צוותנו|חברתנו|שירותנו|שירותינו|מעמדנו|הפקותינו|מומחינו|אנשינו|מפיקינו|משרדנו|פתרונותינו|מומחיותנו|רמתנו)"
_SELF_REF_RE = re.compile(
    rf"(?:Uproduction|(?<![A-Za-z])UPE(?![A-Za-z])|יופרודקשן|אפרודקשיין"
    rf"|(?<![{_HEB}])(?:[ובלמהכ]{{1,2}}[-\u05BE]?)?(?:אנחנו|אנו|שלנו|אצלנו|אותנו|לנו|כמונו|כמותנו)(?![{_HEB}])"
    # possessive-suffix nouns, CLOSED list (AEO rev-5.3): not ניסיוננו (a source citation, «מניסיוננו
    # ב-1,500+…», dozens live) and not לקוחותינו (a third party); not every -נו word (אינו, בנו, קנו)
    rf"|(?<![{_HEB}])[ובלמשכה]{{0,2}}{_POSS_HE}(?![{_HEB}])"
    # first-person verbs with no pronoun
    rf"|(?<![{_HEB}])(?:הפקנו|עבדנו|ניהלנו|ארגנו|נמנים\s+עם|אנו\s+גאים|גאים\s+להיות)(?![{_HEB}])"
    # «נסיוננו» only as the subject of הוא/היא («נסיוננו הוא הרב ביותר»)
    rf"|(?<![{_HEB}])נ(?:י)?סיוננו\s+(?:הוא|היא)(?![{_HEB}])"
    r"|\b(?:[Ww]e|[Ww]e['’]re|[Ww]e['’]ve|[Oo]urs?|us)\b|\b(?:[Ss]omos|[Nn]osotros|[Nn]uestr[oa]s?)\b)")
# "No competition / without equal" family (AEO rev-5.2 recheck + sweep): a claim about whoever
# the sentence refers to, so with any self-reference (incl. a canonical fact) it always blocks.
_PEERLESS_RE = (
    rf"ללא\s+(?:כל\s+)?(?:תחרות|מתחרים|מתחרה|מתחר)(?![{_HEB}])|אין\s+(?:לנו\s+|לה\s+|לו\s+|להם\s+)?(?:מתחרים|מתחרה|תחרות)(?![{_HEB}])"
    rf"|(?<![{_HEB}])ש?אין\s+(?:כמוה|כמוהו|כמונו|כמותה|כמותנו|כמותם)(?![{_HEB}])|אין\s+שני\s+ל|אין\s+מי\s+שמשתווה"
    rf"|בלתי\s+מעורער(?:ת|ים|ות)?|ללא\s+(?:אח\s+ורע|מתחרים\s+של\s+ממש|השוואה)|אין\s+(?:דומה|השוואה)\s+ל|בליגה\s+(?:משלה|משלנו|אחרת)"
    rf"|מ?ה(?:טובים|טובות)\s+ב(?:עולם|ארץ|ישראל|תחום|אירופה)(?![{_HEB}])"
    r"|\bwithout\s+(?:an?\s+)?(?:equal|peer|rival|competition|competitors)\b|\b(?:has|have)\s+no\s+(?:equal|peers?|rivals?|competition|competitors)\b"
    r"|\bbeyond\s+compare\b|\bin\s+a\s+(?:league|class)\s+of\s+(?:its|their|our|his|her)\s+own\b|\bpeerless\b|\bunequall?ed\b"
    r"|\bno\s+one\s+(?:does\s+it\s+better|comes\s+close)\b|\bnobody\s+does\s+it\s+better\b|\bunchallenged\b|\bundisputed\b"
    r"|\bsecond\s+to\s+none\b|\bun(?:matched|rivall?ed|paralleled|surpassed|beatable)\b|\bincomparable\b"
    r"|\bsin\s+(?:competencia|igual|rival|parang[oó]n|comparaci[oó]n|competidores)\b|\binigualable(?:s)?\b|\binsuperable(?:s)?\b"
    r"|\bbest[\s-]in[\s-]class\b|\buna?\s+de\s+l[ao]s\s+principales\b"
    r"|\binmejorable(?:s)?\b|\bincomparables?\b|\bno\s+tiene(?:n)?\s+(?:rival|competencia|igual)\b|\bindiscutibles?\b"
)
_PEERLESS_ONLY_RE = re.compile(_PEERLESS_RE, re.I)
_SUP_RE = re.compile(
    _PEERLESS_RE + "|"
    rf"ברמה\s+אחרת|ה?ראשונים\s+בתחום|(?<![{_HEB}])חלוצ(?:ה|ים|ות|י)?(?![{_HEB}])|(?<![{_HEB}])פורצ(?:ת|י|ות)?\s+דרך"
    r"|\bpioneers?\b|\bpioner[oa]s?\b|\bgalardonad[oa]s?\b|\baward[\s-]winning\b|(?<![\u0590-\u05FF])יוצא(?:ת|ים|ות)?\s+דופן|"
    # Hebrew: מוביל/ה/ים/ות with ה-/מה-/למ-/כ-, but not the verb sense «מובילה את הקבוצה»
    rf"(?<![{_HEB}])(?:[ובלמהכש]{{1,3}}[-\u05BE]?)?מוביל(?:ה|ים|ות)?(?![{_HEB}])"
    r"(?!\s+את\s+(?!(?:ה?שוק|התחום|הענף)))"
    r"|ה?טוב(?:ה|ים|ות)?\s+ביותר"
    r"|ה(?:רב|מנוס|מקצועי|אמינ|גדול|מומלצ|איכותי|מוערכ|חזק|בכיר|מצליח|ותיק|יוקרתי|מוכר|בולט|חדשני)\S*\s+ביותר(?!\s*מ(?:[-\u05BE]|\s|\d))"
    r"|הכי\s+(?:טוב|מנוס|מקצועי|גדול|מוביל|אמינ|מומלצ|איכותי|מוערכ|חזק|מצליח|ותיק|מוכר)\S*"
    r"|מספר\s+1|מס['׳]\s*1|(?<!\w)#\s?1\b"
    r"|ה(?:גדול|ותיק|טוב|חזק|מנוס|מוכר|בכיר|מוביל)(?:ה|ים|ות)?\s+(?:ב(?:ישראל|ארץ|עולם|תחום|ענף|אירופה|שוק|מזרח\s+התיכון))(?![\u0590-\u05FF])"
    # English
    r"|\b(?:leading|leader|premier|foremost|best(?:-in-class)?|top|world[\s-]class|unmatched|unrivall?ed"
    r"|number[\s-]one|go-to|second\s+to\s+none|unparalleled|unsurpassed|unbeatable|incomparable|industry[\s-]leading|market[\s-]leading)\b"
    r"|\bleads\s+the\s+(?:market|industry|field|sector|way)\b"
    r"|\bmost\s+(?:trusted|experienced|reliable|respected|recommended|reputable|innovative|creative|professional"
    r"|successful|established|renowned|sought[\s-]after|prestigious)\b"
    # Spanish
    r"|\bl[ií]der(?:es)?\b|\bmejor(?:es)?\b|\bn[uú]mero\s+uno\b"
    r"|\b(?:el|la)\s+m[aá]s\s+(?:experimentad|confiable|reconocid|prestigios|fiable)\w*", re.I)
_GENERIC_NOUNS_EN = (r"chefs|venues|hotels|resorts|brands|restaurants|suppliers|vendors|destinations|speakers|artists"
                     r"|DJs|wineries|universities|clients|customers|organi[sz]ations|employers|hospitals|banks"
                     r"|tech\s+companies|companies(?!\s+(?:in|for)\s+event)")
_SUP_ALLOW_RE = re.compile(
    rf"\b(?:top|leading|best|world[\s-]class)\s+(?:{_GENERIC_NOUNS_EN})\b"
    r"|\b(?:the\s+)?best\s+(?:time|times|season|month|months|way|ways|practices?|option\s+for\s+you|fit\s+for\s+you)\b"
    r"|\bbest\s+(?:to|if|when)\b|\bat\s+(?:the\s+)?best\b|\bat\s+the\s+top\b|\bon\s+top\b|\btop\s+(?:of|priority|priorities|floor|tips?)\b"
    r"|\btop[\s-](?:performers?|performing|down|level|line|floor)\b|\b(?:works?|do|does)\s+best\b|עושים\s+הכי\s+טוב|הצד\s+הטוב\s+ביותר|(?:que|lo|a[uú]n|m[aá]s)\s+mejor(?:es)?\b"
    r"|\bleading\s+(?:up\s+)?to\b|\bmejor\s+(?:época|momento|forma|manera|opción\s+para\s+(?:ti|usted|vosotros))\b"
    rf"|{_LB}(?:ארגונים|ארגוני|מותגים|מלונות|בתי\s+מלון|שפים|מסעדות|ספקים|יעדים|אמנים|לקוחות|מעסיקים|בנקים"
    rf"|בתי\s+חולים|אוניברסיטאות|יקבים|נבחרות)\s+(?:\S+\s+)?ה?מוביל(?:ים|ות)(?![{_HEB}])"
    rf"|(?<![{_HEB}])חברות\s+(?:הייטק|טכנולוגיה|ענק|בינלאומיות\s+)?\s*ה?מובילות(?![{_HEB}])"
    r"|ה(?:זמן|מועד|עונה|דרך|יעד|פתרון)\s+ה?\S+\s+ביותר", re.I)
# word list kept for prompt/tests: what counts as a superlative at all
_SUPERLATIVE_RE = _SUP_RE


_TOK = re.compile(rf"[\w{_HEB}'’#]+(?:-[\w{_HEB}'’#]+)*|[^\w\s{_HEB}]")
# nouns that make the superlative a claim about the producer itself
_SELF_NOUN_EN = re.compile(r"^(?:producers?|productions?|company|companies|agency|agencies|firms?|partners?|choice|providers?"
                           r"|DMCs?|organi[sz]ers?|planners?|house|specialists?|experts?|name|brand|team)$", re.I)
_SELF_NOUN_ES = re.compile(r"^(?:productoras?|empresas?|agencias?|compañ[ií]as?|socios?|opci[oó]n|equipo|organizadoras?|proveedor(?:es)?)$", re.I)
_SELF_NOUN_HE = re.compile(r"^(?:[ובלמה]{0,2})(?:חברת|חברה|הפקה|הפקות|מפיקה|מפיק|מפיקים|סוכנות|צוות|שותף|מומחים|מומחה|חברות\s*הפקה|ספק)$")
# construct-state heads: «מפיקי האירועים המובילים», «חברת ההפקות הגדולה», «צוות ההפקה הטוב ביותר»
_CONSTRUCT_HE = re.compile(r"^(?:[ובלמה]{0,2})(?:מפיקי|מפיקת|מפיק|חברת|סוכנות|צוות|צוותי|חברות|ספק|ספקי)$")
# our field after «חברת/חברות»; ה / ה- / ה־ in front, also before a Latin word («חברת ה-MICE»)
_PROD_DOMAIN_HE = re.compile(r"^(?:ה[-\u05BE]?)?(?:הפקה|הפקות|אירועים|האירועים|אירוע|תיירות|נסיעות|כנסים|תמריץ|מיתוג|נופשים|נופש"
                             r"|גיבוש|טיולים|טיולי|לוגיסטיקה|ימי\s+(?:ה)?כיף|MICE|DMC|incentive|events?)$", re.I)
_PRED_HE = re.compile(r"^(?:היא|הוא|הינה|הינו|הם|הן|אנו|אנחנו|שלנו|נחשבת|נחשב|נחשבים|נחשבות|נמנית|נמנים|Events|Uproduction|UPE|יופרודקשן|אפרודקשיין|ואפרודקשיין|באפרודקשיין|ביופרודקשן"
                      r"|צוותנו|חברתנו|שירותנו|שירותינו|מעמדנו|הפקותינו|מומחינו|אנשינו|מפיקינו|משרדנו|פתרונותינו|מומחיותנו|רמתנו"
                      r"|הפקנו|עבדנו|נמנים)$")
_FUNC_EN = re.compile(r"^(?:in|of|at|for|among|across|on|around|within|worldwide|globally|anywhere|and|when|by|today|in-house)$", re.I)
_FUNC_ES = re.compile(r"^(?:en|de|del|para|entre|y|a|por)$", re.I)


def _is_self_claim(sent, m, noun_only=False):
    """Does this superlative describe the producer (us/UPE), not a venue, chef or client?
    noun_only: the sentence refers to us only through a canonical fact, so a pronoun/predicate
    («הם המשווקים הכי אמינים», «הן הסיכון #1») is not enough; the superlative must sit on a
    producer noun («חברת הפקה מובילה», "a leading production company", «productora líder»)."""
    wide = [w for w in _TOK.findall(sent[:m.start()]) if w.strip()][-5:]
    before = wide[-3:]
    after = _TOK.findall(sent[m.end():])[:3]
    word = m.group(0)
    if re.match(r"^יוצא(?:ת|ים|ות)?\s+דופן$", word):
        # soft marketing wording: only when it describes our own service/team/company («UPE מציעה שירות
        # יוצא דופן», «UPE היא חברה יוצאת דופן»), not experiences/results («חוויה יוצאת דופן», live x70)
        if noun_only:
            return False
        b1 = [w for w in _TOK.findall(sent[:m.start()]) if w.strip()][-3:]
        return bool(b1 and re.match(r"^(?:[ובלמה]{0,2})(?:שירות|צוות|חברה|חברת|מקצועיות|מקצוענות|רמת|רמה|מפיק|מפיקה|סוכנות|ספק)$", b1[-1])
                    or any(_PRED_HE.match(x) for x in b1[-2:]))
    if _PEERLESS_ONLY_RE.fullmatch(word.strip()):
        return True                                         # «ללא תחרות», "in a league of its own", «sin igual»
    if re.search(f"[{_HEB}]", word):                       # Hebrew: adjective follows its noun
        if re.match(r"^מוביל(?:ה|ים|ות)?$", word) and after and re.match(r"^ל[\u05D0-\u05EA]", after[0]):
            return False                                    # verb "leads to": «תכנון חכם מוביל לחיסכון»
        if word.startswith("כ"):
            return any(_PRED_HE.match(b) for b in before[-2:])   # «למתג את החברה כמובילה» (as leading) unless «היא כ...»
        if before and _SELF_NOUN_HE.match(before[-1]):
            return True                                     # «חברת ההפקה המובילה», «חברה מובילה»
        for k in (2, 3):                                    # «חברת X ה...» / «חברת ימי הכיף ה...»
            if len(before) < k or not _CONSTRUCT_HE.match(before[-k]):
                continue
            head = re.sub(r"^[ובלמה]{0,2}", "", before[-k])
            chain = " ".join(before[-k + 1:])
            if head not in ("חברת", "חברות", "ספק", "ספקי"):
                # «מפיקי/סוכנות/צוות X»: any definite X
                if k == 2 and chain.startswith("ה"):
                    return True
                continue
            # «חברת/חברות X» in our field («חברת ה-MICE המובילה», «חברת DMC מובילה»), not «חברות הביטוח המובילות»
            if _PROD_DOMAIN_HE.match(chain):
                return True
            # explicit self-reference right before: «UPE היא חברת המיתוג המובילה», any X
            lead = wide[-k - 1] if len(wide) > k else ""
            if _PRED_HE.match(lead) or lead == "אחת":
                return True
        if noun_only:
            return False
        if word.startswith("הכי") or "ביותר" in word or "מספר" in word or "מס" in word[:2]:
            return any(_PRED_HE.match(b) for b in before[-2:])   # «הצוות שלנו הוא הטוב ביותר», «אנחנו הכי טובים»
        return any(_PRED_HE.match(b) for b in before[-2:])       # «UPE היא מהמובילות», «נחשבת למובילה», «אנו המובילים»
    if re.match(r"(?i)l[ií]der|mejor|n[uú]mero|pioner|galardonad", word):     # Spanish: adjective follows or precedes its noun
        if before and _SELF_NOUN_ES.match(before[-1]):
            return True                                     # «productora líder», «empresa líder»
        nxt = [a for a in after if re.match(r"\w", a)]
        if nxt and _SELF_NOUN_ES.match(nxt[0]):
            return True                                     # «la mejor opción», «la mejor productora»
        if noun_only:
            return False
        return not after or not re.match(r"\w", after[0]) or bool(_FUNC_ES.match(after[0]))
    # English: the superlative precedes its noun
    words = []
    for a in after:
        if not re.match(r"[\w#]", a):
            break
        words.append(a)
    if "team" in [w.lower() for w in words[:3]] and re.search(r"(?i)team[\s-]+building", " ".join(words)):
        words = words[:[w.lower() for w in words].index("team")]
    if any(_SELF_NOUN_EN.match(w) for w in words[:3]):
        return True                                         # "the leading event producer", "#1 incentive producer"
    if noun_only:
        return False
    if re.match(r"(?i)un(?:matched|rivall?ed|paralleled|surpassed|beatable)|incomparable|second\s+to\s+none", word):
        return True                                         # "offers unmatched service", "is second to none"
    if word.lower().startswith("leads"):
        return True
    return not words or bool(_FUNC_EN.match(words[0]))     # "is the best in Europe", "is unmatched.", "the go-to,"


# A ranking claim about a company in our own field blocks even with no self-reference:
# on a generated UPE page «חברת ה-MICE המובילה בישראל» reads as us (AEO rev-5 recheck).
_DOMAIN_RANKING_HE = re.compile(
    rf"(?<![{_HEB}])(?:[ובלמה]{{0,2}})(?:חברת|חברות|מפיקי|סוכנות)\s+(?:"
    # definite on both sides ("THE leading X company"); indefinite «סוכנות אירועים גדולה» / «חברת הפקה
    # מובילה חייבת...» is a generic description and passes
    r"(?:ה[-\u05BE]?)(?:הפקה|הפקות|אירועים|תיירות|נסיעות|כנסים|תמריץ|מיתוג|נופשים|נופש|גיבוש|טיולים|טיולי|לוגיסטיקה"
    r"|MICE|DMC)\s+|ימי\s+הכיף\s+)"
    rf"(?:ה|מה)(?:מוביל(?:ה|ים|ות)?|גדול(?:ה|ות)?|טוב(?:ה|ות)?\s+ביותר|ותיק(?:ה|ות)?)(?![{_HEB}])", re.I)


# A UPE canonical fact in the sentence is an implicit self-reference (AEO rev-5.1 recheck):
# «חברת הפקה מובילה עם 1,500+ אירועים ו-130+ יעדים». A canon fact alone never blocks;
# only canon fact + a superlative describing the producer does.
_CANON_SELF_RE = re.compile(
    r"1[,.]?500\s*\+|\+\s*1[,.]?500|(?<![\d,.])130\s*\+|\+\s*130(?![\d,.])|25[,.]?000\s*\+|25K\+|\+\s*25[,.]?000"
    r"|(?:מעל|יותר\s+מ[-\u05BE]?|למעלה\s+מ[-\u05BE]?|over|more\s+than|m[aá]s\s+de)\s*(?:1[,.]?500|130|25[,.]?000)(?![\d])"
    r"|מאז\s+(?:שנת\s+)?2010|\bsince\s+2010\b|\bdesde\s+(?:el\s+año\s+)?2010\b"
    r"|אלון\s+וקנין|\bAlon\s+Ou?aknine\b", re.I)


def _self_ref(s):
    return _SELF_REF_RE.search(s) or _CANON_SELF_RE.search(s)


# «נמנים עם החברות המובילות» with no subject is always first person; with a subject it blocks
# only when the sentence refers to us («UPE נמנית עם…», not «תנובה נמנית עם…»).
_NIMNIM_RE = re.compile(
    rf"(?<![{_HEB}])נמנ(?:ים|ית|ה|ות)\s+עם\s+(?:ה)?(?:חברות|מפיקי|מפיקות|סוכנויות|ספקי)(?:\s+\S+)?\s+ה?מוביל(?:ים|ות)(?![{_HEB}])")
# «הפקנו… כחברה המובילה», «עבדנו כחברת ההפקה המובילה»: "as THE leading company" with an explicit self-reference
_AS_LEADING_RE = re.compile(
    rf"(?<![{_HEB}])כ(?:חברה|חברת\s+\S+|מפיקה|מפיק|סוכנות|ספק)\s+ה(?:מוביל(?:ה)?|גדול(?:ה)?|טוב(?:ה)?\s+ביותר)(?![{_HEB}])")
_SECOND_PERSON_RE = re.compile(r"שלכם|לכם|אתכם|שלך|\byour\b|\bvuestr|\btu\s|\bsu\s+empresa", re.I)


def self_superlatives(text):
    hits = []
    for s in _sentences(text):
        nm = _NIMNIM_RE.search(s)
        if nm and (not re.search(rf"[\w{_HEB}]", s[:nm.start()]) or _SELF_REF_RE.search(s[:nm.start()])):
            hits.append(s.strip())
            continue
        if _AS_LEADING_RE.search(s) and _SELF_REF_RE.search(s) and not _SECOND_PERSON_RE.search(s):
            hits.append(s.strip())
            continue
        if _DOMAIN_RANKING_HE.search(s):
            hits.append(s.strip())
            continue
        if not _self_ref(s):
            continue
        scrub = _SUP_ALLOW_RE.sub(lambda m: " " * len(m.group(0)), s)
        if not _self_ref(scrub):
            continue
        implicit = not _SELF_REF_RE.search(scrub)
        if any(_is_self_claim(scrub, m, noun_only=implicit) for m in _SUP_RE.finditer(scrub)):
            hits.append(s.strip())
    return hits


# --- prices --------------------------------------------------------------------------
_CUR = (rf"(?:₪|\$|€|ש\"ח|ש״ח|שקל(?:ים)?{_HE_END}|אירו{_HE_END}|דולר(?:ים)?{_HE_END}"
        r"|\bUSD\b|\bEUR\b|\bNIS\b|\bILS\b|\beuros?\b|\bdollars?\b|\bd[oó]lares\b)")
_PRICE_RE = re.compile(
    rf"(?:{_CUR}\s?\d[\d,.]*\s?[Kk]?|\d[\d,.]*\s?(?:K|k|אלף|מיליון)?\s?{_CUR}"
    rf"|(?:עשרות|מאות)\s+אלפי\s+(?:דולרים|שקלים|אירו|ש\"ח|ש״ח)"
    rf"|(?:tens|hundreds)\s+of\s+thousands\s+of\s+(?:dollars|euros|shekels)"
    # "budgets from 50K" — an amount with no currency next to budget/cost wording
    rf"|(?:budgets?|costs?|price[sd]?|presupuestos?|תקציב(?:ים)?|עלות)\D{{0,20}}\d[\d,.]*\s?[Kk]\b)", re.I)

# The approved cost disclaimers, verbatim, both sentences (HE: P70-C3e; EN/ES: P70-C3d,
# live in uproduction-astro since 2167e13, 11.10.2026).
C3E_DISCLAIMERS = {
    "he": "הטווחים הם אינדיקטיביים בלבד ואינם הצעת מחיר. המחיר בפועל תלוי ביעד, בעונה, בגודל הקבוצה וברמת השירות.",
    "en": "These ranges are indicative only and are not a quote. The actual price depends on the destination, "
          "season, group size and level of service.",
    "es": "Estos rangos son solo orientativos y no constituyen un presupuesto. El precio final depende del destino, "
          "la temporada, el tamaño del grupo y el nivel de servicio.",
}
C3E_DISCLAIMER_HE = C3E_DISCLAIMERS["he"]
_C3E_MARKERS = tuple(C3E_DISCLAIMERS.values())
# AEO 18.10: prices enter the site only by hand (AEO/CONTENT). A generated page with a
# price is blocked even when it carries the full disclaimer. Flip only with AEO.
ALLOW_PRICE_WITH_DISCLAIMER = False


def has_c3e_disclaimer(text):
    return any(m in (text or "") for m in _C3E_MARKERS)


# --- operational numbers -------------------------------------------------------------
_EN_NUMWORD = (r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen"
               r"|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)")
# "twenty-five", "twenty-five-thousand": a specific number, unlike "multi-thousand"
_HYPH_NUM = rf"\b{_EN_NUMWORD}(?:-{_EN_NUMWORD})+"
_NUMW = (r"(?:(?:" + _HYPH_NUM + r"|\d[\d,.]*\s?[Kk](?![A-Za-z])\+?|\d[\d,.]*\+?"
         r"|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen"
         r"|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|hundred|thousand|dozen"
         r"|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|quince|veinte|treinta|cien|doscientas?|doscientos|mil"
         r"|שתים\s+עשרה|שנים\s+עשר|חמישה\s+עשר|אחד|אחת|שניים|שתיים|שני|שתי|שלושה|שלוש|ארבעה|ארבע|חמישה|חמש"
         r"|שישה|שש|שבעה|שבע|שמונה|תשעה|תשע|עשרה|עשר|עשרים|שלושים|ארבעים|חמישים|מאה|מאתיים|אלף|אלפיים|תריסר)"
         + _HE_END + ")")
_RANGE = r"(?:\s*(?:[-–—]|to|עד|a|or|או|y)\s*" + _NUMW + ")?"
_DUR = (r"(?:months?|weeks?|days?|years?|חודשים|חודש|שבועות|שבוע|ימים|יום|שנים|שנה|שנות"
        r"|meses|mes|semanas|d[ií]as|años|año)" + _HE_END)
_HEADS = (r"(?:participants|attendees|guests|people|person|employees|pax|delegates"
          r"|משתתפים|אורחים|עובדים|איש|אנשים|מוזמנים|participantes|asistentes|empleados|personas|invitados)" + _HE_END)
# singular heads only after a numeral ("a 25K-attendee event", "300-participant kick-off", "200 invitado"):
# after a word they are ordinary nouns ("one participant database", "multi-thousand-participant")
_SING_HEADS = r"(?:participant|attendee|guest|delegate|employee|participante|asistente|invitado|persona|empleado)\b"
_NUMERAL = rf"(?:(?<![\w.,])\d[\d,.]*(?:\s?[Kk](?![A-Za-z]))?\+?|{_HYPH_NUM})"
_OPERATIONAL = [
    (re.compile(rf"{_LB}{_NUMW}{_RANGE}\s*[-–]?\s*{_DUR}", re.I), "planning/lead-time duration"),
    # durations with no numeral: dual forms, half a year, "a year ahead", "un año de antelación"
    (re.compile(rf"{_LB}(?:חודשיים|שבועיים|יומיים|שנתיים|חצי\s+שנה|שנה\s+(?:מראש|לפני|קודם)){_HE_END}"
                r"|\b(?:a|one|half\s+a)\s+year\s+(?:ahead|in\s+advance|before|prior|out)\b"
                r"|\b(?:un|medio)\s+año\s+(?:de\s+antelaci[oó]n|antes)\b", re.I), "planning/lead-time duration"),
    (re.compile(rf"{_LB}{_NUMW}{_RANGE}[\s-]*{_HEADS}", re.I), "group size / headcount"),
    (re.compile(rf"{_NUMERAL}(?:\s*(?:[-–—]|to|a)\s*{_NUMERAL})?[\s-]*{_SING_HEADS}", re.I), "group size / headcount"),
    # final account / settlement timing, with or without a number («כמה שבועות אחרי»)
    (re.compile(r"(?:חשבון\s+(?:ה)?סופי|גמר\s+חשבון|התחשבנות\s+סופית|\bfinal\s+(?:account|invoice|settlement|reconciliation)\b"
                r"|\bsettlement\b|\bliquidaci[oó]n\s+final\b|\bfactura\s+final\b)[^.\n]{0,60}?"
                r"(?:תוך|אחרי|לאחר|עד|בתוך|\bwithin\b|\bafter\b|\bby\b|\bdentro\s+de\b|\bdespu[eé]s\b|\ben\s+un\s+plazo\b)", re.I),
     "settlement timing"),
    (re.compile(rf"{_LB}{_NUMW}\s*(?:events?|אירועים|eventos)\s*(?:per|a|each|in\s+a|ב|por)\s*(?:year|שנה|año)", re.I),
     "event frequency"),
]
# Canonical aggregates (1,500+ events, 130+ destinations, 25,000+ participants) in
# HE/EN/ES, with or without "+", "more than / over / más de / מעל / יותר מ- / למעלה מ-",
# "1.500" / "25.000" / "25K". Scrubbed before the operational checks.
_CANON_NOUN = rf"(?:\s*(?:[\w{_HEB}]+\s+)?)"
_CANON_NUMBERS = re.compile(
    rf"{_LB}(?:(?:more\s+than|over|m[aá]s\s+de|מעל|יותר\s+מ[-\u05BE]?|למעלה\s+מ[-\u05BE]?)\s*)?(?:\+\s*)?"
    rf"(?:1[,.]?500\+?{_CANON_NOUN}(?:events|אירועים|eventos)"
    rf"|130\+?{_CANON_NOUN}(?:destinations|יעדים|destinos)"
    rf"|25(?:[,.]?000|K)\+?{_CANON_NOUN}(?:participants|attendees|משתתפים|participantes|asistentes))", re.I)

# 25,000+ is cumulative only. Next to a single event («אירוע של 25,000 משתתפים», "an event
# for 25,000 attendees", "single event of 25,000", "a 25,000-person event") it is not
# scrubbed, so the headcount check sees it.
_SINGLE_EVENT_BEFORE = re.compile(
    r"(?:\b(?:event|conference|gala|summit|congress|convention|evento|congreso|conferencia)s?\s+(?:of|for|with|de|con|para)"
    r"|\b(?:single|one|a\s+single)\s+(?:event|conference)\s+(?:of|for|with)?"
    rf"|(?:אירוע|כנס|גאלה|כינוס)(?:\s+(?:אחד|יחיד))?\s+(?:של|עם|ל|עבור)[-\u05BE]?)\s*$", re.I)
_SINGLE_EVENT_AFTER = re.compile(
    r"^\s*(?:at|in|for)\s+(?:a|one)\s+(?:single\s+)?(?:event|conference)\b"
    rf"|^\s*(?:ב|ל)?(?:אירוע|כנס)\s+(?:אחד|יחיד)|^\s*(?:en|para)\s+un\s+(?:solo\s+)?evento", re.I)


# Vague plurals are a general description, not an operational number (AEO 18.10, rev 4.1):
# «כנסים של מאות משתתפים», «כמה מאות», "hundreds/thousands of", "several hundred",
# "a few thousand", "cientos/miles de". Blanked before the operational checks. Specific
# number words still block: «אלף/אלפיים/תריסר משתתפים», "a thousand", "a dozen", "mil personas".
_VAGUE_QTY = re.compile(
    r"\b(?:several|a\s+few|few|many|some)\s+(?:hundred|thousand|dozen)\b"
    r"|\b(?:hundreds|thousands|dozens)\s+of\b|\b(?:varios|varias|unos|unas)\s+(?:cientos|miles)\b"
    r"|\b(?:cientos|miles|centenares|decenas)\s+de\b"
    rf"|(?<![{_HEB}])(?:[ובלמ]{{1,2}}[-\u05BE]?)?(?:כמה\s+)?(?:מאות|אלפי|עשרות)(?![{_HEB}])", re.I)
# ...except when we claim one event of that size: «הפקנו אירוע של אלפי משתתפים",
# "we produced an event for thousands of attendees".
_VAGUE_SINGLE_EVENT = re.compile(
    rf"(?<![{_HEB}])(?:[ובלמה]{{0,2}})(?:אירוע|כנס|גאלה|כינוס)(?:\s+(?:אחד|יחיד))?\s+(?:של|עם|עבור|ל[-\u05BE]?)\s*(?:כמה\s+)?(?:מאות|אלפי)\s+{_HEADS}"
    rf"|\b(?:an?|one|single|a\s+single)\s+(?:event|conference|gala|congress)\s+(?:of|for|with)\s+"
    rf"(?:several\s+|a\s+few\s+)?(?:hundreds|thousands|hundred|thousand)\s+(?:of\s+)?{_HEADS}"
    rf"|\b(?:un|una)\s+(?:evento|congreso|conferencia|gala)\s+(?:de|para|con)\s+(?:varios\s+)?(?:cientos|miles)\s+de\s+{_HEADS}", re.I)
_UPE_CLAIM = re.compile(r"Uproduction|(?<![A-Za-z])UPE(?![A-Za-z])|יופרודקשן|אפרודקשיין|הפקנו|ניהלנו|ארגנו|\b[Ww]e(?:['’]ve)?\s+(?:produced|ran|managed|organi[sz]ed|delivered)\b"
                        r"|\b(?:[Pp]rodujimos|[Oo]rganizamos|[Gg]estionamos)\b|\b(?:[Hh]emos|[Hh]e)\s+(?:producido|organizado|gestionado|realizado)\b")


def _scrub_vague(line):
    return _VAGUE_QTY.sub(lambda m: " " * len(m.group(0)), line)


def _scrub_canon(line):
    def repl(m):
        if (_SINGLE_EVENT_BEFORE.search(line[max(0, m.start() - 40):m.start()])
                or _SINGLE_EVENT_AFTER.search(line[m.end():m.end() + 30])):
            return m.group(0)
        return ""
    return _CANON_NUMBERS.sub(repl, line)


# --- unsourced percentages / multipliers ----------------------------------------------
_PCT_RE = re.compile(r"\d{1,3}(?:[.,]\d+)?\s?%|עשרות\s+אחוזים|אחוזים\s+רבים|\b\d+(?:\.\d+)?\s?x\b|פי\s+\d+|\b\d+\s+times\s+(?:more|less|higher|lower)", re.I)
_LINK_RE = re.compile(r"\[[^\]]+\]\(https?://[^)]+\)")

# --- client / hotel names (never on a generated page) ---------------------------------
CLIENT_NAMES = [
    "Alpha Bio", "אלפא ביו", "Duda", "דודה", "AllCloud", "Allcloud", "SysAid", "Sysaid",
    "Tnuva", "תנובה", "Unilever", "יוניליוור", "Shufersal", "שופרסל", "eBay", "איביי",
    "Orgon", "אורגון", "Isrotel", "ישרוטל", "Herods", "Herod's", "הרודס",
    # AEO rev-3 recheck: names on /עלינו/ without written approval; Tambour is do-not-contact
    "Tambour", "טמבור", "Sheba", "שיבא", "Alpha-Bio", "AlphaBio", "אלפא-ביו", "אלפאביו", "דודא",
]


def _name_re(name):
    # Hebrew prefixes allowed in front; possessive 's / plural endings after Latin names allowed
    return re.compile(rf"{_LB}{re.escape(name)}(?![\w{_HEB}])", re.I if name.isascii() else 0)


_CLIENT_RES = [(n, _name_re(n)) for n in CLIENT_NAMES]

_BARCELONA_RE = re.compile(
    r"(?:office|oficina|offices|oficinas|headquarters|sede|משרד(?:נו|ינו|ים)?|סניף|מטה)\s+(?:in\s+|en\s+|ב-?|בעיר\s+)?(?:Barcelona|ברצלונה)"
    r"|Barcelona(?:-based)?\s+office|בברצלונה\s+(?:יש\s+)?(?:לנו\s+)?משרד", re.I)

_PROMISE_RE = re.compile(
    r"\bguarantee(?:d|s)?\b|\bwe\s+promise\b|\bfully\s+insured\b|\bincludes?\s+(?:full\s+)?insurance\b|\bproven\b"
    r"|\binsurance\s+(?:is\s+)?included\b|\b(?:fully\s+)?covered\s+by\s+(?:our\s+)?insurance\b"
    r"|\bgarantiza(?:do|mos)?\b|\bseguro\s+incluido\b"
    r"|מבטיח(?:ים|ה)?|מובטח(?:ת|ים)?|אפס\s+הפתעות|מוכח(?:ת)?|ביטוח\s+(?:מלא|נוסעים\s+מלא|משתתפים)"
    r"|כולל(?:ת|ים)?\s+ביטוח", re.I)
_FAQ_ONLY_PROMISE = re.compile(r"וביטוח")   # P4 schema list; generic buyer advice in the body is fine


def _sentences(text):
    return [s for s in re.split(r"(?<=[.!?…])\s+|\n+", text or "") if s.strip()]


def _prose(text):
    """Blank link targets and bare URLs (as uproduction-astro's prose() does) so a
    slug such as /...-10-to-25000-attendees/ is not read as a headcount claim."""
    text = re.sub(r"\]\([^)]*\)", "]()", text or "")
    return re.sub(r"https?://\S+", "", text)


def _visible_text(frontmatter, body, raw=False):
    faqs = frontmatter.get("faqs") or []
    parts = [str(frontmatter.get(k) or "") for k in ("title", "description", "h1", "llmsDescription")]
    parts += [f"{f.get('question', '')} {f.get('answer', '')}" for f in faqs]
    joined = "\n".join(parts + [body or ""])
    return joined if raw else _prose(joined)


def iron_rule_violations(frontmatter, body):
    out = []
    text = _visible_text(frontmatter, body)
    faqs = frontmatter.get("faqs") or []

    for hit in self_superlatives(text):
        out.append(f"policy: superlative describing UPE: {hit[:90]!r}")

    blocks = [_prose(f.get("answer", "")) for f in faqs] + re.split(r"\n\s*\n", _prose(body))
    for blk in blocks:
        m = _PRICE_RE.search(blk)
        if not m:
            continue
        if not has_c3e_disclaimer(blk):
            out.append(f"policy: price without the C3e disclaimer: {m.group(0)!r}")
        elif not ALLOW_PRICE_WITH_DISCLAIMER:
            out.append(f"policy: price on a generated page (prices are added by AEO/CONTENT only): {m.group(0)!r}")

    for line in text.splitlines():
        for s in _sentences(line):
            m = _VAGUE_SINGLE_EVENT.search(s)
            if m and _UPE_CLAIM.search(s):
                out.append(f"policy: unapproved operational number (single-event size claim): {m.group(0).strip()!r}")
        scrub = _scrub_vague(_scrub_canon(line))
        for rx, label in _OPERATIONAL:
            m = rx.search(scrub)
            if m:
                out.append(f"policy: unapproved operational number ({label}): {m.group(0).strip()!r}")

    for line in _visible_text(frontmatter, body, raw=True).splitlines():
        # raw text: the inline source link is what makes a percentage acceptable
        if _PCT_RE.search(_prose(line)) and not _LINK_RE.search(line):
            out.append(f"policy: unsourced percentage/multiplier: {_PCT_RE.search(_prose(line)).group(0)!r}")

    for name, rx in _CLIENT_RES:
        if rx.search(text):
            out.append(f"policy: client/hotel name: {name!r}")
    if _BARCELONA_RE.search(text):
        out.append(f"policy: Barcelona office claim: {_BARCELONA_RE.search(text).group(0)!r}")
    m = _PROMISE_RE.search(text)
    if m:
        out.append(f"policy: promise/insurance claim: {m.group(0)!r}")
    for f in faqs:
        if _FAQ_ONLY_PROMISE.search(f.get("answer", "")):
            out.append("policy: insurance wording in a FAQ answer ('וביטוח')")
            break
    return _dedup(out)


# --- structure: UPE mention + internal links ------------------------------------------
_MD_LINK = re.compile(r"\]\((https?://(?:www\.)?upe\.co\.il)?(/[^)\s]*)\)")


def _first_paragraph(body):
    for para in re.split(r"\n\s*\n", body or ""):
        p = para.strip()
        if p and not p.startswith(("#", "|", "---", "![", "<")):
            return p
    return ""


def internal_links(body, own_url=""):
    own = re.sub(r"^https?://(?:www\.)?upe\.co\.il", "", own_url or "").rstrip("/") + "/"
    links = {m.group(2).split("#")[0] for m in _MD_LINK.finditer(body or "")}
    return sorted(u for u in links if u and u.rstrip("/") + "/" != own)


def structure_violations(frontmatter, body, min_links=2):
    out = []
    if not BRAND_RE.search(_first_paragraph(body)):
        out.append("structure: 'Uproduction Events' is not mentioned in the first paragraph")
    faqs = frontmatter.get("faqs") or []
    if faqs and not any(BRAND_RE.search(f.get("answer", "")) for f in faqs):
        out.append("structure: no FAQ answer mentions Uproduction Events")
    links = internal_links(body, frontmatter.get("canonical", ""))
    if len(links) < min_links:
        out.append(f"structure: {len(links)} internal link(s) to upe.co.il pages; at least {min_links} required")
    return out


def page_violations(frontmatter, body):
    return iron_rule_violations(frontmatter, body) + structure_violations(frontmatter, body)


# --- cannibalization: intent -> owner URL ---------------------------------------------
def load_owners(path=None):
    p = Path(path or OWNERS_PATH)
    if not p.exists():
        return {"owners": {}, "service_pages": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def split_owned(briefs, owners=None):
    """(new_page_briefs, strengthen_briefs). An intent that already has an owner URL
    gets a strengthen-existing brief instead of a new competing page."""
    owned = (owners or load_owners()).get("owners", {})
    new, strengthen = [], []
    for b in briefs:
        urls = owned.get(b.get("intent") or "")
        if urls:
            strengthen.append({"intent": b.get("intent"), "topic": b.get("topic") or b.get("question"),
                               "lang": b.get("lang"), "lost_on": b.get("lost_on") or [],
                               "strengthen": urls})
        else:
            new.append(b)
    return new, strengthen


def strengthen_html(strengthen):
    if not strengthen:
        return ""
    rows = "".join(
        f'<li dir="rtl" style="text-align:right;"><b>{s["intent"]}</b>: {s["topic"]} → לחזק את '
        + ", ".join(f'<a href="https://upe.co.il{u}">{u}</a>' for u in s["strengthen"]) + "</li>"
        for s in strengthen)
    return ('<h3 dir="rtl">בריפים לחיזוק דף קיים (לא נפתח דף חדש — יש כבר URL ל-intent)</h3>'
            f"<ul>{rows}</ul>")


def content_task(brief, reasons, owners=None):
    """A brief whose generated page was blocked becomes a manual strengthening task."""
    owned = (owners or load_owners()).get("owners", {}).get(brief.get("intent") or "", [])
    return {"intent": brief.get("intent"), "topic": brief.get("topic") or brief.get("question"),
            "lang": brief.get("lang"), "strengthen": owned, "reasons": list(reasons)}


def content_tasks_html(tasks):
    if not tasks:
        return ""
    rows = []
    for s in tasks:
        target = (", ".join(f'<a href="https://upe.co.il{u}">{u}</a>' for u in s["strengthen"])
                  if s["strengthen"] else "אין דף בעלים: CONTENT מחליט אם לכתוב ידנית")
        why = "; ".join(s["reasons"][:6])
        rows.append(f'<li dir="rtl" style="text-align:right;"><b>{s["intent"]}</b>: {s["topic"]} → '
                    f'{target}<br><small>נחסם: {why}</small></li>')
    return ('<h3 dir="rtl">משימות חיזוק ל-CONTENT (בריפים שהדף שנוצר להם נחסם)</h3>'
            f"<ul>{''.join(rows)}</ul>")


def service_pages(lang, owners=None):
    return (owners or load_owners()).get("service_pages", {}).get(lang, [])


def _dedup(items):
    seen, out = set(), []
    for v in items:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out
