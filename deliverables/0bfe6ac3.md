# תיקון Salesforce OAuth (HTTP 400 invalid_grant): לחדש את ה-refresh token / credentials של חיבור ה-CRM בדחיפות

_P0 · crm · updated 2026-08-10_

להלן הדליברבל המלא — מוכן לאישור אלון.

---

# 🔴 P0 | תיקון Salesforce OAuth — `invalid_grant` HTTP 400
### SOP (Standard Operating Procedure) + Checklist מלא לאדמין ה-CRM של UPE
**סטטוס:** DRAFT — ממתין לאישור לפני ביצוע  
**עדיפות:** קריטית / חסם KPI  
**בעל המשימה:** ___________  
**תאריך יעד לתיקון:** ___________

---

## 🧭 רקע ומשמעות עסקית

חיבור ה-CRM (Salesforce) של UPE מחזיר שגיאת OAuth **HTTP 400 `invalid_grant`**.

שגיאה זו היא הדרך הגנרית של OAuth 2.0 לומר שה-authorization grant (קוד אוטורציה או refresh token) אינו תקף, פג תוקף, בוטל, או שכבר נעשה בו שימוש.

**השפעה עסקית מיידית על UPE:**
- ❌ KPI #1 — **לידים מוסמכים (MQL):** ללא נתון
- ❌ KPI #2 — **לידים דיגיטליים:** ללא נתון
- ❌ **אפס visibility על ה-pipeline** — כל פעולת מרקטינג (קמפיינים, אאוטריץ', רטרגטינג) אינה ניתנת להוכחת ROI
- ❌ דוחות הנהלה (CMO/CEO) — ריקים

**כל רגע שהחיבור שבור = נתוני לידים שנאבדים ולא יחזרו.**

---

## 🔍 שלב 1 — אבחון: מה גרם לשגיאה?

השגיאה `HTTP 400 invalid_grant` עם התיאור "expired access/refresh token" יכולה לנבוע ממספר סיבות. סיבה נפוצה אחת: יותר מדי access grants ל-Connected App עבור משתמש מסוים — Salesforce מאפשר רק 5 access grants לכל Connected App למשתמש.

סיבה נפוצה נוספת: חסרים ה-scopes `refresh_token` או `offline_access` בבקשת ה-authorization.

Refresh tokens נמשכים זמן ארוך יותר מ-access tokens, אך הם אינם נצחיים. הם יכולים לפוג עקב חוסר שימוש, להיות מבוטלים על-ידי המשתמש, או להיפסל עקב אירועי אבטחה. כשזה קורה, כל ניסיון לרענן את ה-access token מחזיר `invalid_grant`.

Salesforce tokens יכולים לפוג בהתאם להגדרות ה-session של הארגון.

### ✅ טבלת אבחון — זהה את הגורם שלך

| # | בדיקה | תסמין | פתרון |
|---|--------|--------|--------|
| 1 | האם ה-Connected App ישן / לא עודכן? | Token פג עקב אי-שימוש | ← **שלב 2A** |
| 2 | האם ה-scope `refresh_token` מוגדר? | חסר scope | ← **שלב 2B** |
| 3 | האם המשתמש המקשר שינה סיסמה/MFA? | Token בוטל | ← **שלב 2C** |
| 4 | האם יש יותר מ-5 grants למשתמש? | Grant הישן ביותר בוטל אוטומטית | ← **שלב 2D** |
| 5 | האם ה-base URL נכון? (sandbox vs. production) | Authentication failure | ← **שלב 2E** |
| 6 | האם שעון השרת מסונכרן? | JWT drift error | ← **שלב 2F** |

---

## 🛠️ שלב 2 — תיקון: פרוטוקול לפי גורם

### 🔧 2A — חידוש Refresh Token (הפתרון הנפוץ ביותר — עשה זאת ראשון)

יש לבצע reauthorization של ה-App על-ידי הפניית המשתמש להתחבר שוב דרך ה-OAuth flow.

**שלבי ביצוע:**

```
1. היכנס ל-Salesforce Setup
2. Quick Find → "Connected Apps" → בחר את ה-App הרלוונטי
3. לחץ "Manage" → "Edit Policies"
4. תחת "OAuth Policies" → "Refresh Token Policy" → בחר:
   ✅ "Refresh token is valid until revoked"
5. שמור → חזור לאינטגרציה → לחץ "Reconnect" / "Authorize"
6. התחבר עם credentials של System User ייעודי (לא משתמש אישי)
7. העתק את ה-refresh token החדש והגדר אותו בחיבור ה-CRM
```

ודא שהאפשרות **"Refresh token is valid until revoked"** אכן נבחרה.

---

### 🔧 2B — הוסף את ה-scope החסר

יש להוסיף `refresh_token` או `offline_access` לרשימת ה-scopes. דוגמה לבקשה תקינה הכוללת scopes של `api`, `id`, ו-`refresh_token`:

```
https://[YourDomain].my.salesforce.com/services/oauth2/authorize?
  response_type=token
  &client_id=[CLIENT_ID]
  &redirect_uri=[REDIRECT_URI]
  &scope=api id refresh_token
```

**בממשק Salesforce:**
```
Setup → Apps → App Manager → [שם ה-App] → Edit
→ "Selected OAuth Scopes" → הוסף:
  ✅ Access and manage your data (api)
  ✅ Perform requests at any time (refresh_token, offline_access)
  ✅ Access your basic information (id)
→ Save → המתן 2-10 דקות להפצה
```

---

### 🔧 2C — המשתמש המקשר שינה סיסמה / MFA

ביטול על-ידי המשתמש הוא גורם מרכזי נוסף. אם משתמש ביטל גישה מהגדרות החשבון שלו, ה-refresh token מיד נפסל.

**פתרון:** צור **System Integration User** ייעודי ב-Salesforce שאינו קשור לאדם ספציפי:
```
Setup → Users → New User
  Profile: System Administrator (or custom Integration Profile)
  Username: salesforce-integration@upe-events.com
  License: Salesforce Integration (חוסך עלות רישיון)
→ הגדר MFA ייעודי לחשבון זה
→ בצע OAuth authorization מחדש עם משתמש זה
```

---

### 🔧 2D — יותר מ-5 Grants למשתמש

Salesforce מאפשר רק 5 access grants ל-Connected App עבור משתמש מסוים. לאחר ניסיון חמישי, האישור הישן ביותר מבוטל אוטומטית.

**ניקוי Grants:**
```
Setup → Connected Apps OAuth Usage → [שם ה-App]
→ "View Users" → מצא את המשתמש → "Revoke"
→ בצע authorization מחדש (grant אחד בלבד)
```

---

### 🔧 2E — בדיקת Base URL (Sandbox vs. Production)

בדוק תחילה אם ה-base URL שגוי — זה תיקון פשוט.

| סביבה | URL נכון |
|--------|----------|
| Production | `https://login.salesforce.com` |
| Sandbox | `https://test.salesforce.com` |
| Custom Domain | `https://[YourDomain].my.salesforce.com` |

**בחיבור ה-CRM — ודא שה-Instance URL תואם בדיוק לסביבת ה-Salesforce שלך.**

---

### 🔧 2F — סנכרון שעון שרת (אם משתמשים ב-JWT Bearer Flow)

חלק מה-OAuth flows, בפרט כאלה שמשתמשים ב-JWT bearer tokens, רגישים לשעון המערכת.

```bash
# Linux/Mac — בדיקת drift
timedatectl status
# ודא שה-NTP מסונכרן: "NTP synchronized: yes"

# אם לא מסונכרן:
sudo timedatectl set-ntp true
```

---

## 🏆 שלב 3 — פתרון לטווח ארוך: JWT Bearer Flow (מניעה קבועה)

השתמש ב-**OAuth 2.0 JWT Bearer Flow** במקום לשמור refresh token שהתקבל דרך אינטראקציה של משתמש. זהו הפתרון הרובוסטי ביותר לאינטגרציות server-to-server.

שים לב: Salesforce אוכף דרישות אבטחה חדשות מ-Summer 2026. יש להגדיר מדיניות גישה ל-OAuth של Connected Apps, כולל הגדרת אילו משתמשים יכולים לגשת ואיזה מגבלות IP חלות.

בנוסף, יצירת Connected Apps חדשים הוגבלה החל מ-Spring '26. ניתן להמשיך להשתמש ב-Connected Apps קיימים, אך Salesforce ממליצה לעבור ל-External Client Apps.

**מפת מעבר ל-JWT Bearer:**
```
1. צור X.509 Certificate (openssl req -x509 -sha256 -nodes...)
2. העלה את ה-certificate ל-Connected App ב-Salesforce
3. הגדר "Use digital signatures" ב-Connected App
4. Pre-authorize את ה-System User
5. החלף את קוד ה-OAuth Flow בחיבור ה-CRM ל-JWT-based flow
6. אין יותר refresh tokens שפגים!
```

---

## 🔒 שלב 4 — מניעה עתידית: Policy Hardening

כ-best practice, מפתחים יכולים להגדיר מדיניות refresh token מתאימה, לתזמן רענון tokens קבוע, לבטל tokens ישנים, ולנטר עליות ב-`invalid_grant`.

כ-best practice אבטחה, Salesforce ממליצה שה-refresh tokens בארגון יפגו לאחר 90 יום או פחות.

| פעולה | תדירות | אחראי |
|--------|---------|--------|
| בדיקת תקינות חיבור Salesforce | שבועי | אדמין CRM |
| Rotation של credentials | כל 90 יום | IT/אדמין |
| בדיקת Salesforce Trust Status | לפי צורך | מרקטינג |
| דוח `invalid_grant` מ-Salesforce Event Log | חודשי | אדמין CRM |
| ביקורת Active Grants למשתמש הסיסטם | רבעוני | IT |

---

## ✅ Checklist ביצוע — לסימון בזמן אמת

```
תיקון מיידי:
[ ] 1. בדוק base URL (sandbox/production)
[ ] 2. בדוק Connected App Policies → "Refresh token valid until revoked"
[ ] 3. בדוק OAuth Scopes — וודא refresh_token/offline_access קיים
[ ] 4. בצע Revoke + Re-authorize עם System Integration User
[ ] 5. הדבק token חדש בחיבור ה-CRM
[ ] 6. בדוק חיבור → תקבל 200 OK

אימות:
[ ] 7. KPI "לידים מוסמכים" מציג נתונים ב-Dashboard
[ ] 8. KPI "לידים דיגיטליים" מציג נתונים ב-Dashboard
[ ] 9. Pipeline report ב-Salesforce תקין
[ ] 10. שלח אישור ל-CMO שה-visibility שוחזר

מניעה:
[ ] 11. תעד את ה-System User שמשמש לאינטגרציה
[ ] 12. הגדר תזכורת calendar ל-90 יום מהיום לבדיקת token
[ ] 13. שקול מעבר ל-JWT Bearer Flow (Q3 2026)
[ ] 14. הוסף monitoring alert ל-invalid_grant מ-Salesforce Event Log
```

---

## 📞 אנשי קשר לסלמציה (מלא לפני ביצוע)

| תפקיד | שם | פרטי קשר |
|--------|-----|-----------|
| Salesforce Admin | | |
| IT / DevOps | | |
| CMO (לקבלת אישור ROI) | | |
| ספק האינטגרציה (אם רלוונטי) | | |

---

> ⚠️ **DRAFT בלבד — לא לביצוע ללא אישור אלון.**  
> מסמך זה הוכן על-ידי סוכן ה-AI של UPE Marketing. יש לאמת את הפרטים הטכניים מול אדמין ה-Salesforce לפני ביצוע כל שינוי ב-Production.

---