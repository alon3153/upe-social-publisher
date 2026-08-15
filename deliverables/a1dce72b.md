# חיבור מחדש של Salesforce (תיקון OAuth / token): ללא חיבור אין מדידת לידים, אין ייחוס דיגיטלי, ואין אפשרות לנהל Pipeline. יש לבצע reset ל-connected app credentials ולאמת HTTP 200 לפני כל פעולה שיווקית אחרת.

_P0 · crm · updated 2026-08-15_

---

# 🔧 UPE Marketing — CRM Reconnection SOP
## חיבור מחדש של Salesforce: OAuth Reset + HTTP 200 Validation
### דרגת עדיפות: P0 | ערוץ: CRM | מסמך לאישור אדם לפני ביצוע

> **⚠️ DRAFT — לאישור לפני ביצוע. אין להפעיל בסביבת Production ללא sign-off.**

---

## 📋 רקע ונחיצות

ללא חיבור Salesforce תקין, ה-Scorecard השיווקי של UPE נותר **❌❌** בכל המדדים הקריטיים:
- אין מדידת לידים → יעד **10 לידים/חודש** בלתי ניתן למעקב
- אין ייחוס דיגיטלי → אי אפשר לדעת אילו ערוצים עובדים
- אין Pipeline management → Sales ו-Marketing לא מסונכרנים

Salesforce מחמירה את דרישות ה-OAuth, כולל PKCE ו-Refresh Token Rotation, ושינויים אלו משפיעים על אופן האימות של אינטגרציות ושמירת הגישה.

החל מ-Spring '26, Salesforce חסמה יצירת Connected Apps חדשות כחלק ממיגרציה מתוכננת ל-External Client Apps — אך אפליקציות קיימות ממשיכות לפעול.

---

## 🗺️ מפת הבעיות הנפוצות + פתרונות

| שגיאה נפוצה | גורם | פתרון |
|---|---|---|
| `invalid_grant` | Token פג תוקף / שימוש חוזר | Reset + Re-authorize |
| `401 Unauthorized` | Client Secret שגוי | Rotate Credentials |
| `403 Forbidden` | IP Restriction Policy | עדכון Network Access |
| Token לא מתחדש | Rotation לא מוגדר | הגדרת Refresh Token Rotation |
| חיבור נופל אחרי Sandbox Refresh | Org ID חדש | Re-authenticate מלא |

---

## ✅ SOP — נוהל חיבור מחדש מלא (Step-by-Step)

### שלב 0: הכנה לפני הכל
```
זמן מומלץ: שעות בשימוש נמוך (בוקר מוקדם / סוף שבוע)
```
מומלץ לתזמן את ה-Reset בשעות בשימוש נמוך כדי למזער השפעה.

**Checklist טרום-ביצוע:**
- [ ] גיבוי של `client_id` + `client_secret` הנוכחיים (copy למקום מאובטח)
- [ ] תיעוד של כל ה-Redirect URIs המוגדרות
- [ ] הכנת רשימת כל המערכות התלויות ב-Connected App זה (Marketing Automation, Website Forms, Reporting)
- [ ] קבלת גישת System Administrator ל-Salesforce Org
- [ ] אם ה-Security Token של החשבון משמש במקומות נוספים, יש לדעת שה-Reset עלול לגרום לבעיות גם שם.

---

### שלב 1: אימות סטטוס החיבור הנוכחי

**בדיקה מהירה — cURL:**
```bash
# בדיקת Token קיים
curl -X POST https://login.salesforce.com/services/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=refresh_token" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "refresh_token=YOUR_REFRESH_TOKEN"

# תוצאה צפויה: HTTP 200 + access_token בגוף התגובה
# תוצאה שמסמנת בעיה: HTTP 400 עם {"error":"invalid_grant"}
```

**תיעוד ממצא:**
- [ ] HTTP Status שהתקבל: `______`
- [ ] Error message (אם קיים): `______`

---

### שלב 2: Reset Connected App Credentials

**נתיב בממשק Salesforce:**

```
Setup → Quick Find: "App Manager" → מצא את ה-App הרלוונטי
→ ▼ (dropdown) → "View" → לחץ "Edit" 
→ גלול ל-"API (Enable OAuth Settings)"
→ לחץ "Click to reveal" ליד Consumer Secret
→ לחץ "Reset Consumer Secret"
→ אשר בחלון הדיאלוג
→ שמור את ה-Consumer Secret החדש מיד (מופיע פעם אחת בלבד)
```

**חלופה דרך Manage Connected Apps:**

```
Setup → Quick Find: "Connected Apps" → "Manage Connected Apps"
→ לחץ על שם ה-App
→ "Edit Policies"
→ תחת "OAuth Policies" — בדוק הגדרות Refresh Token Policy
→ ודא שמוגדר: "Refresh token is valid until revoked"
```

> ⚠️ יצירת Connected Apps חדשות מוגבלת החל מ-Spring '26. אפשר להמשיך להשתמש ב-App קיים, אך Salesforce ממליצה לעבור ל-External Client Apps.

---

### שלב 3: עדכון Credentials בכל המערכות המחוברות

לאחר קבלת ה-`client_secret` החדש — יש לעדכן **בכל** המקומות הבאים לפני בדיקת HTTP 200:

```
□ Marketing Automation Platform (HubSpot / ActiveCampaign / אחר)
□ Website Contact Forms
□ Landing Page integrations
□ Zapier / Make (Integromat) Zaps
□ Google Analytics / GTM שמחברים ל-SF
□ כל סקריפט Webhook מותאם אישית
```

חשוב: בעת פיתוח OAuth, יש להעביר מידע רגיש תמיד ב-body של POST Request ולא ב-URL query string. מידע רגיש כולל usernames, passwords, OAuth tokens, ו-client secrets.

---

### שלב 4: Re-Authorization Flow — OAuth 2.0

Authorization codes ב-Salesforce הם Single-Use ותקפים ל-10 דקות בלבד. ניסיון לעשות שימוש חוזר או עיכוב בשימוש בהם יגרום לשגיאת invalid_grant.

**Authorization URL (החלף את הפרמטרים):**
```
https://login.salesforce.com/services/oauth2/authorize
  ?response_type=code
  &client_id=YOUR_NEW_CLIENT_ID
  &redirect_uri=https://YOUR_REDIRECT_URI
  &scope=api refresh_token offline_access
  &state=UPE_CRM_RECONNECT_2026
```

**Token Exchange (מיד לאחר קבלת ה-code):**
```bash
curl -X POST https://login.salesforce.com/services/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "client_id=YOUR_NEW_CLIENT_ID" \
  -d "client_secret=YOUR_NEW_CLIENT_SECRET" \
  -d "redirect_uri=https://YOUR_REDIRECT_URI" \
  -d "code=AUTHORIZATION_CODE_FROM_STEP_ABOVE"
```

**תגובה תקינה (HTTP 200):**
```json
{
  "access_token": "00D...",
  "refresh_token": "5Aep...",
  "instance_url": "https://YOUR_ORG.salesforce.com",
  "id": "https://login.salesforce.com/id/...",
  "token_type": "Bearer",
  "issued_at": "1723xxxxxx",
  "signature": "..."
}
```

---

### שלב 5: Validation — אימות HTTP 200 מלא

**בדיקת חיבור פעיל — Salesforce REST API:**
```bash
# בדיקת Identity
curl -X GET "https://YOUR_ORG.salesforce.com/services/data/v61.0/" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json"

# תוצאה צפויה: HTTP 200 + רשימת API endpoints
```

**בדיקת Lead Object — קריטי לייחוס שיווקי:**
```bash
# Query על Lead האחרון
curl -X GET \
  "https://YOUR_ORG.salesforce.com/services/data/v61.0/query/?q=SELECT+Id,LastName,Email,LeadSource,CreatedDate+FROM+Lead+ORDER+BY+CreatedDate+DESC+LIMIT+1" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# תוצאה צפויה: HTTP 200 + שורת Lead
```

**בדיקת כתיבה — Test Lead Creation:**
```bash
curl -X POST \
  "https://YOUR_ORG.salesforce.com/services/data/v61.0/sobjects/Lead/" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "LastName": "TEST_CONNECTION_UPE",
    "Company": "UPE_CRM_TEST",
    "LeadSource": "Web",
    "Email": "test-connection@upe-events.com",
    "Status": "New"
  }'

# תוצאה צפויה: HTTP 201 Created + {"id":"00Q...","success":true}
# מחיקה מיד לאחר הבדיקה!
```

---

### שלב 6: Refresh Token Rotation — אבטחה עדכנית

סיבוב תקופתי של Refresh Tokens הוא best practice תעשייתי שמסייע לשמור על אבטחת האינטגרציה עם Salesforce.

PKCE הופך למחייב עבור Public Clients ומומלץ בחום לכל OAuth flows.

**הגדרת Token Rotation ב-Salesforce Setup:**
```
Setup → Connected Apps → Manage Connected Apps → [שם ה-App]
→ Edit Policies → Refresh Token Policy:
  ✅ "Refresh token is valid until revoked"  ← מומלץ ל-CRM
  או
  □ "Immediately expire refresh token"  ← אם רוצים Rotation מלא
```

---

### שלב 7: Lead Attribution — אימות Pipeline

לאחר HTTP 200 מאומת, יש לוודא שהייחוס השיווקי עובד:

**בדיקת Lead Source Mapping:**
```
□ Web Form → SF Lead (LeadSource = "Web") ✓
□ LinkedIn Ad → SF Lead (LeadSource = "Social Media") ✓  
□ Email Campaign → SF Lead (LeadSource = "Email") ✓
□ Event/Conference → SF Lead (LeadSource = "Conference") ✓
□ Referral → SF Lead (LeadSource = "Word of Mouth") ✓
```

**בדיקת Pipeline View:**
```
Reports → New Report → "Leads" → Group By "LeadSource" 
→ פילטר: Created Date = "This Month"
→ ודא שמדד "10 לידים/חודש" מדיד
```

---

### שלב 8: IP Restrictions — אם החיבור עדיין נכשל

Salesforce עשויה לחסום בקשות Token מ-IPs לא מורשים אם מדיניות IP Restriction מופעלת ב-Org.

```
Setup → Network Access → ודא שה-IP של שרת ה-Marketing/Automation כלול
Setup → Connected Apps → [App] → Edit Policies 
→ תחת "IP Relaxation": 
   בחר "Relax IP restrictions" לצורך בדיקה ראשונית
```

---

## 📊 Checklist סיכום — Go/No-Go לפעולה שיווקית

| בדיקה | סטטוס | מבצע | תאריך |
|---|---|---|---|
| Consumer Secret הוחלף | ☐ | | |
| Credentials עודכנו בכל המערכות | ☐ | | |
| `GET /services/data/` → HTTP 200 | ☐ | | |
| Lead Query → HTTP 200 + תוצאות | ☐ | | |
| Test Lead נוצר ונמחק | ☐ | | |
| Refresh Token שמור ומוגן | ☐ | | |
| Lead Source attribution עובד | ☐ | | |
| Pipeline Report מציג לידים | ☐ | | |
| **✅ מותר להמשיך לפעולה שיווקית** | ☐ | | |

---

## 🚨 Spring '26 Alert — External Client Apps

אדמינים שזקוקים ל-App חדש (לא רק reconnect) חייבים לבצע מיגרציה ל-External Client Apps (ECAs) או לבקש Exception מ-Salesforce Support.

אפשר להמשיך להשתמש ב-Connected App קיים גם לאחר Spring '26, אך Salesforce ממליצה לעבור ל-External Client Apps.

**לבדיקה אם נדרשת מיגרציה:**
```
Setup → External Client Apps → Settings
→ אם הכפתור "New Connected App" אפור — המיגרציה נדרשת
→ אם ה-App הקיים עובד — אפשר להמשיך ב-Reconnect בלבד
```

---

## ⏱️ אומדן זמן ביצוע

| פעולה | זמן משוער |
|---|---|
| שלבים 0–2 (Reset + הכנה) | 15–20 דקות |
| שלב 3 (עדכון כל המערכות) | 30–60 דקות (תלוי במספר integrations) |
| שלבים 4–5 (Auth + Validation) | 10–15 דקות |
| שלבים 6–7 (Rotation + Attribution) | 20–30 דקות |
| **סה"כ** | **~1.5–2 שעות** |

---

## 📞 אם שום דבר לא עובד — Escalation Path

1. **שלב ראשון:** בדוק Salesforce Status Page: `status.salesforce.com`
2. **שלב שני:** פתח Case ב-Salesforce Support עם:
   - Org ID
   - Connected App Name
   - Error response מלא (JSON)
   - Timestamp של ניסיונות
3. **שלב שלישי:** שקול מעבר ל-**JWT Bearer Token Flow** — במיוחד אם ה-Org משתמש ב-MFA, מומלץ לעבור ל-JWT Bearer Token Flow.

---

> **DRAFT בלבד — מסמך זה מיועד לאישור Alon לפני כל ביצוע. אין לשתף עם צדדים חיצוניים.**

---