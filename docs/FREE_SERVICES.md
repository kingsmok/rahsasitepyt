# 🌐 سرویس‌های رایگان و بدون تحریم — Clarity · Crisp · Groq · Bing

> تاریخ: ۱۴۰۵/۰۵/۱۶ · ماژول: `integrations.py` · همه کلیدها از `.env` خوانده می‌شوند

---

## ۱) Microsoft Clarity — تحلیل رفتار کاربر
- اسکریپت استاندارد در `<head>` قالب `base.html` (فقط با `CLARITY_ID` فعال می‌شود)
- نصب: از [clarity.microsoft.com](https://clarity.microsoft.com) پروژه بسازید و `CLARITY_ID` را در `.env` بگذارید

## ۲) Crisp Chat — پشتیبانی آنلاین
- ویجت Crisp قبل از `</body>` همه صفحات (فقط با `CRISP_WEBSITE_ID` فعال می‌شود)
- نصب: از [app.crisp.chat](https://app.crisp.chat) شناسه وب‌سایت را بردارید

## ۳) Groq AI — نویسنده هوشمند (Llama-3)
- **`POST /api/ai-writer`** — فقط مدیران (403 برای بقیه)
  - ورودی: `{prompt, mode}` — mode: `article` (مقاله سئو) · `answer` (پاسخ سوال) · `seo` (عنوان/متا/کلیدواژه)
  - خروجی: `{ok, text}` — اعتبارسنجی: prompt الزامی (400)، حداکثر ۲۰۰۰ کاراکتر (413)
- **صفحه ادمین**: `/admin/ai-writer` — منوی «🤖 نویسنده هوشمند» — با کپی/دانلود خروجی
- نصب: کلید رایگان از [console.groq.com](https://console.groq.com)

## ۴) Bing Webmaster — ایندکس سریع
- `submit_bing(url)`: مسیر ۱ → IndexNow (`api.indexnow.org`) · مسیر ۲ → Bing URL Submission
- `submit_bing_async(url)`: اجرا در thread (بدون کندکردن سایت)
- **هوک خودکار**: هنگام ذخیره مقاله منتشرشده (`_blog_form`) و دوره منتشرشده (`_course_form`) → URL به Bing ارسال می‌شود
- نصب: کلید IndexNow از [bing.com/webmasters](https://www.bing.com/webmasters) + قراردادن فایل `{key}.txt` در ریشه سایت (و `BING_KEY_LOCATION`)

## متغیرهای `.env`
```env
CLARITY_ID=
CRISP_WEBSITE_ID=
GROQ_API_KEY=
BING_API_KEY=
BING_KEY_LOCATION=
```
> اگر کلیدی خالی باشد، آن سرویس به‌طور خودکار غیرفعال می‌شود (بدون خطا در سایت).

## تست‌ها (سبز)
- بدون کلید: هیچ اسکریپتی در HTML نیست · ai-writer پیام «کلید تنظیم نشده» (502)
- با کلید جعلی: Clarity/Crisp در HTML ظاهر می‌شوند · Groq خطای 401 واقعی را برمی‌گرداند (بدون کرش) · Bing graceful
- دسترسی: anon → 403 · prompt خالی → 400 · طولانی → 413
- pytest 27 · سلامت 123 · مسیریاب 185+12 = ALL GOOD ✅
