# TikTok Publisher Setup — UPE

Step-by-step להפעלת פרסום אוטומטי ל-TikTok @alonouaknine.

---

## חד-פעמי: יצירת אפליקציית מפתחים ב-TikTok

### 1. הרשמה ל-TikTok Developers
- כנס ל-https://developers.tiktok.com
- לחץ **Log in** (בחר Log in with TikTok)
- התחבר עם החשבון `@alonouaknine`
- אם זו פעם ראשונה — תתבקש לאשר Developer Terms

### 2. יצירת אפליקציה
- **Manage Apps** → **Connect an app** (או **Create app**)
- מלא:
  - **App name:** `UPE Social Publisher`
  - **Category:** Business / Productivity
  - **Description:** "Internal tool for Uproduction Events to publish company event videos"
  - **Website URL:** `https://www.upe.co.il`
  - **Terms of service URL:** (אופציונלי בסנדבוקס)
  - **Privacy policy URL:** (אופציונלי בסנדבוקס)
- **Platform:** Web
- שמור

### 3. הוספת מוצרים (Products)
בתוך עמוד האפליקציה:
- **Add Products** → **Login Kit** (אפשר Web/Desktop)
- **Add Products** → **Content Posting API**

### 4. הגדרת Redirect URI
- בקטע Login Kit → Settings:
- **Redirect URI:** הוסף:
```
https://alon3153.github.io/upe-social-publisher/tiktok-callback.html
```
- שמור

### 5. בקשת Scopes
- **Scopes** → לחץ Add:
  - `user.info.basic` ✅ (מאושר מיידית)
  - `video.upload` ✅ (מאושר מיידית — Inbox draft)
  - `video.publish` ⏳ (דורש app audit — Direct Post)
- שלח לאישור

### 6. העתקת מפתחות
- בעמוד **App keys** (או **Basic info**):
- העתק:
  - **Client Key** (קוד 18-20 תווים)
  - **Client Secret** (קוד ארוך)

### 7. הוסף ל-`.env`
```bash
TIKTOK_CLIENT_KEY=awxxxxxxxxxxxxxx
TIKTOK_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## חד-פעמי: OAuth — קבלת access token

מהתיקייה `upe-social-publisher/`:
```bash
python3 scripts/tiktok_oauth.py
```

מה קורה:
1. נפתח דפדפן עם דף האישור של TikTok
2. אישור הרשאות לאפליקציה
3. אתה מועבר לעמוד callback ב-GitHub Pages עם הקוד
4. **העתק את הקוד** (יש כפתור 📋 העתק)
5. **הדבק** בטרמינל ולחץ Enter
6. הסקריפט מחליף את הקוד ל-access_token ושומר ב-`.env`

תוקף:
- `access_token`: 24 שעות (מתחדש אוטומטית בסקריפט הפרסום)
- `refresh_token`: 365 ימים (חידוש פעם בשנה)

---

## שימוש שוטף: פרסום וידאו

### מצב 1: Inbox (זמין מיידית, ללא audit)
```bash
python3 scripts/publish_ab_dental_tiktok.py
```
הסרטון מועלה כטיוטה לתיבת ה-Inbox שלך באפליקציית TikTok.
פתח את האפליקציה → תיבת התראות → לחץ על הטיוטה → **Post**.

### מצב 2: Direct Post (אחרי audit מ-TikTok)
```bash
python3 scripts/publish_ab_dental_tiktok.py --direct --privacy PUBLIC_TO_EVERYONE
```
הסרטון מתפרסם ישירות.

---

## הוספת חשבונות נוספים
לדוגמה `@uproductionevents` ל-TikTok:
- חזור ל-`developers.tiktok.com` עם החשבון השני
- צור אפליקציה נפרדת או הוסף Login נוסף
- עדכן את `.env` עם prefix שונה:
  - `TIKTOK_UPRODUCTION_CLIENT_KEY=...`
- שכפל את scripts ל-script ייעודי לחשבון

---

## פתרון בעיות

### "Invalid redirect URI"
- ודא ש-URI ב-TikTok app **בדיוק** זהה ל-`REDIRECT_URI` בסקריפט
- כולל את `.html` בסוף

### "Scope not authorized"
- חזור ל-TikTok app → Scopes
- ודא ש-`video.upload` מאושר (סטטוס Approved)
- `video.publish` יקבל "Pending review" — זה תקין

### "Token expired"
- הסקריפט יחדש אוטומטית
- אם נכשל: רוץ שוב `python3 scripts/tiktok_oauth.py`

### העלאה תקועה במצב PROCESSING
- TikTok לפעמים לוקח עד 5 דקות
- בדוק את האפליקציה (Inbox) אחרי 5-10 דקות
