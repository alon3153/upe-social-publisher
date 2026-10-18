import scripts.aeo_guards as gd


def test_clean_text_passes():
    assert gd.check_content("Uproduction Events: operating since 2010, 1,500+ events across 130+ destinations.") == []


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


def test_operating_since_2010_allowed():
    assert gd.check_content("Operating since 2010, Uproduction Events has produced 1,500+ events.") == []


def test_tenure_since_2010_not_flagged():
    # the real dry-run false-positive: tenure phrasing near "events" must NOT be flagged
    assert gd.check_content("We have produced 1,500+ events since 2010 across 130+ destinations.") == []
    assert gd.check_content("פועלת מאז 2010 עם 1,500+ אירועים.") == []


def test_names_competitor_detects_and_clean_passes():
    import scripts.aeo_guards as g
    assert g.names_competitor("We compared Jack Morton and Freeman.") == ["jack morton", "freeman"]
    assert g.names_competitor("Uproduction produces global events.") == []


def test_destination_policy_preserves_warning_and_ordinary_word_semantics():
    from scripts.aeo_guards import destination_violations
    assert destination_violations("Cvent manages registration; this sparks debate.") == []
    assert destination_violations("A comparative MCI Group entry")
    assert destination_violations("Sparks")


# --- PR #203 regressions (11.10.2026): non-canonical age + truncated Hebrew pages ---

def test_sixteen_years_and_founded_2010_flagged():
    v = gd.check_content("founded in 2010, with over 16 years of operation")
    assert any("16 years" in x for x in v)
    assert any("founded in 2010" in x for x in v)
    assert all(gd.is_blocking(x) for x in v if x.startswith("canonical fact"))
    assert gd.check_content("16 שנות ניסיון בהפקת אירועים.")
    assert gd.check_content("החברה נוסדה ב-2010.")


def test_planning_durations_are_blocked():
    # AEO 18.10 blocker 1: planning lead times are unapproved operational numbers (#203 B3).
    import scripts.aeo_policy as pol
    for text in ["Book venues 9 to 12 months ahead.", "Plan six to nine months ahead.",
                 "לפחות 9-12 חודשים מראש.", "6–12 חודשים מראש.", "45 יום לפני האירוע."]:
        v = pol.iron_rule_violations({"faqs": [{"question": "When?", "answer": text}]}, "Body.")
        assert any("operational number" in x for x in v), text
        assert all(gd.is_blocking(x) for x in v)


def test_truncated_hebrew_body_flagged():
    v = gd.completeness_violations("**Force majeure** – הגדרה ברורה של מה קורה במקרה של מזג אוויר קי")
    assert v and v[0].startswith("incomplete body") and gd.is_blocking(v[0])
    assert gd.completeness_violations("…במקרה של מגפה, או ס")


def test_complete_body_and_faqs_pass():
    assert gd.completeness_violations("## סיכום\nזה הסוף.", [{"question": "q", "answer": "תשובה מלאה."}]) == []
    assert gd.completeness_violations("Read the **contract terms.**") == []
    assert gd.completeness_violations("Done.", [{"question": "q", "answer": "cut off mid"}])


# --- AEO 18.10 blocker 2: every founding/age variant blocks; "since 2010" passes ---
import pytest


@pytest.mark.parametrize("text", [
    "נוסדה בשנת 2010.", "הוקמה ב־2010.", "נוסדה ב–2010.", "מאז הקמתה ב-2010.",
    "since its founding in 2010", "founded back in 2010", "est. 2010", "sixteen years",
    "שש עשרה שנה", "a 16-year track record", "16 years", "founded in 2010", "נוסדה ב-2010",
    "established in 2010", "16 שנות ניסיון", "Fundada en 2010",
])
def test_founding_and_age_variants_block(text):
    v = gd.check_content(text)
    assert any(x.startswith("canonical fact") for x in v), text
    assert all(gd.is_blocking(x) for x in v if x.startswith("canonical fact"))


@pytest.mark.parametrize("text", ["since 2010", "Since 2010, Uproduction Events has produced 1,500+ events.",
                                  "פועלת מאז 2010", "16 שניות", "תוך 16 שניות בלבד"])
def test_canonical_wording_passes(text):
    assert [x for x in gd.check_content(text) if x.startswith("canonical fact")] == []


def test_table_and_list_endings_are_complete():
    assert gd.completeness_violations("Intro.\n\n| a | b |\n|---|---|\n| x | y |") == []
    assert gd.completeness_violations("Checklist:\n- [ ] Confirm the venue contract") == []
    assert gd.completeness_violations("Steps:\n1. Compare the proposals") == []
    # the real #203 Greece ending: a long prose list item cut mid-word still blocks
    cut = "- **Force majeure** – הגדרה ברורה של מה קורה במקרה של אירועי קיצון, שביתות, מזג אוויר קי"
    assert gd.completeness_violations("Intro.\n\n" + cut)


# --- AEO 18.10 blocker 4: iron rules ---
import scripts.aeo_policy as pol


def _iron(body, answer="Uproduction Events answers."):
    return pol.iron_rule_violations({"faqs": [{"question": "q", "answer": answer}]}, body)


@pytest.mark.parametrize("body,label", [
    ("Uproduction Events is the leading producer in Israel.", "superlative"),
    ("Uproduction Events היא חברת ההפקה המובילה.", "superlative"),
    ("Uproduction Events is a premier agency.", "superlative"),
    ("A conference costs $40,000 to $90,000.", "price"),
    ("טווח רחב של עשרות אלפי עד מאות אלפי דולרים.", "price"),
    ("התקציב מתחיל ב-150 ש\"ח למשתתף.", "price"),
    ("Groups of 200-1,000 attendees work well.", "operational"),
    ("כנסים של 50 משתתפים ומעלה.", "operational"),
    ("We run 40 events per year.", "operational"),
    ("Cancellation saves עשרות אחוזים.", "percentage"),
    ("Engagement rises 30% after incentives.", "percentage"),
    ("ROI improves 3x.", "percentage"),
    ("We worked with Alpha Bio and SysAid.", "client"),
    ("לקוחות כמו תנובה ושופרסל.", "client"),
    ("Clients include eBay.", "client"),
    ("Orgon chose us.", "client"),
    ("Uproduction Events has an office in Barcelona.", "Barcelona"),
    ("Contamos con oficina en Barcelona.", "Barcelona"),
    ("Success is guaranteed.", "promise"),
    ("אנחנו מבטיחים אפס הפתעות.", "promise"),
    ("החבילה כוללת ביטוח מלא.", "promise"),
])
def test_iron_rules_block(body, label):
    v = _iron(body)
    assert v and all(gd.is_blocking(x) for x in v), body


def test_price_blocks_even_with_full_disclaimer_but_message_differs():
    # AEO 18.10 recheck: prices on generated pages stay blocked; the disclaimer only changes the reason
    he = pol.C3E_DISCLAIMERS["he"]
    v = _iron("Body.", f"עלות יום כיף נעה בין 150 ל-400 ש\"ח למשתתף. {he}")
    assert any("prices are added by AEO/CONTENT only" in x for x in v)
    assert not any("without the C3e disclaimer" in x for x in v)


@pytest.mark.parametrize("lang,text", [
    ("he", "הטווחים הם אינדיקטיביים בלבד ואינם הצעת מחיר. המחיר בפועל תלוי ביעד, בעונה, בגודל הקבוצה וברמת השירות."),
    ("en", "These ranges are indicative only and are not a quote. The actual price depends on the destination, season, group size and level of service."),
    ("es", "Estos rangos son solo orientativos y no constituyen un presupuesto. El precio final depende del destino, la temporada, el tamaño del grupo y el nivel de servicio."),
])
def test_c3e_disclaimers_are_the_approved_full_wording(lang, text):
    assert pol.C3E_DISCLAIMERS[lang] == text
    assert pol.has_c3e_disclaimer("Intro. " + text)
    first_sentence_only = text.split(". ")[0] + "."
    assert not pol.has_c3e_disclaimer(first_sentence_only)
    assert not pol.has_c3e_disclaimer("These ranges are indicative only and not a quote.")  # missing "are"


def test_sourced_percentage_and_canonical_numbers_pass():
    assert _iron("Uproduction Events: 1,500+ events, 130+ destinations, 25,000+ participants since 2010.") == []
    assert _iron("Turnover fell 12% ([Gallup](https://www.gallup.com/x)).") == []
    assert _iron("Insurance: check the venue's cancellation insurance terms.") == []


def test_faq_insurance_wording_blocks_only_in_faq():
    assert _iron("בדקו חוזה וביטוח לפני החתימה.") == []
    assert any("insurance" in x for x in _iron("Body.", "Uproduction Events בודקת חוזה וביטוח."))


# --- AEO 18.10 blocker 6: brand + internal links ---

def test_structure_requires_brand_and_two_internal_links():
    fm = {"canonical": "https://upe.co.il/en/x/", "faqs": [{"question": "q", "answer": "A neutral answer."}]}
    v = pol.structure_violations(fm, "## Guide\n\nA neutral buyer guide with [one](/en/a/).")
    assert any("first paragraph" in x for x in v)
    assert any("FAQ answer" in x for x in v)
    assert any("internal link" in x for x in v)
    good = {"canonical": "https://upe.co.il/en/x/",
            "faqs": [{"question": "q", "answer": "Uproduction Events can help."}]}
    body = "Uproduction Events has operated since 2010; see [a](/en/a/) and [b](https://upe.co.il/en/b/)."
    assert pol.structure_violations(good, body) == []
    # a self-link does not count
    assert pol.structure_violations(good, "Uproduction Events: [self](/en/x/) and [a](/en/a/).")


# --- AEO 18.10 blocker 5: an owned intent becomes a strengthen brief ---

def test_owned_intent_becomes_strengthen_brief():
    owners = {"owners": {"bh_il_greece": ["/2026-74/"]}}
    briefs = [{"intent": "bh_il_greece", "topic": "Greece"}, {"intent": "ps_global_best", "topic": "best"}]
    new, strengthen = pol.split_owned(briefs, owners)
    assert [b["intent"] for b in new] == ["ps_global_best"]
    assert strengthen[0]["strengthen"] == ["/2026-74/"]
    assert "/2026-74/" in pol.strengthen_html(strengthen)


def test_repo_owner_map_covers_the_203_intents():
    owned = pol.load_owners()["owners"]
    for intent in ("bh_il_greece", "bh_il_criteria", "ex_en_destination"):
        assert owned.get(intent), intent


# --- AEO recheck 18.10, blocker 1: canonical sentences must pass every check ---
CANON_SENTENCES = [
    "מעל 1,500 אירועים ביותר מ-130 יעדים.",
    "Uproduction Events פועלת מאז 2010: מעל 1,500 אירועים ביותר מ-130 יעדים.",
    "25,000 משתתפים.", "+25,000 משתתפים.", "יותר מ-25,000 משתתפים.",
    "25,000 participants.", "Over 25,000 participants since 2010.", "25K+ participants.",
    "más de 25.000 participantes.", "Más de 1.500 eventos en más de 130 destinos.",
    "1,500+ events across 130+ destinations.", "מ-1,500 אירועים.",
    "Since 2010, Uproduction Events has produced 1,500+ events.",
]


@pytest.mark.parametrize("text", CANON_SENTENCES)
def test_canonical_sentences_are_never_blocked(text):
    v = _iron(text) + [x for x in gd.check_content(text) if gd.is_blocking(x)]
    assert v == [], (text, v)


def test_euro_boundary_and_more_than_are_not_price_or_superlative():
    assert not pol._PRICE_RE.search("1,500 אירועים")
    assert pol._PRICE_RE.search("1,500 אירו")
    assert not pol._SUPERLATIVE_RE.search("ביותר מ-130 יעדים")
    assert not pol._SUPERLATIVE_RE.search("ביותר מ 130 יעדים")
    assert pol._SUPERLATIVE_RE.search("החברה הטובה ביותר")


# --- blocker 2: Hebrew prefixes in front of names and numbers ---
@pytest.mark.parametrize("text", ["עבדנו לתנובה.", "הפקנו בשופרסל.", "הפקה ליוניליוור.", "וSysAid בחרו בנו.",
                                  "עם תנובה.", "Tnuva's team.", "ולאלפא ביו."])
def test_client_names_with_prefixes_block(text):
    assert any("client/hotel name" in x for x in _iron(text)), text


@pytest.mark.parametrize("text", ["תכננו ל6 חודשים.", "תכננו ל-6 חודשים.", "כנס ל300 עובדים.",
                                  "בתשעה חודשים.", "כ-200 משתתפים."])
def test_numbers_with_prefixes_block(text):
    assert any("operational number" in x for x in _iron(text)), text


# --- blocker 3: durations and sizes that used to pass ---
@pytest.mark.parametrize("text", [
    "Reserve con seis a nueve meses de antelación.", "Planifique doce meses antes.",
    "חודשיים מראש.", "שבועיים לפני.", "שנה מראש.", "חצי שנה מראש.", "Plan at least a year ahead.",
    "חמישה חודשים.", "שבעה שבועות.", "שמונה חודשים.", "עשרה ימים.", "fifteen weeks out.", "thirty days before.",
    "200 personas.", "מאתיים משתתפים.", "Reserve un año de antelación.", "15+ years in the field.",
])
def test_duration_and_size_gaps_block(text):
    v = _iron(text) + [x for x in gd.check_content(text) if gd.is_blocking(x)]
    assert v, text


@pytest.mark.parametrize("text", ["עשרות חברות.", "שנה טובה לכולם.", "האירוע השנתי.", "Durante el año pasado.",
                                  "One of the options is a DMC.", "כמה אנשים מעורבים?", "a few weeks of prep."])
def test_ordinary_words_are_not_durations(text):
    assert [x for x in _iron(text) if "operational number" in x] == [], text


# --- non-blocking items from the recheck ---
@pytest.mark.parametrize("text", ["Founded: 2010.", "fundada en el año 2010", "15+ years of experience",
                                  "más de 15 años de experiencia", "ב-16 השנים האחרונות", "שישה עשר שנים"])
def test_extra_age_variants_block(text):
    assert any(x.startswith("canonical fact") for x in gd.check_content(text)), text


@pytest.mark.parametrize("text", ["Uproduction Events is a top producer.", "משרדנו בברצלונה.",
                                  "Tenemos oficinas en Barcelona.", "Insurance included.",
                                  "Everything is fully covered by insurance.", "Budgets from 50K per event."])
def test_small_gaps_block(text):
    assert _iron(text), text



# --- blocker 5: the intent map exactly as AEO gave it ---
def test_intent_map_matches_aeo_recheck():
    o = pol.load_owners()["owners"]
    cg = "/en/choosing-global-corporate-event-conference-production-company/"
    assert o["bh_il_greece"] == ["/אירוע-חברה-ביוון/", "/אירוע-חברה-בקפריסין/"]
    assert "/2026-74/" not in sum(o.values(), [])
    assert o["ex_es_boutique"] == ["/es/productora-boutique-vs-grandes-redes-eventos-corporativos/"]
    assert o["ps_dmc_spain"] == [
        "/en/event-production-in-spain-everything-international-companies-need-to-know/",
        "/en/incentive-travel-to-spain-the-ultimate-planning-guide-for-international-companie/"]
    assert cg in o["ex_en_destination"] and o["cmp_full_service"] == [cg]
    assert o["ex_es_elegir"] == ["/es/guia-elegir-productora-eventos-corporativos-conferencias-globales/"]
    for intent in ("bh_il_gala", "bh_il_criteria"):   # the two #216 intents
        assert o[intent]



# superlatives: a self-claim about UPE blocks; superlatives about other things do not
@pytest.mark.parametrize("text", [
    "Uproduction Events is the leading producer in Israel.", "Uproduction Events is a top producer.",
    "Uproduction Events is one of the best agencies.", "Uproduction Events, the leading boutique producer.",
    "Uproduction Events היא חברת ההפקה המובילה.", "Uproduction Events היא דוגמה מובילה.",
    "Uproduction Events היא הכי מנוסה.", "Uproduction Events es la productora líder.",
    "Uproduction Events היא החברה הטובה ביותר.",
])
def test_self_superlatives_block(text):
    assert any("superlative" in x for x in _iron(text)), text


@pytest.mark.parametrize("text", [
    "Since 2010, Uproduction Events has produced 1,500+ events, with strong relationships with top chefs.",
    "Uproduction Events מפיקה ימי גיבוש לארגונים מובילים בישראל מאז 2010.",
    "Uproduction Events פועלת ב-130+ יעדים ויכולה לייעץ על היעד המתאים ביותר למטרות שלכם.",
    "מניסיון של Uproduction Events עם 1,500+ אירועים, חמשת הטיפים המובילים הם אלה.",
    "Uproduction Events מפיקה כנסים, ובונה את לוח הזמנים אחורה מרגע ההגעה של המשתתף הרחוק ביותר.",
])
def test_superlatives_about_other_things_pass(text):
    assert [x for x in _iron(text) if "superlative" in x] == [], text
