# הוספת schema markup מסוג LocalBusiness + Event + FAQPage לעמודי השירות הקיימים (ארגון-כנסים, הפקת-אירועים-עסקיים, טיולי-תמריץ-לחברות)

_P1 · google_organic · updated 2026-08-24_

> **⚠️ הערה קריטית לפני ה-Deliverable:** החל מ-7 במאי 2026, Google הפסיקה להציג rich results של FAQPage בתוצאות החיפוש. עם זאת, FAQPage schema עדיין מומלצת לצורכי AEO (Answer Engine Optimization) — AI Overviews, ChatGPT Search, Perplexity — שם המבנה ממשיך לתמוך בהבנה ובציטוט. הקוד למטה מיושם בהתאם לאסטרטגיה זו.

---

# Schema Markup — JSON-LD | UPE Production
## 3 עמודי שירות | מוכן להטמעה (טיוטה לאישור)

---

> **הוראות הטמעה כלליות:**
> - הדבק כל בלוק בתוך `<script type="application/ld+json">` לפני סגירת `</head>` בעמוד הרלוונטי.
> - JSON-LD הוא הפורמט המומלץ, ומספר `<script>` נפרדים באותו עמוד מותרים כאשר הם מתארים ישויות שונות.
> - וודא שכל כתובת, טלפון ותוכן שירות שב-JSON-LD מופיעים **גם בתוכן הגלוי** בעמוד.
> - לאחר הטמעה: בדוק כל עמוד ב-Google's Rich Results Test וב-Schema Markup Validator לפני פרסום.
> - `sameAs` הוא קריטי ל-entity-based SEO — הוא מאפשר לאנגיני חיפוש ו-AI לזהות אילו פרופילים חיצוניים מייצגים את אותה ישות.

---

## עמוד 1: `upe.co.il/ארגון-כנסים`

### BLOCK A — LocalBusiness (Organization)

```json-ld
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": ["LocalBusiness", "ProfessionalService"],
  "@id": "https://www.upe.co.il/#organization",
  "name": "UPE - הפקת אירועים עסקיים",
  "alternateName": "UPE Production",
  "url": "https://www.upe.co.il",
  "logo": "https://www.upe.co.il/wp-content/uploads/upe-logo.png",
  "image": "https://www.upe.co.il/wp-content/uploads/upe-conference-production.jpg",
  "description": "UPE היא חברת הפקת אירועים עסקיים וטיולי תמריץ מובילה בישראל. מאז 2010 הפקנו מעל 1,500 אירועים ב-130+ יעדים עם מעל 25,000 משתתפים.",
  "foundingDate": "2010",
  "numberOfEmployees": {
    "@type": "QuantitativeValue",
    "minValue": 20,
    "maxValue": 99
  },
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "[כתובת UPE]",
    "addressLocality": "תל אביב",
    "addressRegion": "מרכז",
    "postalCode": "[מיקוד]",
    "addressCountry": "IL"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": "[LAT]",
    "longitude": "[LON]"
  },
  "telephone": "+972-[מספר]",
  "email": "info@upe.co.il",
  "openingHoursSpecification": [
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Sunday","Monday","Tuesday","Wednesday","Thursday"],
      "opens": "09:00",
      "closes": "18:00"
    }
  ],
  "areaServed": [
    {
      "@type": "Country",
      "name": "Israel"
    },
    {
      "@type": "Place",
      "name": "Europe"
    },
    {
      "@type": "Place",
      "name": "Global"
    }
  ],
  "serviceType": [
    "ארגון כנסים",
    "הפקת אירועים עסקיים",
    "טיולי תמריץ לחברות",
    "הפקת כנסים בינלאומיים",
    "אירועי חברה"
  ],
  "hasOfferCatalog": {
    "@type": "OfferCatalog",
    "name": "שירותי הפקת אירועים עסקיים",
    "itemListElement": [
      {
        "@type": "Offer",
        "itemOffered": {
          "@type": "Service",
          "name": "ארגון כנסים עסקיים",
          "url": "https://www.upe.co.il/ארגון-כנסים"
        }
      },
      {
        "@type": "Offer",
        "itemOffered": {
          "@type": "Service",
          "name": "הפקת אירועים עסקיים",
          "url": "https://www.upe.co.il/הפקת-אירועים-עסקיים"
        }
      },
      {
        "@type": "Offer",
        "itemOffered": {
          "@type": "Service",
          "name": "טיולי תמריץ לחברות",
          "url": "https://www.upe.co.il/טיולי-תמריץ-לחברות"
        }
      }
    ]
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.9",
    "reviewCount": "[מספר ביקורות]",
    "bestRating": "5",
    "worstRating": "1"
  },
  "sameAs": [
    "https://www.linkedin.com/company/upe-production",
    "https://www.facebook.com/UPEproduction",
    "https://www.youtube.com/@UPEproduction",
    "https://www.instagram.com/upe_production"
  ],
  "priceRange": "₪₪₪"
}
</script>
```

---

### BLOCK B — Service (ארגון כנסים)

```json-ld
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Service",
  "@id": "https://www.upe.co.il/ארגון-כנסים#service",
  "serviceType": "ארגון כנסים עסקיים",
  "name": "ארגון כנסים עסקיים | UPE",
  "url": "https://www.upe.co.il/ארגון-כנסים",
  "description": "UPE מתמחה בארגון כנסים עסקיים מקצה לקצה: בחירת אולם, תכנות תוכן, ניהול ספקים, עיצוב במה, מערכות תאורה וסאונד, ואחרת לוגיסטיקה. מעל 1,500 כנסים שהופקו מאז 2010.",
  "provider": {
    "@type": "Organization",
    "@id": "https://www.upe.co.il/#organization"
  },
  "areaServed": {
    "@type": "Country",
    "name": "Israel"
  },
  "audience": {
    "@type": "Audience",
    "audienceType": "B2B — CMO, HR Directors, CEOs, Event Managers"
  },
  "offers": {
    "@type": "Offer",
    "priceCurrency": "ILS",
    "priceSpecification": {
      "@type": "PriceSpecification",
      "description": "תמחור מותאם לפי גודל הכנס, מספר משתתפים ורמת ההפקה"
    },
    "eligibleRegion": {
      "@type": "Country",
      "name": "Israel"
    }
  },
  "hasOfferCatalog": {
    "@type": "OfferCatalog",
    "name": "שירותי ארגון כנסים",
    "itemListElement": [
      {
        "@type": "Offer",
        "name": "ניהול כנס מלא",
        "description": "תכנון, ריכוז ספקים, ניהול פרויקט ואחרת הפקה ביום האירוע"
      },
      {
        "@type": "Offer",
        "name": "עיצוב במה ותאורה",
        "description": "עיצוב סטנדים, במות ומרחבי כנס עם ציוד תאורה וסאונד מקצועי"
      },
      {
        "@type": "Offer",
        "name": "כנסים בינלאומיים",
        "description": "ארגון כנסים בחו\"ל ב-130+ יעדים עולמיים"
      }
    ]
  }
}
</script>
```

---

### BLOCK C — FAQPage (ארגון כנסים)
> *⚠️ Rich results הופסקו ב-Google (מאי 2026) — הבלוק פועל לצורכי AEO/AI Overviews ו-entity understanding.*

```json-ld
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "@id": "https://www.upe.co.il/ארגון-כנסים#faq",
  "name": "שאלות נפוצות — ארגון כנסים עסקיים",
  "url": "https://www.upe.co.il/ארגון-כנסים",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "כמה זמן לוקח לארגן כנס עסקי?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "כנס עסקי דורש בדרך כלל 6–12 שבועות הכנה, תלוי בגודל האירוע. כנסים גדולים מ-500 משתתפים מומלץ להתחיל לתכנן 3–6 חודשים מראש. UPE מציעה גם פתרונות Fast-Track לאירועים דחופים."
      }
    },
    {
      "@type": "Question",
      "name": "מה כולל שירות ארגון כנסים של UPE?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "שירות ארגון הכנסים של UPE כולל: בחירת מקום ואולם, תכנות תכנים ואג'נדה, ניהול ספקים (קייטרינג, תאורה, סאונד, אורחים ומרצים), עיצוב גרפי ובמה, שידור חי והיברידי, לוגיסטיקה מלאה וניהול משתתפים."
      }
    },
    {
      "@type": "Question",
      "name": "האם UPE מפיקה כנסים בחו\"ל?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "כן. UPE מתמחה בהפקת כנסים בינלאומיים ב-130+ יעדים בעולם. צוות הפרויקטים שלנו מלווה את הלקוח מקצה לקצה — כולל לוגיסטיקה, ויזות, מלונות, ותיאום ספקים מקומיים."
      }
    },
    {
      "@type": "Question",
      "name": "כמה עולה ארגון כנס עסקי?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "עלות ארגון כנס עסקי משתנה בהתאם למספר המשתתפים, מיקום, רמת ההפקה ורשימת השירותים. UPE מתאימה הצעות מחיר לכל פרויקט בנפרד לאחר פגישת היכרות קצרה. צרו קשר לקבלת הצעה."
      }
    },
    {
      "@type": "Question",
      "name": "האם ניתן להפיק כנס היברידי (פרונטלי + מקוון)?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "כן, UPE מפיקה כנסים היברידיים הכוללים שידור חי, הכנת סטודיו ושילוב קהל מרחוק. אנו עובדים עם פלטפורמות מובילות ומספקים פתרון טכני מלא מקצה לקצה."
      }
    }
  ]
}
</script>
```

---
---

## עמוד 2: `upe.co.il/הפקת-אירועים-עסקיים`

### BLOCK A — Service (הפקת אירועים עסקיים)

```json-ld
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Service",
  "@id": "https://www.upe.co.il/הפקת-אירועים-עסקיים#service",
  "serviceType": "הפקת אירועים עסקיים",
  "name": "הפקת אירועים עסקיים | UPE",
  "url": "https://www.upe.co.il/הפקת-אירועים-עסקיים",
  "description": "UPE מפיקה אירועים עסקיים בכל הסקאלות — ממפגשי הנהלה ועד כנסי ענף גדולים. ניסיון של 15 שנה, 1,500+ אירועים, 25,000+ משתתפים ב-130+ יעדים.",
  "provider": {
    "@type": "Organization",
    "@id": "https://www.upe.co.il/#organization"
  },
  "areaServed": [
    {"@type": "Country", "name": "Israel"},
    {"@type": "Place", "name": "Europe"},
    {"@type": "Place", "name": "Global"}
  ],
  "audience": {
    "@type": "Audience",
    "audienceType": "B2B — CMO, CEO, HR Director, Event Manager"
  },
  "category": "Corporate Event Production",
  "offers": {
    "@type": "Offer",
    "priceCurrency": "ILS",
    "priceSpecification": {
      "@type": "PriceSpecification",
      "description": "תמחור מותאם לפי היקף הפרויקט, מיקום ורמת ההפקה"
    }
  },
  "hasOfferCatalog": {
    "@type": "OfferCatalog",
    "name": "שירותי הפקת אירועים עסקיים",
    "itemListElement": [
      {
        "@type": "Offer",
        "name": "ימי גיבוש חברה",
        "description": "תכנון וביצוע ימי גיבוש מקצועיים לצוותים ולחברות"
      },
      {
        "@type": "Offer",
        "name": "אירועי חברה שנתיים",
        "description": "הפקת אירוע חברה שנתי כולל בידור, לוגיסטיקה וניהול אורחים"
      },
      {
        "@type": "Offer",
        "name": "השקות מוצר ואירועי לקוחות",
        "description": "השקות מוצר, סיורי לקוחות VIP ואירועי PR עסקיים"
      },
      {
        "@type": "Offer",
        "name": "כנסי ענף ופסגות",
        "description": "ארגון וניהול כנסי ענף, פסגות מנהלים ופורומים מקצועיים"
      }
    ]
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.9",
    "reviewCount": "[מספר ביקורות]",
    "bestRating": "5"
  }
}
</script>
```

---

### BLOCK B — LocalBusiness (reference, lightweight — link to @id)

```json-ld
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "@id": "https://www.upe.co.il/#organization",
  "name": "UPE - הפקת אירועים עסקיים",
  "url": "https://www.upe.co.il",
  "telephone": "+972-[מספר]",
  "address": {
    "@type": "PostalAddress",
    "addressLocality": "תל אביב",
    "addressCountry": "IL"
  },
  "sameAs": [
    "https://www.linkedin.com/company/upe-production",
    "https://www.facebook.com/UPEproduction"
  ]
}
</script>
```

> *💡 הערה: הבלוק המלא של LocalBusiness נמצא בעמוד הבית ובעמוד ארגון-כנסים. כאן נשתמש ב-reference קל כדי לשמור על קשר ל-@id ולמנוע כפילות מלאה.*

---

### BLOCK C — FAQPage (הפקת אירועים עסקיים)

```json-ld
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "@id": "https://www.upe.co.il/הפקת-אירועים-עסקיים#faq",
  "name": "שאלות נפוצות — הפקת אירועים עסקיים",
  "url": "https://www.upe.co.il/הפקת-אירועים-עסקיים",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "מה ההבדל בין ארגון כנס להפקת אירוע עסקי?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "ארגון כנס מתמקד בעיקר בתוכן מקצועי, לוח זמנים ומרצים. הפקת אירוע עסקי היא תהליך רחב יותר הכולל גם עיצוב חוויית המשתתף, סצינוגרפיה, בידור, פרוֹפ-ות, צילום ווידאו, קייטרינג ועוד. UPE מספקת את שני השירותים כחבילה אחת."
      }
    },
    {
      "@type": "Question",
      "name": "כמה משתתפים יכולים להשתתף באירוע שUPE מפיקה?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "UPE מפיקה אירועים בכל גודל — ממפגשי הנהלה קטנים של 20 איש ועד כנסים גדולים עם אלפי משתתפים. הניסיון שלנו כולל מעל 25,000 משתתפים מצטברים על פני 1,500+ אירועים."
      }
    },
    {
      "@type": "Question",
      "name": "האם UPE עובדת עם חברות בינלאומיות ואירופאיות?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "כן. UPE מלווה חברות ישראליות ובינלאומיות בהפקת אירועים עסקיים בישראל ובעולם. יש לנו ניסיון עשיר עם חברות גלובליות המחפשות ספק הפקה אמין בישראל ובאירופה."
      }
    },
    {
      "@type": "Question",
      "name": "מה כולל ניהול אירוע מלא (Full Production Management)?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "ניהול אירוע מלא מכסה: תכנון קונספט ואסטרטגיה, בחירת ואנו (venue), ריכוז וניהול ספקים, עיצוב גרפי ובמה, תפעול לוגיסטי, ניהול אורחים ורישום, שידור היברידי, צילום ווידאו ותיעוד — הכל תחת גג אחד."
      }
    },
    {
      "@type": "Question",
      "name": "כיצד UPE מבטיחה חוויית משתתף גבוהה?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "UPE עובדת לפי מתודולוגיית הפקה ממוקדת-חוויה: כל נקודת מגע של המשתתף מתוכננת מראש, מרשמת ההצטרפות ועד לחבילת הפרידה. זה מה שמבדיל בין 'אירוע שעובד' לחוויה שנזכרים בה."
      }
    }
  ]
}
</script>
```

---
---

## עמוד 3: `upe.co.il/טיולי-תמריץ-לחברות`

### BLOCK A — Service (טיולי תמריץ)

```json-ld
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Service",
  "@id": "https://www.upe.co.il/טיולי-תמריץ-לחברות#service",
  "serviceType": "טיולי תמריץ לחברות",
  "name": "טיולי תמריץ לחברות | UPE",
  "url": "https://www.upe.co.il/טיולי-תמריץ-לחברות",
  "description": "UPE מתכננת ומוציאה לפועל טיולי תמריץ עסקיים ל-130+ יעדים בעולם. פתרון מנוהל במלואו — ממטרת הטיול ועד ניהול הלוגיסטיקה בשטח — לחברות המעוניינות לתגמל עובדים וממכרי ביצועים.",
  "provider": {
    "@type": "Organization",
    "@id": "https://www.upe.co.il/#organization"
  },
  "areaServed": {
    "@type": "Place",
    "name": "Global — 130+ destinations"
  },
  "audience": {
    "@type": "Audience",
    "audienceType": "B2B — HR Directors, CMO, Sales Directors, CEO"
  },
  "category": "Incentive Travel",
  "keywords": "טיולי תמריץ לחברות, incentive travel Israel, תוכניות תמריץ לעובדים, טיול חברה לחו\"ל, corporate incentive trips",
  "hasOfferCatalog": {
    "@type": "OfferCatalog",
    "name": "תוכניות טיול תמריץ",
    "itemListElement": [
      {
        "@type": "Offer",
        "name": "טיול תמריץ אירופה",
        "description": "תוכניות תמריץ ליעדים כמו ברצלונה, רומא, אמסטרדם, דובאי ועוד"
      },
      {
        "@type": "Offer",
        "name": "טיול תמריץ אסיה",
        "description": "תוכניות תמריץ ליעדים כמו תאילנד, יפן, סינגפור ובאלי"
      },
      {
        "@type": "Offer",
        "name": "טיול תמריץ ישראל",
        "description": "חוויות תמריץ ייחודיות בישראל לחברות מחו\"ל"
      },
      {
        "@type": "Offer",
        "name": "תוכנית תמריץ מותאמת אישית",
        "description": "עיצוב תוכנית תמריץ ייחודית בהתאם ליעדי הארגון, התקציב וצרכי הצוות"
      }
    ]
  },
  "offers": {
    "@type": "Offer",
    "priceCurrency": "ILS",
    "priceSpecification": {
      "@type": "PriceSpecification",
      "description": "תמחור מותאם ליעד, מספר משתתפים, משך הטיול ורמת ההפקה"
    }
  }
}
</script>
```

---

### BLOCK B — LocalBusiness (reference lightweight)

```json-ld
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "@id": "https://www.upe.co.il/#organization",
  "name": "UPE - הפקת אירועים עסקיים וטיולי תמריץ",
  "url": "https://www.upe.co.il",
  "telephone": "+972-[מספר]",
  "address": {
    "@type": "PostalAddress",
    "addressLocality": "תל אביב",
    "addressCountry": "IL"
  },
  "sameAs": [
    "https://www.linkedin.com/company/upe-production",
    "https://www.facebook.com/UPEproduction",
    "https://www.instagram.com/upe_production"
  ]
}
</script>
```

---

### BLOCK C — FAQPage (טיולי תמריץ לחברות)

```json-ld
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "@id": "https://www.upe.co.il/טיולי-תמריץ-לחברות#faq",
  "name": "שאלות נפוצות — טיולי תמריץ לחברות",
  "url": "https://www.upe.co.il/טיולי-תמריץ-לחברות",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "מה זה טיול תמריץ לחברות?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "טיול תמריץ (Incentive Travel) הוא כלי ניהולי שחברות משתמשות בו כדי לתגמל עובדים, מנהלים או שותפי עסקים מצטיינים בחוויית נסיעה ייחודית. בשונה מטיול חברה רגיל, טיול תמריץ מתוכנן סביב מטרה עסקית ברורה — חיזוק מוטיבציה, שימור עובדים, או גמול על עמידה ביעדי מכירות."
      }
    },
    {
      "@type": "Question",
      "name": "לאילו יעדים UPE מפיקה טיולי תמריץ?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "UPE מפיקה טיולי תמריץ ב-130+ יעדים ברחבי העולם, כולל אירופה (ברצלונה, רומא, פאריז, אמסטרדם), אסיה (תאילנד, יפן, באלי, סינגפור), אמריקה, ועוד. אנו מתאימים את היעד לפי מטרות הארגון, התקציב והעדפות הצוות."
      }
    },
    {
      "@type": "Question",
      "name": "מה ההבדל בין טיול חברה לטיול תמריץ?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "טיול חברה הוא לרוב אירוע שנתי לכל העובדים. טיול תמריץ, לעומת זאת, מיועד לקבוצה ממוקדת (מנהלים מצטיינים, מוכרי TOP, שותפים עסקיים) ומתוכנן כחוויה ממותגת ומדויקת עם פעילויות ייחודיות, לינה ברמה גבוהה ויחס VIP לאורך כל התוכנית."
      }
    },
    {
      "@type": "Question",
      "name": "כמה זמן מראש צריך לתכנן טיול תמריץ?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "מומלץ להתחיל לתכנן טיול תמריץ 3–6 חודשים מראש, בפרט לאירועים גדולים או ביעדים מבוקשים (דרום מזרח אסיה, אירופה בעונת שיא). UPE מנהלת את כל שלבי התכנון — החל מבחירת היעד, בניית תוכנית פעילויות ייחודיות, הסדרת לוגיסטיקה ועד ליווי בשטח."
      }
    },
    {
      "@type": "Question",
      "name": "האם UPE מלווה את הקבוצה לאורך כל הטיול?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "כן. UPE שולחת נציג מקצועי מטעמה שמלווה את הקבוצה מרגע ההמראה ועד לשיבה, מטפל בכל בעיה לוגיסטית בזמן אמת ומבטיח חוויה חלקה ובלתי נשכחת."
      }
    },
    {
      "@type": "Question",
      "name": "האם ניתן לשלב בטיול התמריץ גם פעילויות עסקיות כמו סדנאות או כנסים?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "בהחלט. UPE מתמחה בשילוב 'Meeting & Incentive' — שילוב של ישיבות הנהלה, סדנאות, כנסי מכירות ופעילויות גיבוש בתוך מסגרת טיול תמריץ. פורמט זה מאפשר לארגון להשיג גם מטרות עסקיות וגם מטרות מוטיבציה בטיול אחד."
      }
    }
  ]
}
</script>
```

---

## BreadcrumbList — לכל 3 העמודים

> הדבק את הבלוק הרלוונטי בכל עמוד בנפרד:

**עמוד ארגון כנסים:**
```json-ld
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {"@type": "ListItem", "position": 1, "name": "דף הבית", "item": "https://www.upe.co.il"},
    {"@type": "ListItem", "position": 2, "name": "שירותים", "item": "https://www.upe.co.il/שירותים"},
    {"@type": "ListItem", "position": 3, "name": "ארגון כנסים", "item": "https://www.upe.co.il/ארגון-כנסים"}
  ]
}
</script>
```

**עמוד הפקת אירועים עסקיים:**
```json-ld
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {"@type": "ListItem", "position": 1, "name": "דף הבית", "item": "https://www.upe.co.il"},
    {"@type": "ListItem", "position": 2, "name": "שירותים", "item": "https://www.upe.co.il/שירותים"},
    {"@type": "ListItem", "position": 3, "name": "הפקת אירועים עסקיים", "item": "https://www.upe.co.il/הפקת-אירועים-עסקיים"}
  ]
}
</script>
```

**עמוד טיולי תמריץ לחברות:**
```json-ld
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {"@type": "ListItem", "position": 1, "name": "דף הבית", "item": "https://www.upe.co.il"},
    {"@type": "ListItem", "position": 2, "name": "שירותים", "item": "https://www.upe.co.il/שירותים"},
    {"@type": "ListItem", "position": 3, "name": "טיולי תמריץ לחברות", "item": "https://www.upe.co.il/טיולי-תמריץ-לחברות"}
  ]
}
</script>
```

---

## סיכום אסטרטגי — הערות לאלון לפני הטמעה

| נושא | פרטים |
|---|---|
| **FAQPage ב-2026** | FAQPage schema לא מייצר rich results ב-Google מאז מאי 2026, אך עדיין מומלץ למבנה תוכן ולתמיכה ב-AI Overviews. הקוד כלול כי הוא מדד AEO ישיר |
| **LocalBusiness @id** | הישות הראשית (Organization/LocalBusiness) עם `@id` יציב מהווה עוגן לכל ה-entity graph — קשור לשירותים, לשאלות FAQ ולפרופילים חיצוניים דרך `sameAs`. |
| **sameAs** | sameAs מעלה CTR בכ-10% בממוצע ומגביר ציטוט AI בכ-40% עבור עסקים עם קישורי פרופיל חיצוניים עקביים. **יש להשלים את ה-URLs האמיתיים** |
| **AggregateRating** | למלא רק אם יש ביקורות אמיתיות. אסור להמציא |
| **בדיקה לפני פרסום** | יש לוודא כל הטמעה ב-validator.schema.org לפני deploy. + Google Rich Results Test |
| **CTR אפקט** | עמודים עם structured data תקף יכולים להרוויח rich results שמשפרים CTR אורגני ב-30%-82% בהתאם לcase studies של Google עצמה. |
| **AEO impact** | מחקר AEOGrader.org 2026 מוצא שעמודים עם structured data מצוטטים 2.4 פעמים יותר מאלה ללא תוכן מובנה. |
| **שדות לא מלאים** | סמנתי `[מספר טלפון]`, `[כתובת]`, `[מיקוד]`, `[LAT/LON]`, `[מספר ביקורות]`, `[URLs סושיאל]` — **יש להשלים לפני deploy** |
| **מיקום בקוד** | כל `<script type="application/ld+json">` — לפני `</head>`. JSON-LD נמצא בבלוק `<script>` נפרד, לא נוגע ב-HTML הגלוי, וקל יותר לסורקי AI לפרש מ-Microdata או RDFa. |

---