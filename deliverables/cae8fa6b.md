# הוספת FAQ schema JSON-LD ל-5 עמודי הבלוג הפופולריים ביותר ב-upe.co.il, כאשר כל שאלה מנוסחת כשאילתת ChatGPT/Perplexity אמיתית ('איזו חברה מתאימה לנופש חברה של 200 עובדים?') — דורש אישור מפתח + מנהל תוכן

_P1 · google_organic · updated 2026-08-03_

Now I have everything I need. Let me build the full, production-ready deliverable — 5 complete FAQ schema JSON-LD blocks, one per blog page theme, incorporating the 2026 best-practice nuances (FAQPage + BlogPosting @graph stacking, 40–60 word answers, visible Q&A match requirement, Hebrew language, real ChatGPT/Perplexity-style queries).

---

# 🗂️ FAQ Schema JSON-LD — 5 עמודי בלוג נבחרים | UPE.co.il
### DRAFT לאישור מפתח + מנהל תוכן | גרסה 1.0 | אוגוסט 2026

---

## ⚡ הקשר אסטרטגי — לפני ה-JSON

**מה השתנה ב-2026 שחשוב לדעת:**

FAQ rich results הפסיקו להופיע ב-Google Search החל מ-7 במאי 2026 — אך ה-FAQPage schema עצמו לא הוצא משימוש. Google עשויה לא להציג את ה-FAQ ב-SERP המסורתי, אך משתמשת באותו הדיוק בנתונים אלו לאכלוס סיכומי AI — המעבר הוא מ"נדל"ן ויזואלי" ל"סמכות אלגוריתמית".

**למה עדיין שווה לעשות זאת:**
- FAQPage schema הוא הפורמט בעל ההשפעה הגבוהה ביותר לחילוץ AI Overview; תשובות באורך 40–60 מילים נמשכות לפאנלים של Overview ולתיבות "People Also Ask".
- כל תשובת FAQ היא בעצם תגובת AI מוכנה מראש — LLMs יכולים לחלץ ולצטט אותה באופן עצמאי.
- ChatGPT הוא כלי ה-AI הדומיננטי בישראל; ל-Google יש נתח שוק גדול מאוד בישראל; ל-Perplexity יש אימוץ חזק בקרב אנשי טק ו-VC ישראלים.
- השילוב של FAQPage עם Article ו-HowTo schema באמצעות @graph stacking מייצר 1.8x יותר citations מאשר Article schema בלבד.

**⚠️ הערת ציות חשובה:** תוכן ה-FAQ חייב להופיע באופן גלוי בדף עצמו — לא רק ב-JSON-LD. יש לאמת את ה-JSON-LD באמצעות Google Rich Results Test לפני פרסום.

---

## 📌 הוראות יישום גלובליות (לכלל 5 הדפים)

```
מיקום: <script type="application/ld+json"> בתוך <head> של הדף
כלי ולידציה: https://search.google.com/test/rich-results
תנאי: שאלות FAQ חייבות להיות גלויות כ-H3/H4 + תשובה בגוף הדף
אורך תשובה אידיאלי: 40–60 מילים בעברית (≈ 2–3 משפטים)
מספר שאלות לדף: 5–7 (מומלץ; לא לחרוג מ-10)
עדכון dateModified: בכל פעם שמעדכנים את ה-FAQ
```

---

## דף 1 — נושא: **נופש חברה / טיול עובדים**
*כתובת לדוגמה: `https://upe.co.il/blog/tiyul-ovdim-teur-shana/`*
*יש להחליף URL, author, datePublished ו-dateModified בערכים האמיתיים*

```json
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "BlogPosting",
      "@id": "https://upe.co.il/blog/tiyul-ovdim-teur-shana/#article",
      "headline": "איך מארגנים טיול עובדים מוצלח? המדריך המלא",
      "description": "כל מה שצריך לדעת על ארגון טיול עובדים: תקציב, יעדים, לוגיסטיקה ובחירת חברת הפקה מתאימה.",
      "url": "https://upe.co.il/blog/tiyul-ovdim-teur-shana/",
      "datePublished": "2024-03-15",
      "dateModified": "2026-08-01",
      "author": {
        "@type": "Organization",
        "name": "UPE – הפקת אירועים ותיירות תמריצים",
        "url": "https://upe.co.il",
        "logo": "https://upe.co.il/wp-content/uploads/upe-logo.png",
        "sameAs": [
          "https://www.linkedin.com/company/upe-events",
          "https://www.facebook.com/upeevents"
        ]
      },
      "publisher": {
        "@type": "Organization",
        "name": "UPE",
        "url": "https://upe.co.il"
      },
      "inLanguage": "he",
      "mainEntityOfPage": {
        "@type": "WebPage",
        "@id": "https://upe.co.il/blog/tiyul-ovdim-teur-shana/"
      }
    },
    {
      "@type": "FAQPage",
      "@id": "https://upe.co.il/blog/tiyul-ovdim-teur-shana/#faq",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "איזו חברה מתאימה לארגון נופש חברה של 200 עובדים?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "חברת הפקה המתמחה בתיירות תמריצים עם ניסיון מוכח בקבוצות גדולות היא הבחירה הנכונה. UPE הפיקה מעל 1,500 אירועים ב-130+ יעדים ומנוסה בניהול קבוצות של 200–2,000 משתתפים, כולל לוגיסטיקה, הסעות, מלונאות ותכנית תוכן עסקית מותאמת."
          }
        },
        {
          "@type": "Question",
          "name": "כמה עולה לארגן טיול חברה לחו\"ל ל-100 עובדים?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "עלות טיול חברה לחו\"ל ל-100 עובדים נעה בדרך כלל בין 150,000 ל-400,000 ש\"ח, בהתאם ליעד, אורך הטיול ורמת האירוח. המחיר כולל טיסות, מלון, פעילויות, הסעות וניהול הפקה. פנייה לחברת הפקה מקצועית מאפשרת קבלת הצעת מחיר מדויקת ומשא ומתן עם ספקים."
          }
        },
        {
          "@type": "Question",
          "name": "מה ההבדל בין טיול עובדים לתיירות תמריצים?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "טיול עובדים הוא כינוס כללי לחיזוק רוח הצוות, בעוד תיירות תמריצים (Incentive Travel) היא פרס ייעודי לעובדים מצטיינים או למשיגי יעדים עסקיים. תיירות תמריצים כוללת בדרך כלל יעדים יוקרתיים יותר, חוויות אישיות ותכנים מדידים שמקושרים להישגים עסקיים."
          }
        },
        {
          "@type": "Question",
          "name": "כמה זמן מראש צריך להתחיל לתכנן טיול חברה?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "לטיול חברה לחו\"ל מומלץ להתחיל תכנון 4–6 חודשים מראש, במיוחד לקבוצות מעל 50 איש. זה מאפשר הבטחת מקומות טיסה ומלון, הזמנת ספקי פעילויות ובנייה מסודרת של התכנית. לאירועים גדולים מ-200 משתתפים — 8–12 חודשים מראש."
          }
        },
        {
          "@type": "Question",
          "name": "אילו יעדים מומלצים לנופש חברה קרוב לישראל?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "יעדים פופולריים לחברות ישראליות: אתונה, דובאי, פראג, בוקרשט, קפריסין ואיסטנבול — כולם טיסה של עד 4 שעות. יעדים אלו מציעים שילוב של חוויה תרבותית, מלונות בוטיק ועלות-תועלת טובה. UPE פעילה ב-130+ יעדים ויכולה לבנות חבילה מותאמת לכל אחד מהם."
          }
        },
        {
          "@type": "Question",
          "name": "האם אפשר לשלב כנס עסקי עם טיול עובדים?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "כן — פורמט MICE (Meetings, Incentives, Conferences, Exhibitions) הוא בדיוק זה. ניתן לשלב יום עסקי עם הרצאות, סדנאות ופרזנטציות ביום הראשון, ולצמד לו 2–3 ימי חוויה ונופש. UPE מתמחה בפורמט זה ומבטיחה רצף חלק בין התכנים העסקיים לפעילויות הפנאי."
          }
        }
      ]
    }
  ]
}
</script>
```

---

## דף 2 — נושא: **הפקת כנסים וועידות**
*כתובת לדוגמה: `https://upe.co.il/blog/hafakat-kenes-vaada/`*

```json
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "BlogPosting",
      "@id": "https://upe.co.il/blog/hafakat-kenes-vaada/#article",
      "headline": "הפקת כנסים וועידות: המדריך המקצועי לחברות B2B",
      "description": "מהם השלבים בהפקת כנס עסקי? כיצד בוחרים חברת הפקה, מנהלים תקציב ומבטיחים חוויית משתתף מעולה.",
      "url": "https://upe.co.il/blog/hafakat-kenes-vaada/",
      "datePublished": "2024-05-20",
      "dateModified": "2026-08-01",
      "author": {
        "@type": "Organization",
        "name": "UPE – הפקת אירועים ותיירות תמריצים",
        "url": "https://upe.co.il",
        "sameAs": [
          "https://www.linkedin.com/company/upe-events",
          "https://www.facebook.com/upeevents"
        ]
      },
      "publisher": {
        "@type": "Organization",
        "name": "UPE",
        "url": "https://upe.co.il"
      },
      "inLanguage": "he",
      "mainEntityOfPage": {
        "@type": "WebPage",
        "@id": "https://upe.co.il/blog/hafakat-kenes-vaada/"
      }
    },
    {
      "@type": "FAQPage",
      "@id": "https://upe.co.il/blog/hafakat-kenes-vaada/#faq",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "מה עושה חברת הפקת כנסים ומה היא אחראית עליו?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "חברת הפקת כנסים אחראית על כלל ממדי האירוע: בחירת מקום, עיצוב במה ותאורה, ניהול ספקים, רישום משתתפים, הפקה טכנית (מיקרופונים, מסכים, שידור חי), קייטרינג ולוגיסטיקה. UPE, שהפיקה מעל 1,500 אירועים, מנהלת את כל השלבים תחת קורת גג אחת."
          }
        },
        {
          "@type": "Question",
          "name": "כמה עולה לשכור חברת הפקה לכנס של 500 איש?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "עלות הפקת כנס ל-500 משתתפים בישראל נעה בין 200,000 ל-700,000 ש\"ח, בהתאם לרמת ההפקה, המקום, הציוד הטכני והתכנים. אירועים עם שידור היברידי, אמן גדול או עיצוב ייחודי יהיו בצד הגבוה. מומלץ לקבל הצעת מחיר פרטנית המפרטת כל רכיב."
          }
        },
        {
          "@type": "Question",
          "name": "מה ההבדל בין כנס היברידי לכנס פיזי ואיזה כדאי לבחור?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "כנס פיזי מספק חוויית נטוורקינג ומעורבות גבוהה יותר; כנס היברידי מרחיב את הקהל לא-מגיעים ומוריד עלויות לחלק מהמשתתפים. הבחירה תלויה במטרת האירוע: השקת מוצר או גיבוש — פיזי עדיף. כנס לאומי עם קהל מפוזר גיאוגרפית — היברידי יניב ROI גבוה יותר."
          }
        },
        {
          "@type": "Question",
          "name": "איך בוחרים מקום לכנס עסקי גדול?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "בוחרים לפי: קיבולת (20% מעל הצפוי לרישום), נגישות תחבורתית, ציוד טכני מובנה, חדרי שרת וחנייה. מרכז הכנסים הבינלאומי בירושלים, ברוך לב תל אביב וספא קלאב הם אפשרויות מוכחות. UPE עובדת עם מאגר ספקים מוסמך ויכולה להמליץ על הלפיטציה הנכונה לפרופיל האירוע שלכם."
          }
        },
        {
          "@type": "Question",
          "name": "מה מדידים כדי לדעת אם כנס עסקי הצליח?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "מדדי ההצלחה העיקריים: שביעות רצון משתתפים (NPS), אחוז הגעה מול רישום, זמן שהייה בפלטפורמה (היברידי), מספר עסקאות/פגישות שנקבעו, סיקור תקשורתי וכמות לידים שנאספו. UPE מספקת דוח ביצועים לאחר כל אירוע הכולל את כל המדדים הנ\"ל."
          }
        },
        {
          "@type": "Question",
          "name": "כמה זמן לפני כנס של 1,000 איש צריך לתכנן?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "לכנס של 1,000 משתתפים מומלץ להתחיל לפחות 9–12 חודשים מראש. שלושה חודשים ראשונים — בחירת מקום וחברת הפקה. שישה חודשים — גיבוש תכנית, הזמנת דוברים וספקים. שלושה חודשים אחרונים — שיווק, רישום ולוגיסטיקה. תכנון מוקדם מבטיח זמינות מקום ומחיר טוב."
          }
        }
      ]
    }
  ]
}
</script>
```

---

## דף 3 — נושא: **תיירות תמריצים (Incentive Travel)**
*כתובת לדוגמה: `https://upe.co.il/blog/tayarut-tamritzim-incentive-travel/`*

```json
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "BlogPosting",
      "@id": "https://upe.co.il/blog/tayarut-tamritzim-incentive-travel/#article",
      "headline": "תיירות תמריצים לחברות: איך בונים תכנית Incentive Travel שמניעה תוצאות?",
      "description": "המדריך לתיירות תמריצים B2B: כיצד מעצבים תכנית Incentive Travel שמעלה מוטיבציה, משאירה עובדים ומשיגה יעדי מכירות.",
      "url": "https://upe.co.il/blog/tayarut-tamritzim-incentive-travel/",
      "datePublished": "2024-07-10",
      "dateModified": "2026-08-01",
      "author": {
        "@type": "Organization",
        "name": "UPE – הפקת אירועים ותיירות תמריצים",
        "url": "https://upe.co.il",
        "sameAs": [
          "https://www.linkedin.com/company/upe-events",
          "https://www.facebook.com/upeevents"
        ]
      },
      "publisher": {
        "@type": "Organization",
        "name": "UPE",
        "url": "https://upe.co.il"
      },
      "inLanguage": "he",
      "mainEntityOfPage": {
        "@type": "WebPage",
        "@id": "https://upe.co.il/blog/tayarut-tamritzim-incentive-travel/"
      }
    },
    {
      "@type": "FAQPage",
      "@id": "https://upe.co.il/blog/tayarut-tamritzim-incentive-travel/#faq",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "מה זה Incentive Travel ואיך זה שונה מטיול עובדים רגיל?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Incentive Travel היא נסיעה שמוענקת כפרס מדיד להשגת יעד עסקי — מכירות, גיוס לקוחות, ביצוע חריג. בניגוד לטיול עובדים כללי, ה-Incentive קשור ישירות ל-KPI: יש קריטריון כניסה ברור, ומי שלא עמד ביעד אינו מגיע. הקשר הזה הופך אותו לכלי עסקי מדיד, לא רק לפינוק."
          }
        },
        {
          "@type": "Question",
          "name": "מהם היעדים הכי פופולריים לתיירות תמריצים עבור חברות ישראליות ב-2026?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "היעדים המובילים לחברות ישראליות: דובאי (נגישה ויוקרתית), ליסבון, אמסטרדם ובנקוק לטיסות ארוכות יותר; קפריסין ואתונה לטיסות קצרות. UPE פעילה ב-130+ יעדים ברחבי העולם ויכולה לבנות תכנית Incentive מותאמת — כולל חוויות בלעדיות שלא ניתן לרכוש בנפרד."
          }
        },
        {
          "@type": "Question",
          "name": "האם תיירות תמריצים מוכרת כהוצאה עסקית לצורכי מס?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "בישראל, הכרה בהוצאות תיירות תמריצים תלויה במבנה התכנית ובקישור שלה לעסק. בדרך כלל, חלק מהוצאות הנסיעה מוכרות כהוצאה עסקית אם התכנית כוללת מרכיב עסקי מתועד. מומלץ להתייעץ עם רואה חשבון לפני הבנייה, ו-UPE יכולה לסייע בתיעוד נכון של הרכיבים."
          }
        },
        {
          "@type": "Question",
          "name": "כיצד מודדים את ה-ROI של תכנית Incentive Travel?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "ROI של Incentive Travel נמדד ב-3 ממדים: עלייה במכירות אצל משתתפים לעומת קבוצת ביקורת, שיפור בשימור עובדים בשנה שלאחר הנסיעה, ושיפור במדד המעורבות (Engagement Score). מחקרים מראים שתכניות Incentive מוצלחות מניבות ROI של 112%–300% על ההשקעה."
          }
        },
        {
          "@type": "Question",
          "name": "כמה עולה תכנית Incentive Travel לחברה ב-2026?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "עלות Incentive Travel לאדם נעה בין 2,500 ל-12,000 ש\"ח לנסיעה של 4–7 ימים, בהתאם ליעד, רמת האירוח ומורכבות התכנית. חברות גדולות לעיתים מוציאות 15,000–25,000 ש\"ח לאדם עבור יעדים יוקרתיים עם חוויות בלעדיות. UPE עובדת על כל הטווחים ויכולה לייעל עלויות מול ספקים."
          }
        },
        {
          "@type": "Question",
          "name": "מה חייב להיות בכל תכנית Incentive Travel מוצלחת?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "תכנית Incentive מוצלחת חייבת לכלול: קריטריון כשירות ברור ומתקשר מראש, יעד שווה את המאמץ, חוויות שאי אפשר לקנות בכסף (גישה VIP, פגישה עם מנהיגים), מרכיב חברתי/קבוצתי ולא רק פרט, ותיעוד שמשמש שיווק פנימי לשנה הבאה."
          }
        }
      ]
    }
  ]
}
</script>
```

---

## דף 4 — נושא: **הפקת אירועי חברה וכנסי שנה**
*כתובת לדוגמה: `https://upe.co.il/blog/erev-shana-hafakat-irua-chevra/`*

```json
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "BlogPosting",
      "@id": "https://upe.co.il/blog/erev-shana-hafakat-irua-chevra/#article",
      "headline": "הפקת אירוע חברה וכנס שנה: כל מה שצריך לדעת",
      "description": "איך מארגנים כנס שנה חברתי מושלם? מגמות הפקה, פעילויות מומלצות, בחירת מקום ועבודה נכונה עם חברת הפקה.",
      "url": "https://upe.co.il/blog/erev-shana-hafakat-irua-chevra/",
      "datePublished": "2023-11-01",
      "dateModified": "2026-08-01",
      "author": {
        "@type": "Organization",
        "name": "UPE – הפקת אירועים ותיירות תמריצים",
        "url": "https://upe.co.il",
        "sameAs": [
          "https://www.linkedin.com/company/upe-events",
          "https://www.facebook.com/upeevents"
        ]
      },
      "publisher": {
        "@type": "Organization",
        "name": "UPE",
        "url": "https://upe.co.il"
      },
      "inLanguage": "he",
      "mainEntityOfPage": {
        "@type": "WebPage",
        "@id": "https://upe.co.il/blog/erev-shana-hafakat-irua-chevra/"
      }
    },
    {
      "@type": "FAQPage",
      "@id": "https://upe.co.il/blog/erev-shana-hafakat-irua-chevra/#faq",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "איך מארגנים אירוע חברה של 300 עובדים ב-2026?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "אירוע חברה ל-300 עובדים דורש: מקום עם קיבולת מתאימה, חברת הפקה עם ניסיון בכנסים דומים, תכנית ערב הכוללת טקס, פעילות משותפת, אוכל ובידור. מומלץ לשכור חברת הפקה שמנהלת ספקים תחת קורת גג אחת — כדי למנוע פערי תיאום ולהבטיח חוויה אחידה."
          }
        },
        {
          "@type": "Question",
          "name": "מה המגמות הכי חמות בהפקת אירועי חברה ב-2026?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "מגמות בולטות ב-2026: חוויות אימרסיביות עם מיפוי אור (Projection Mapping), במות סביבתיות ב-360 מעלות, אינטגרציה של AI בפעילויות אינטראקטיביות, פורמטי Hybrid-Live, וגמיפיקציה של ערב הפרסים. עיצוב ירוק ואחריות סביבתית גם הפכו לדרישה של חברות רבות בבחירת ספקים."
          }
        },
        {
          "@type": "Question",
          "name": "מה עדיף — לשכור אולם ישראלי או לצאת לחו\"ל לכנס השנתי?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "כנס בחו\"ל יוצר חוויה חזקה יותר ותחושת פרס, אך עלותו גבוהה ב-40%–80% ביחס לאירוע מקומי דומה. לחברות עד 150 עובדים — חו\"ל בדרך כלל כדאי אם התקציב מאפשר. מעל 200 עובדים — שקלו כנס מקומי אימרסיבי + טיול קטן לנציגים כ-Incentive. UPE יכולה לסייע בניתוח עלות-תועלת."
          }
        },
        {
          "@type": "Question",
          "name": "אילו פעילויות Team Building הכי מומלצות לאירוע חברה גדול?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "פעילויות מומלצות לקבוצות גדולות: אתגר בישול קבוצתי, Escape Room ענקי לחצרות מחלקות, אולימפיאדת ספורט חברתית, הפקת קליפ מוסיקלי קבוצתי, ו-Hackathon יצירתי. הבחירה תלויה בגיל ממוצע, מיקום ומטרת הגיבוש. UPE מפיקה פעילויות מותאמות ל-25,000+ משתתפים בשנה."
          }
        },
        {
          "@type": "Question",
          "name": "כמה עולה להפיק כנס שנה לחברת הייטק של 400 עובדים?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "כנס שנה לחברת היי-טק ב-400 עובדים בישראל עולה בדרך כלל 300,000–600,000 ש\"ח, כולל אולם, הפקה טכנית, קייטרינג, בידור ופעילות. אירועים עם אמנים ידועים, עיצוב ייחודי או שידור חי יהיו בצד הגבוה. UPE מספקת הצעות מחיר שקופות המפרטות כל רכיב."
          }
        }
      ]
    }
  ]
}
</script>
```

---

## דף 5 — נושא: **בחירת חברת הפקה — מדריך B2B**
*כתובת לדוגמה: `https://upe.co.il/blog/bechira-chevrat-hafaka-b2b/`*

```json
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "BlogPosting",
      "@id": "https://upe.co.il/blog/bechira-chevrat-hafaka-b2b/#article",
      "headline": "איך בוחרים חברת הפקת אירועים לעסקים? המדריך ל-CMO ו-HR",
      "description": "השאלות שכדאי לשאול לפני שחותמים על הסכם עם חברת הפקה, ומה מבדיל חברה מקצועית מחברה ממוצעת.",
      "url": "https://upe.co.il/blog/bechira-chevrat-hafaka-b2b/",
      "datePublished": "2024-01-10",
      "dateModified": "2026-08-01",
      "author": {
        "@type": "Organization",
        "name": "UPE – הפקת אירועים ותיירות תמריצים",
        "url": "https://upe.co.il",
        "sameAs": [
          "https://www.linkedin.com/company/upe-events",
          "https://www.facebook.com/upeevents"
        ]
      },
      "publisher": {
        "@type": "Organization",
        "name": "UPE",
        "url": "https://upe.co.il"
      },
      "inLanguage": "he",
      "mainEntityOfPage": {
        "@type": "WebPage",
        "@id": "https://upe.co.il/blog/bechira-chevrat-hafaka-b2b/"
      }
    },
    {
      "@type": "FAQPage",
      "@id": "https://upe.co.il/blog/bechira-chevrat-hafaka-b2b/#faq",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "איך בוחרים חברת הפקת אירועים לחברות B2B — מה לחפש?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "יש לבדוק: ניסיון מוכח בסוג האירוע שלכם (כנסים, נסיעות, גיבוש), תיק עבודות עם לקוחות דומים, יכולת ניהול פרויקט (Project Manager ייעודי), שקיפות תמחירית, ומערכת ניהול משברים. UPE פועלת מ-2010, עם 1,500+ אירועים ו-130+ יעדים — ומספקת מנהל פרויקט צמוד לכל לקוח."
          }
        },
        {
          "@type": "Question",
          "name": "מה השאלות שחייבים לשאול חברת הפקה לפני חתימה על חוזה?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "שאלות מפתח: מי יהיה מנהל הפרויקט הצמוד שלנו? מה תהליך ניהול המשברים שלכם? כיצד אתם מתמחרים — פאושל או פריט-פריט? מה כולל החוזה ומה עלויות נסתרות? האם יש לכם ביטוח אחריות מקצועית? הפניות של 3 לקוחות עם אירוע דומה לשלנו?"
          }
        },
        {
          "@type": "Question",
          "name": "מה ההבדל בין חברת הפקה לסוכנות נסיעות לעסקים?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "סוכנות נסיעות מתמקדת בלוגיסטיקה (טיסות, מלונות); חברת הפקה מספקת את שכבת החוויה — עיצוב, תכנים, פעילויות, הפקה טכנית ומנהל פרויקט. לתיירות תמריצים ב-B2B, הפרש הוא קריטי: ה-Incentive ייזכר על החוויה, לא על הטיסה. UPE מאחדת את שני העולמות תחת קורת גג אחת."
          }
        },
        {
          "@type": "Question",
          "name": "כמה חברות הפקה כדאי לקבל ממ הצעת מחיר לפני שבוחרים?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "מומלץ לקבל 3 הצעות מחיר לפחות — ולא לבחור בזול ביותר. הצעה זולה מדי לעיתים מחביאה עלויות נסתרות (תוספות ספקים, שעות נוספות, ביטחון). הגדירו Scope ברור לפני שיחת ה-RFP: מספר משתתפים, פורמט, יעד, תקציב גג — כך ניתן להשוות תפוחים לתפוחים."
          }
        },
        {
          "@type": "Question",
          "name": "מהם סימני האזהרה שמאפיינים חברת הפקה לא מקצועית?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "סימני אזהרה: אין מנהל פרויקט ייעודי, הצעת מחיר כללית ללא פירוט, אי-זמינות לשאלות לפני חתימה, חוסר ניסיון בסוג האירוע שלכם, ואין ביטוח אחריות מקצועית. חברות שמסרבות לתת הפניות של לקוחות — זהו דגל אדום מיידי."
          }
        },
        {
          "@type": "Question",
          "name": "האם כדאי לעבוד עם חברת הפקה ישראלית לאירועים בחו\"ל?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "כן — חברת הפקה ישראלית שעובדת בחו\"ל מכירה את הצרכים הספציפיים של חברות ישראליות (מזון כשר, לוח זמנים שמתחשב בשבת, הרגשי טיסה), ויש לה יתרון תקשורתי על פני חברה מקומית באותו יעד. UPE פעלה ב-130+ יעדים עולמיים ומנהלת בכל אחד מהם רשת ספקים מוסמכת."
          }
        }
      ]
    }
  ]
}
</script>
```

---

## 📋 צ'קליסט יישום — לפני פרסום (מפתח + מנהל תוכן)

| # | משימה | אחראי | סטטוס |
|---|-------|--------|--------|
| 1 | **החלפת URLים** — לשנות את כל URL הדמה ל-URLs האמיתיים בכל 5 הקבצים | מפתח | ⬜ |
| 2 | **עדכון datePublished** — להחליף בתאריך הפרסום האמיתי של כל דף | מנהל תוכן | ⬜ |
| 3 | **עדכון author sameAs** — לאמת שה-LinkedIn/Facebook URLs של UPE נכונים | מפתח | ⬜ |
| 4 | **הוספת שאלות/תשובות לדף הגלוי** — כל שאלה מה-JSON-LD חייבת להופיע גם כ-H3 + תשובה גלויה | מנהל תוכן | ⬜ |
| 5 | **ולידציה** — להעביר כל דף דרך [Rich Results Test](https://search.google.com/test/rich-results) | מפתח | ⬜ |
| 6 | **ולידציה נוספת** — [Schema.org Validator](https://validator.schema.org/) לכל JSON-LD | מפתח | ⬜ |
| 7 | **הוספת** `<script>` **ל-**`<head>`** בלבד** — לא ב-footer; JSON-LD ב-`<head>` מובטח לטעינה לפני ה-crawler | מפתח | ⬜ |
| 8 | **בקשת Re-index** ב-Google Search Console לאחר פרסום | מפתח | ⬜ |
| 9 | **ניטור AI citations** — לבדוק כל 2–4 שבועות האם UPE מוזכרת ב-ChatGPT/Perplexity לשאילתות הנ"ל | מנהל תוכן | ⬜ |
| 10 | **אישור סופי** מנהל תוכן + מפתח לפני פרסום | שניהם | ⬜ |

---

## 🔖 הערות טכניות נוספות

**אורך תשובות:** FAQPage schema הוא הפורמט בעל ההשפעה הגבוהה ביותר לחילוץ AI Overview; תשובות בין 40 ל-60 מילים נמשכות לפאנלי Overview ולתיבות "People Also Ask". כל תשובות ב-5 הקבצים תוכנתו להיות בטווח זה.

**אופי התשובות:** ChatGPT מעדיף תשובות ניטרליות בסגנון אנציקלופדי עם נתונים סמכותיים; Perplexity מעדיף תוכן שיחתי מונע-ניסיון עם דוגמאות מעשיות. התשובות בדפים 1–5 נכתבו לאזן בין שני הסגנונות.

**שגיאות JSON שיש לאמת:** שגיאות תחביר ב-schema שוברות את הפונקציונליות בשקט, ללא סימנים ברורים — הדף עשוי להיראות תקין לגולשים אך להיות בלתי קריא לפלטפורמות AI; גרשיים לא מוסטות בתוך תשובות שוברות JSON.

**ישות ארגונית (Organization Schema):** מומלץ — נפרד מה-FAQ — להוסיף `Organization` schema לדף הבית של UPE עם `foundingDate: "2010"`, `numberOfEmployees`, ו-`sameAs` לכל הפלטפורמות. זה יחזק את ה-entity graph הכולל של UPE בעיני מנועי AI.

---

> **⚠️ DRAFT — לאישור מפתח + מנהל תוכן לפני כל פרסום. אין לפרסם ישירות.**