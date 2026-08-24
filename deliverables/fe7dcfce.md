# אופטימיזציה מסחרית דחופה של עמודי הכנסים והאירועים הקיימים: הוסף CTA ברור + טופס ליד מעל ה-fold

_P0 · google_organic · updated 2026-08-24_

Now I have strong research to build the full deliverable. Let me produce the complete, ready-to-use document.

---

# 🎯 UPE | אופטימיזציה מסחרית עמודי כנסים ואירועים — DRAFT לאישור

**סוג:** אופטימיזציה CRO — CTA + טופס ליד מעל ה-fold
**ערוץ:** Google Organic (SEO עמודי כנסים/אירועים קיימים)
**עדיפות:** P0
**מטרה:** המרת 186 קליקים/שבוע לידים — שיפור של 5% = 1–2 לידים/שבוע נוספים
**סטטוס:** DRAFT — טרם פורסם, ממתין לאישור

---

## חלק א׳ — עקרונות האופטימיזציה (הבסיס המחקרי)

לפני הקוד והקופי — הנה ה-logic:

57% מהמבקרים לעולם לא גוללים מתחת ל-viewport הראשון בדסקטופ; המספר עולה ל-64% במובייל. לכן, כל מבקר שמגיע לעמודי הכנסים של UPE ולא רואה CTA וטופס מיידית — ברובו הגדול יעזוב מבלי ליצור קשר.

מעל ה-fold חייב להכיל: כותרת, תת-כותרת, CTA ראשי, ואות אמון — ללא גלילה.

לכל עמוד צריך להיות מטרה אחת ברורה. כאשר מספר CTAs מתחרים על תשומת הלב, המבקרים מהססים או לא בוחרים כלל. ב-B2B, פוקוס = המרה. יש לשמור על פעולה ראשית אחת מעל ה-fold ולחזור עליה לאורך העמוד.

CTAs בגוף ראשון ("קבל הצעה עבורי") עולים על גוף שני ב-14%. תוצאות ספציפיות ("קבל הצעת מחיר לכנס") עולות על פעלים גנריים ("שלח") ב-31%.

עמודי נחיתה עם 5 שדות או פחות ממירים טוב יותר. לוקחים את הבסיס ומאחרים. כל שדה נוסף עולה בלידים.

---

## חלק ב׳ — מבנה ה-Hero Section החדש (לכל עמוד כנסים/אירועים)

### 🔷 תבנית Hero Section — עברית (עמודי ישראל)

> **הנחיה למפתח:** להחליף את ה-hero הנוכחי בתבנית זו. כל האלמנטים צריכים להיות גלויים ללא גלילה בדסקטופ (1280px+) ובמובייל.

---

#### H1 — כותרת ראשית (לבחור לפי סוג העמוד — ראה וריאנטים בחלק ג׳)

```
הכנס הבא שלכם — בידיים הנכונות.
```
*(גרסה קצרה, 6 מילים, outcome-led)*

#### Sub-headline — תת-כותרת

```
UPE מפיקה כנסים, כינוסים ואירועי תמריץ לחברות מובילות בישראל ובעולם.  
1,500+ אירועים | 130+ יעדים | 25,000+ משתתפים.
```

#### Social Proof Strip (מיד מתחת לסאב-הדליין — שורה אחת)

```
[לוגואים של לקוחות מוכרים] · ⭐ "ביצוע ברמה אחרת" – מנהלת HR, חברת טכנולוגיה מובילה
```

---

### 📋 טופס הליד — מעל ה-fold (Desktop: מימין לטקסט / Mobile: מתחת ל-CTA)

**כותרת הטופס:**
```
קבלו הצעה מותאמת — ללא עלות וללא התחייבות
```

**שדות הטופס (מקסימום 4 שדות):**

כל שדה נוסף מוסיף חיכוך. יש להתחיל עם השדות החיוניים — שם, אימייל, חברה — ורק לאחר שערך ההצעה מצדיק זאת, לבקש פרטים נוספים.

| שדה | Label עברית | Placeholder | Required? |
|-----|-------------|-------------|-----------|
| 1 | שם מלא | ישראל ישראלי | ✅ |
| 2 | אימייל עסקי | you@company.com | ✅ |
| 3 | שם החברה | שם הארגון | ✅ |
| 4 | סוג האירוע | כנס / כינוס / טיול תמריץ / אחר (dropdown) | ✅ |

> **שדה אופציונלי (מוצג כ"לא חובה"):**
> מספר משתתפים משוער: `____` *(עוזר לנו להכין הצעה מדויקת יותר)*

**כפתור ה-CTA:**

```
🎯  קבלו הצעה לכנס שלכם  ←
```

*עיצוב: כפתור בצבע ניגודי חזק (כתום/ירוק UPE — לא אפור על לבן), פונט Bold 18px+, RTL.*

**מתחת לכפתור (מיקרו-קופי):**
```
✅ תוך 24 שעות עסקיות · ✅ ללא עלות · ✅ ללא התחייבות
```

**Privacy line (GDPR-ready לאירופה):**
```
המידע שלכם מאובטח ולא יועבר לצד שלישי. מדיניות פרטיות ←
```

---

### 📌 Sticky CTA Bar — מובייל (נדבק לתחתית המסך בגלילה)

Sticky CTAs נשארים גלויים בזמן גלילה, מה שמקל על מבקרי מובייל לפעול בכל רגע מבלי לחפש את הכפתור.

```html
<!-- Sticky Bottom Bar — Mobile Only -->
<div class="sticky-cta-bar mobile-only">
  <span>מוכנים לתכנן את הכנס הבא?</span>
  <a href="#lead-form" class="btn-primary">קבלו הצעה עכשיו ←</a>
</div>
```

---

## חלק ג׳ — וריאנטים לפי סוג עמוד (Keyword-specific)

### עמוד 1: "הפקת כנסים" / "הפקת אירועים"

| אלמנט | תוכן |
|-------|------|
| **H1** | הפקת כנסים עסקיים — מקצה לקצה |
| **Sub** | מהתכנון האסטרטגי ועד הרגע האחרון על הבמה — UPE לוקחת אחריות על הכל. |
| **CTA כפתור** | קבלו הצעה להפקת הכנס שלכם ← |
| **Social proof** | 1,500+ אירועים הופקו מאז 2010 |
| **Urgency line** | מועדי הכנסים הגדולים נסגרים מהר — בדקו זמינות ←|

---

### עמוד 2: "טיולי תמריץ" / "incentive travel"

| אלמנט | תוכן |
|-------|------|
| **H1** | טיולי תמריץ שהצוות שלכם לא ישכח |
| **Sub** | 130+ יעדים בעולם · לוגיסטיקה אחת · חוויה שמחזקת צוותים. |
| **CTA כפתור** | תכננו את טיול התמריץ שלכם ← |
| **Social proof** | 25,000+ עובדים השתתפו בטיולי UPE |
| **Urgency line** | חלונות הזמן לעונת 2025–2026 מתמלאים — בדקו זמינות |

---

### עמוד 3: "כינוסי חברה" / "אירועי HR"

| אלמנט | תוכן |
|-------|------|
| **H1** | כינוס החברה שמדבר בשפה של הצוות |
| **Sub** | חוויה שמותאמת לתרבות הארגון שלכם — מהאולם ועד הפתעות הבמה. |
| **CTA כפתור** | בואו נתכנן את הכינוס שלכם ← |
| **Social proof** | לקוחות כוללים: [לוגואים רלוונטיים] |
| **Urgency line** | מקבלים 3 בקשות ביום — מבטיחים מענה תוך 24 שעות |

---

## חלק ד׳ — קוד HTML/CSS מלא לטופס (Ready-to-Paste)

> **הנחיה:** להדביק בתוך ה-hero section הקיים, או להחליף את ה-hero. לחבר ל-CRM/HubSpot לפי הגדרות הקיימות. כל השדות מסומנים עם `dir="rtl"`.

```html
<!-- ============================================
     UPE Lead Form — Above the Fold
     DRAFT — Awaiting approval
     ============================================ -->

<section class="upe-hero-section" dir="rtl">

  <!-- LEFT COLUMN: Value Proposition -->
  <div class="hero-content">
    <h1 class="hero-h1">הכנס הבא שלכם — בידיים הנכונות.</h1>
    <p class="hero-sub">
      UPE מפיקה כנסים, כינוסים ואירועי תמריץ לחברות מובילות בישראל ובעולם.<br>
      <strong>1,500+ אירועים · 130+ יעדים · 25,000+ משתתפים</strong>
    </p>

    <!-- Trust logos strip -->
    <div class="trust-logos">
      <!-- הכנס כאן את לוגואי הלקוחות -->
      <img src="/assets/logos/client-1.svg" alt="לקוח 1" />
      <img src="/assets/logos/client-2.svg" alt="לקוח 2" />
      <img src="/assets/logos/client-3.svg" alt="לקוח 3" />
    </div>

    <!-- Quote testimonial -->
    <blockquote class="hero-quote">
      "הביצוע היה ברמה אחרת — כל פרט תוכנן עד הסוף."
      <cite>— מנהלת HR, חברת הייטק מובילה</cite>
    </blockquote>
  </div>

  <!-- RIGHT COLUMN: Lead Form -->
  <div class="hero-form-wrapper">
    <div class="form-card">
      <p class="form-headline">קבלו הצעה מותאמת — ללא עלות וללא התחייבות</p>

      <form
        id="upe-lead-form"
        class="upe-lead-form"
        method="POST"
        action="/thank-you"
        novalidate
        dir="rtl"
      >
        <!-- Field 1: Full Name -->
        <div class="form-group">
          <label for="full-name">שם מלא <span aria-hidden="true">*</span></label>
          <input
            type="text"
            id="full-name"
            name="full_name"
            placeholder="ישראל ישראלי"
            required
            autocomplete="name"
          />
        </div>

        <!-- Field 2: Business Email -->
        <div class="form-group">
          <label for="email">אימייל עסקי <span aria-hidden="true">*</span></label>
          <input
            type="email"
            id="email"
            name="email"
            placeholder="you@company.com"
            required
            autocomplete="email"
            dir="ltr"
          />
        </div>

        <!-- Field 3: Company -->
        <div class="form-group">
          <label for="company">שם החברה <span aria-hidden="true">*</span></label>
          <input
            type="text"
            id="company"
            name="company"
            placeholder="שם הארגון"
            required
            autocomplete="organization"
          />
        </div>

        <!-- Field 4: Event Type (Dropdown) -->
        <div class="form-group">
          <label for="event-type">סוג האירוע <span aria-hidden="true">*</span></label>
          <select id="event-type" name="event_type" required>
            <option value="" disabled selected>בחרו סוג אירוע</option>
            <option value="conference">כנס / Conference</option>
            <option value="convention">כינוס חברה</option>
            <option value="incentive">טיול תמריץ</option>
            <option value="teambuilding">גיבוש צוות</option>
            <option value="other">אחר</option>
          </select>
        </div>

        <!-- Optional Field: Participants -->
        <div class="form-group form-optional">
          <label for="participants">
            מספר משתתפים משוער
            <span class="optional-tag">(לא חובה — עוזר לנו להכין הצעה מדויקת)</span>
          </label>
          <input
            type="number"
            id="participants"
            name="participants"
            placeholder="לדוגמה: 150"
            min="10"
          />
        </div>

        <!-- CTA Button -->
        <button type="submit" class="cta-button">
          קבלו הצעה לכנס שלכם ←
        </button>

        <!-- Micro-copy below button -->
        <p class="form-microcopy">
          ✅ מענה תוך 24 שעות עסקיות &nbsp;·&nbsp; ✅ ללא עלות &nbsp;·&nbsp; ✅ ללא התחייבות
        </p>

        <!-- Privacy / GDPR -->
        <p class="form-privacy">
          המידע שלכם מאובטח ולא יועבר לצד שלישי.
          <a href="/privacy-policy">מדיניות פרטיות</a>
        </p>

        <!-- Hidden fields for tracking -->
        <input type="hidden" name="source_page" value="{{PAGE_SLUG}}" />
        <input type="hidden" name="utm_source" value="" id="utm_source_field" />
        <input type="hidden" name="utm_medium" value="" id="utm_medium_field" />
        <input type="hidden" name="utm_campaign" value="" id="utm_campaign_field" />
      </form>
    </div>
  </div>

</section>

<!-- ============================================
     Sticky Bottom CTA — Mobile Only
     ============================================ -->
<div class="sticky-mobile-cta" id="sticky-cta" aria-hidden="true">
  <span>מוכנים לתכנן את הכנס הבא?</span>
  <a href="#upe-lead-form" class="sticky-cta-btn">קבלו הצעה עכשיו ←</a>
</div>
```

---

## חלק ה׳ — CSS (קריטי — מעל ה-fold בלבד)

```css
/* ============================================
   UPE Hero Section — Above the Fold
   DRAFT — Awaiting approval
   ============================================ */

.upe-hero-section {
  display: grid;
  grid-template-columns: 1fr 420px;
  gap: 48px;
  align-items: center;
  padding: 64px 80px;
  min-height: 90vh;
  background: linear-gradient(135deg, #0a1628 0%, #1a3a5c 100%);
  direction: rtl;
}

/* H1 */
.hero-h1 {
  font-size: clamp(2rem, 3.5vw, 3rem);
  font-weight: 800;
  color: #ffffff;
  line-height: 1.2;
  margin-bottom: 16px;
}

/* Sub */
.hero-sub {
  font-size: 1.125rem;
  color: #c8d8e8;
  line-height: 1.6;
  margin-bottom: 24px;
}

/* Trust logos */
.trust-logos {
  display: flex;
  gap: 24px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 20px;
  filter: brightness(0) invert(1);
  opacity: 0.7;
}
.trust-logos img { height: 32px; }

/* Testimonial quote */
.hero-quote {
  font-size: 0.95rem;
  color: #a8c4dc;
  font-style: italic;
  border-right: 3px solid #f5a623; /* UPE orange — adjust to brand */
  padding-right: 14px;
  margin: 0;
}
.hero-quote cite {
  display: block;
  margin-top: 6px;
  font-size: 0.85rem;
  color: #7a9bb5;
  font-style: normal;
}

/* Form Card */
.hero-form-wrapper { position: relative; }
.form-card {
  background: #ffffff;
  border-radius: 16px;
  padding: 32px 28px;
  box-shadow: 0 24px 64px rgba(0,0,0,0.3);
}
.form-headline {
  font-size: 1.05rem;
  font-weight: 700;
  color: #0a1628;
  margin-bottom: 20px;
  text-align: center;
}

/* Form Groups */
.form-group {
  margin-bottom: 14px;
}
.form-group label {
  display: block;
  font-size: 0.85rem;
  font-weight: 600;
  color: #333;
  margin-bottom: 5px;
}
.form-group input,
.form-group select {
  width: 100%;
  padding: 10px 14px;
  border: 1.5px solid #d0d8e0;
  border-radius: 8px;
  font-size: 0.95rem;
  direction: rtl;
  transition: border-color 0.2s;
  box-sizing: border-box;
}
.form-group input:focus,
.form-group select:focus {
  border-color: #f5a623;
  outline: none;
  box-shadow: 0 0 0 3px rgba(245,166,35,0.15);
}
.optional-tag {
  font-weight: 400;
  color: #888;
  font-size: 0.78rem;
}
.form-optional { opacity: 0.85; }

/* CTA Button — HIGH CONTRAST */
.cta-button {
  width: 100%;
  padding: 14px 20px;
  background: #f5a623; /* adjust to UPE brand orange */
  color: #0a1628;
  font-size: 1.05rem;
  font-weight: 800;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  margin-top: 6px;
  transition: background 0.2s, transform 0.1s;
  letter-spacing: 0.01em;
}
.cta-button:hover {
  background: #e09410;
  transform: translateY(-1px);
}
.cta-button:active { transform: translateY(0); }

/* Micro-copy */
.form-microcopy {
  font-size: 0.78rem;
  color: #555;
  text-align: center;
  margin-top: 10px;
}

/* Privacy */
.form-privacy {
  font-size: 0.72rem;
  color: #999;
  text-align: center;
  margin-top: 8px;
}
.form-privacy a { color: #888; text-decoration: underline; }

/* ============================================
   Sticky Mobile CTA
   ============================================ */
.sticky-mobile-cta {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #0a1628;
  padding: 12px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 9999;
  box-shadow: 0 -4px 20px rgba(0,0,0,0.3);
  direction: rtl;
}
.sticky-mobile-cta span {
  color: #c8d8e8;
  font-size: 0.9rem;
}
.sticky-cta-btn {
  background: #f5a623;
  color: #0a1628;
  font-weight: 800;
  padding: 10px 20px;
  border-radius: 8px;
  text-decoration: none;
  font-size: 0.9rem;
  white-space: nowrap;
}

/* ============================================
   Responsive — Mobile First
   ============================================ */
@media (max-width: 900px) {
  .upe-hero-section {
    grid-template-columns: 1fr;
    padding: 40px 24px 100px; /* bottom pad for sticky CTA */
    min-height: auto;
  }
  .hero-h1 { font-size: 1.75rem; }
  .sticky-mobile-cta { display: flex; }
}

@media (max-width: 480px) {
  .form-card { padding: 24px 18px; }
  .hero-h1 { font-size: 1.5rem; }
}
```

---

## חלק ו׳ — JavaScript (UTM Tracking + Scroll Behavior)

```javascript
// ============================================
// UPE Lead Form — UTM Capture + Sticky CTA
// DRAFT — Awaiting approval
// ============================================

(function () {
  'use strict';

  // 1. Capture UTM params from URL → hidden form fields
  function getUrlParam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name) || '';
  }

  const utmFields = {
    utm_source: document.getElementById('utm_source_field'),
    utm_medium: document.getElementById('utm_medium_field'),
    utm_campaign: document.getElementById('utm_campaign_field'),
  };

  Object.keys(utmFields).forEach(function (key) {
    if (utmFields[key]) {
      utmFields[key].value = getUrlParam(key);
    }
  });

  // 2. Sticky CTA: hide when form is visible on mobile
  const stickyBar = document.getElementById('sticky-cta');
  const leadForm = document.getElementById('upe-lead-form');

  if (stickyBar && leadForm) {
    const observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            stickyBar.setAttribute('aria-hidden', 'true');
            stickyBar.style.display = 'none';
          } else {
            stickyBar.removeAttribute('aria-hidden');
            stickyBar.style.display = 'flex';
          }
        });
      },
      { threshold: 0.3 }
    );
    observer.observe(leadForm);
  }

  // 3. Form submission — basic GA4 event (adjust to existing analytics)
  const form = document.getElementById('upe-lead-form');
  if (form) {
    form.addEventListener('submit', function (e) {
      // Push to dataLayer (GTM)
      if (window.dataLayer) {
        window.dataLayer.push({
          event: 'lead_form_submit',
          form_id: 'upe-lead-form',
          event_type: document.getElementById('event-type')
            ? document.getElementById('event-type').value
            : 'unknown',
          page_slug: window.location.pathname,
        });
      }
    });
  }
})();
```

---

## חלק ז׳ — Thank You Page (עמוד תודה — מיד אחרי שליחת הטופס)

> **מטרה:** שימור מומנטום + הגדרת ציפיות. עמוד תודה איכותי מחזק אמון ומוריד חרטה.

```
H1: קיבלנו! נחזור אליכם תוך 24 שעות עסקיות.

Sub: צוות UPE כבר בוחן את הפרטים שהזנתם ומכין הצעה מותאמת לכנס שלכם.

Checklist:
✅ בדקו תיבת המייל — נשלח אישור לכתובת שהזנתם
✅ נציג מטעמנו יצור קשר תוך יום עסקי אחד
✅ אפשר לחזור לאתר לראות דוגמאות לאירועים שהפקנו

CTA משני: [צפו בגלריית האירועים שלנו →]
CTA שלישי: [עקבו אחרינו ב-LinkedIn ←]
```

---

## חלק ח׳ — מדידה ו-A/B Testing (מה לעקוב אחריו)

יש לבחון וריאציות בניסוח ה-CTA (דגש על מיידיות מול ערך), אורך הטופס (קצר מול ארוך), ומיקום ה-social proof (מעל ה-fold מול סמוך לכפתור).

| מה לבדוק | Variant A (ברירת מחדל) | Variant B (לבחון) | KPI |
|----------|----------------------|------------------|-----|
| ניסוח כפתור | "קבלו הצעה לכנס שלכם ←" | "קבעו שיחת יעוץ חינם ←" | CTR על כפתור |
| אורך טופס | 4 שדות | 3 שדות (ללא dropdown) | Form completion rate |
| Social proof | לוגואים בלבד | ציטוט לקוח + לוגואים | Scroll depth / submissions |
| כותרת הטופס | "ללא עלות וללא התחייבות" | "הצעה תוך 24 שעות" | Click-through to form |
| מיקום ציטוט | מתחת ל-H1 | סמוך לכפתור השליחה | Form submissions |

לכתוב השערה לכל בדיקה בפורמט: "אם נצמצם שדות מ-5 ל-3, אנחנו מצפים לשיעור השלמת טופס גבוה ב-15–25% כי כל שדה שמוסרים מפחית חיכוך בנקודת ההמרה." להריץ בדיקה אחת בכל פעם עד להגעה לרמת מובהקות סטטיסטית.

---

## חלק ט׳ — אנגלית / גרסה אירופאית (עמודים בשפה האנגלית)

> לעמודים שמטרגטים קהלי CMO/HR/CEO ב-EU

```
H1: Your Next Corporate Event — Expertly Produced.

Sub: UPE delivers conferences, conventions & incentive travel for leading companies
     across Israel and Europe.
     1,500+ Events · 130+ Destinations · 25,000+ Participants

Form Headline: Get a Tailored Proposal — Free & Non-Binding

CTA Button: Get My Event Proposal →

Micro-copy: ✅ Response within 24 business hours · ✅ No cost · ✅ No commitment

Privacy (GDPR): Your data is secure and will never be shared with third parties.
                Privacy Policy | You may withdraw consent at any time.
```

**GDPR note:** יש לכלול תמיד קישור למדיניות הפרטיות מיד ליד כפתור השליחה. לקהל אירופאי, עמידה ב-GDPR היא לא אופציה — היא אות אמון.

---

## חלק י׳ — רשימת משימות לאישור ויישום

```
□ 1. QA עיצובי — לוודא שכל האלמנטים גלויים מעל ה-fold ב-1280px, 1024px, 768px, 375px
□ 2. חיבור טופס ל-CRM (HubSpot / Salesforce / מערכת קיימת)
□ 3. הגדרת Thank You Page + redirect לאחר שליחה
□ 4. וידוא UTM tracking עובד ונכנס ל-Analytics
□ 5. הגדרת GA4 event: lead_form_submit (או GTM trigger)
□ 6. החלפת placeholder לוגואים בלוגואים אמיתיים של לקוחות
□ 7. וידוא ניגודיות כפתור עומדת ב-WCAG 2.1 AA (min contrast ratio 4.5:1)
□ 8. בדיקת מהירות טעינה — Page Speed < 3 שניות (Lighthouse)
□ 9. הגדרת A/B Test ראשון (המלצה: Variant B — 3 שדות)
□ 10. אישור משפטי לטקסט ה-GDPR לפני עמודים אירופאיים
```

---

*DRAFT בלבד — ממתין לאישור Alon לפני כל פרסום*

---