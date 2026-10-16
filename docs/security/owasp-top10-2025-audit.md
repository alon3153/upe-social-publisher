# סקירת אבטחה — OWASP Top 10:2025 (ספטמבר 2026)

מיפוי של עשר הקטגוריות ברשימת OWASP Top 10:2025 (גרסה סופית, ינואר 2026) מול
המערכת: סקריפטי Python, GitHub Actions, פונקציות Supabase Edge, דפי GitHub Pages
והתלויות. הממצאים שתוקנו מכוסים בבדיקות רגרסיה:

* `tests/test_security_hardening.py` — workflows, HTML escaping, timeouts, תלויות.
* `supabase/tests/*.test.mjs` — לוגיקת פונקציות ה-Edge (Node 22, ללא Deno).

הרצה מקומית:

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
node --experimental-strip-types --test supabase/tests/*.test.mjs
pip-audit -r requirements.txt -r requirements-dev.txt
```

## מיפוי הקטגוריות

| # | קטגוריה | מה נבדק | מצב |
|---|---|---|---|
| A01 | Broken Access Control | קישורי אישור במייל, זרימת חיבור LinkedIn, גדרות `github.actor` | תוקן: חיבור שגריר/ה מחובר/ת לא ניתן לשכתוב לחשבון אחר; כל job ידני עם סודות מוגבל לבעל הריפו |
| A02 | Security Misconfiguration | `permissions` בכל workflow, קלטי `workflow_dispatch` בתוך `run:`, כותרות תגובה | תוקן: הרשאות מינימליות מוצהרות, קלטים עוברים דרך `env`, `Cache-Control: no-store` |
| A03 | Software Supply Chain Failures | pip, Actions, ייבוא `jsr:` בפונקציה | תוקן חלקית: רצפת `requests>=2.32.4`, Dependabot, `pip-audit` ב-CI, הסרת התלות החיצונית מ-`approve`; **פתוח**: נעיצת Actions ל-SHA |
| A04 | Cryptographic Failures | TLS, השוואת טוקנים, HMAC | תקין; השוואות טוקן הפכו לקבועות בזמן |
| A05 | Injection | HTML במיילים (פלט LLM / DB), דפי callback (DOM XSS), shell ב-Actions, נתיבי קבצים | תוקן: `html.escape`, רינדור ב-`textContent`, קלטים דרך משתני סביבה, ולידציה של שם קובץ תור |
| A06 | Insecure Design | אישור פוסט בלחיצת GET מקישור במייל | **פתוח (החלטת מוצר)**: סורקי קישורים במייל עלולים "ללחוץ" — ראו למטה |
| A07 | Authentication Failures | OAuth `state` ללא nonce, callback פתוח | תוקן: nonce ב-`state` + עוגיית HttpOnly, בדיקת slug בחזרה |
| A08 | Software or Data Integrity Failures | בוטים דוחפים ישירות ל-`main`, תוכן LLM מתפרסם | **פתוח**: הגנת ענף / חתימת קומיטים — דורש הגדרה ב-GitHub |
| A09 | Security Logging & Alerting Failures | לוגים בפונקציות ה-Edge | תוקן: כל אישור/דחייה/חיבור נרשם (ללא טוקנים) |
| A10 | Mishandling of Exceptional Conditions | UPDATE שנכשל דווח כהצלחה, קריאות רשת ללא timeout, הודעות שגיאה חושפות | תוקן: בדיקת תוצאת כתיבה, timeout בכל קריאה, הודעה גנרית למשתמש ופרטים בלוג |

## מה לא נבדק / דורש גישה

* הגדרות ה-DB ב-Supabase: RLS, ברירת המחדל של עמודת `token` ב-`post_approvals`,
  הרשאות הטבלאות `app_secrets` ו-`linkedin_advocate_tokens`.
* קוד המקור של הפונקציה `executor-approve` (לא נמצא בריפו).
* היקף ההרשאות של `GH_PAT` ושל טוקני Meta/LinkedIn (ניתן לבדוק רק מהחשבונות עצמם).
* הגדרות הריפו ב-GitHub: הגנת ענף `main`, "Default workflow permissions", דרישת אישור לפריסה.

## נקודות פתוחות

1. **אישור ב-GET** — קישור "אשר" פועל בלחיצה אחת. סורקי אבטחה של דואר (Safe Links וכדומה)
   עשויים לפתוח קישורים ולאשר פוסט בלי כוונה. הפתרון המלא הוא עמוד ביניים עם כפתור
   אישור (POST). זו החלטת מוצר — לא שונה.
2. **Actions לא נעוצים ל-SHA** — `actions/checkout@v4` וכדומה. Dependabot נוסף; מומלץ לנעוץ ל-SHA.
3. **פריסה** — פונקציות ה-Edge המוקשחות נכנסות לתוקף רק אחרי הרצת `Deploy Edge Function`.
   קישור ההתחברות הישן (`state=main_callback` ללא nonce) יידחה לאחר הפריסה; יש להשתמש
   בפלט של `scripts/linkedin_org_oauth.py --authorize-url`.
