# 🚀 راهنمای انتشار نهایی (Deployment Guide) — آکادمی آنلاین

> تاریخ: ۱۴۰۵/۰۵/۱۶ · وضعیت: **Production-Ready** · پشته: Flask 3 + SQLAlchemy + Gunicorn + Nginx + SQLite (قابل ارتقا به PostgreSQL)

---

## ✅ چک‌لیست نهایی انتشار (Final Checklist)

### الف) پیش از انتشار
- [x] `SECRET_KEY` امن (تولید خودکار در deploy.sh)
- [x] همه کلیدهای API در `.env` (نه در کد): درگاه‌ها، SMS، Clarity، Crisp، Groq و Bing؛ پیش‌نمایش نشانی Google Maps به کلید نیاز ندارد
- [x] `FLASK_ENV=production` و `APP_ENV=production` در `.env`
- [x] `SESSION_COOKIE_SECURE=1` (کوکی فقط HTTPS)
- [x] CSRF روی همه فرم‌ها (۳۹+ فرم) + APIهای JSON
- [x] Security Headers: CSP، HSTS، X-Content-Type-Options، X-Frame-Options، Referrer-Policy، Permissions-Policy، COOP
- [x] Rate Limit: API 120/min · لاگین 20/5min · OTP 10/5min (Redis-ready)
- [x] حفاظت از آپلودها (`instance/uploads` خصوصی) + MAX_CONTENT_LENGTH 50MB
- [x] لاگ خطاها در `logs/academy.log` + traceback کامل در خطای 500
- [x] صفحات اختصاصی 404/403/500/400/413/405 (با تم سایت + صفحهساز 404)

### ب) تست‌های نهایی (همه سبز ✅)
- [x] `pytest`: 27 پاس
- [x] `scripts/health_check.py`: 123 تست ALL GOOD
- [x] `scripts/full_route_test.py`: 185 GET + 12 POST ALL GOOD
- [x] Gunicorn واقعی روی `127.0.0.1:8000` — صفحه اصلی/دوره/فیدها سالم
- [x] صفحه اصلی: ۷ سکشن + ۳ اسلاید (بازیابی از نسخه سالم)

### ج) متغیرهای `.env` (نمونه کامل در `.env.example`)
```env
SECRET_KEY=<تولید خودکار>
FLASK_ENV=production
APP_ENV=production
SESSION_COOKIE_SECURE=1
BASE_URL=https://academy.example.com
# درگاه‌ها (zarinpal_merchant, idpay_api_key, ...)
# پیامک (sms_provider, sms_kavenegar_key, sms_kavenegar_sender, sms_kavenegar_template)
# سرویس‌های رایگان (CLARITY_ID, CRISP_WEBSITE_ID, GROQ_API_KEY, BING_API_KEY, BING_KEY_LOCATION)
```

---

## 📁 ساختار نهایی پوشه‌ها

```
/var/www/academy/
├── app.py                  # Factory + میان‌افزار + تم‌ها + RateLimit
├── wsgi.py                 # ✅ WSGI entry point
├── gunicorn.conf.py        # ✅ Gunicorn (3 worker، لاگ هوشمند)
├── models.py / ext_models.py
├── blueprints/             # ✅ معماری ماژولار (MVC)
│   ├── site.py             #   سایت/صفحات/دوره‌ها/وبلاگ
│   ├── auth.py             #   ورود/ثبت‌نام/OTP/2FA
│   ├── shop.py             #   سبد/پرداخت/اقساط
│   ├── builder.py          #   صفحه‌ساز (۸۵+ ویجت)
│   ├── api.py / products.py / features.py / community.py
│   └── teacher.py / seo_admin.py
├── bnpl.py / marketplace.py / engagement.py / integrations.py   # ماژول‌های زیرساخت
├── persian_themes.py / designs.py / gateways.py / sms.py
├── templates/ static/      # قالب‌ها و استاتیک (کش ۷ روزه)
├── instance/
│   ├── academy.db          # دیتابیس (بکاپ‌ها در backups/)
│   └── uploads/            # فایل‌های خصوصی
├── logs/                   # academy.log + access/error گانیکورن
├── deploy/
│   ├── nginx-academy.conf  # ✅ Nginx + SSL + Gzip + Cache
│   ├── academy.service     # ✅ Systemd ۲۴/۷
│   └── deploy.sh           # ✅ اسکریپت استقرار یک‌دست
└── docs/                   # مستندات (معماری، سئو، سرویس‌ها...)
```

---

## 🔧 دستورات اجرا روی سرور واقعی (Ubuntu 22.04/24.04)

### ۱) استقرار خودکار (پیشنهادی)
```bash
# پروژه را به /var/www/academy منتقل کنید
DOMAIN=academy.example.com sudo bash deploy/deploy.sh
```

### ۲) استقرار دستی
```bash
# نصب پیش‌نیازها
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx
# CPython 3.11 و ماژول venv آن را از منبع رسمی سیستم‌عامل/شرکت هاست نصب کنید.
python3.11 --version

# محیط پایتون 3.11
cd /var/www/academy
python3.11 -m venv venv
bash scripts/install_dependencies.sh ./venv/bin/python

# .env
cp .env.example .env
nano .env        # SECRET_KEY + کلیدها

# دیتابیس (اولین بار)
./venv/bin/python seed.py          # فقط دمو — برای شروع خالی: حذف seed

# سرویس
sudo cp deploy/academy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now academy

# Nginx
sudo cp deploy/nginx-academy.conf /etc/nginx/sites-available/academy
sudo ln -s /etc/nginx/sites-available/academy /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# SSL
sudo certbot --nginx -d academy.example.com -d www.academy.example.com
```

### ۳) مدیریت روزانه
```bash
sudo systemctl status academy          # وضعیت
sudo journalctl -u academy -f          # لاگ زنده
sudo systemctl restart academy         # ری‌استارت بعد از تغییر کد
sudo nginx -t && sudo systemctl reload nginx
```

### ۴) بکاپ (کرون پیشنهادی)
```bash
# /etc/cron.d/academy-backup
0 3 * * * root sqlite3 /var/www/academy/instance/academy.db ".backup /var/www/academy/instance/backups/auto-$(date +\%Y\%m\%d).db" && find /var/www/academy/instance/backups -name "auto-*" -mtime +14 -delete
```

---

## 🔌 اتصال‌های واقعی (وضعیت)

| سرویس | وضعیت | کلید در .env |
|---|---|---|
| پرداخت زرین‌پال/آیدی‌پی/زیبال/ملی/سپه/سداد | ✅ متد کامل + Callback صحت‌سنج | `zarinpal_merchant` و... |
| اقساطی اسنپ‌پی/دیجی‌پی/ترب | ✅ متد + لندینگ ۴ قسطی | `snapp_client_id` و... |
| پیامک کاوه‌نگار (OTP) | ✅ متد واقعی + الگوی تایید | `sms_kavenegar_key/sender/template` |
| Microsoft Clarity | ✅ در base.html (فعال با کلید) | `CLARITY_ID` |
| Crisp Chat | ✅ در base.html (فعال با کلید) | `CRISP_WEBSITE_ID` |
| Groq AI (Llama-3) | ✅ API + صفحه ادمین | `GROQ_API_KEY` |
| Bing IndexNow | ✅ خودکار هنگام انتشار مقاله/دوره | `BING_API_KEY` + فایل کلید |
| فید ترب/ایمالز/دیجی‌کالا | ✅ JSON/XML + no-store | — |
| Google Maps / ارسال | ✅ پیش‌نمایش واقعی نشانی + هزینه ثابت/هماهنگی | بدون کلید؛ تنظیم هزینه در پنل |

---

## ⚠️ نکات حیاتی قبل از انتشار واقعی

1. **SECRET_KEY**: هرگز پیش‌فرض نماند (deploy.sh خودکار تولید می‌کند)
2. **HTTPS**: الزامی — `SESSION_COOKIE_SECURE=1` فقط با SSL کار می‌کند
3. **دیتابیس**: SQLite برای شروع کافی است؛ برای مقیاس بالا → PostgreSQL (فقط تغییر `DATABASE_URL` + نصب psycopg)
4. **بکاپ**: کرون بالا را فعال کنید + قبل از هر تغییر مهم بکاپ دستی
5. **سرویس‌های خارجی**: بدون کلید، سایت سالم کار می‌کند (هر سرویس مستقل غیرفعال می‌شود)
6. **تست نهایی**: بعد از استقرار، `scripts/health_check.py` و `full_route_test.py` را روی دامنه واقعی اجرا کنید

## نکته: sitemap.xml پویا
`sitemap.xml` توسط Flask تولید میشود (با Cache-Control یکساعته) — در nginx نباید بهصورت استاتیک سرو شود. کانفیگ `nginx-academy.conf` آن را به Gunicorn پروکسی میکند؛ robots.txt استاتیک است و deploy.sh آن را میسازد.

---

## 🚀 استقرار روی هاست اشتراکی (Phusion Passenger — هاستینگر/سیپنل)

پروژه از قبل فایل **`passenger_wsgi.py`** را در ریشه دارد — نقطه ورود Passenger.

### مراحل:
1. **انتقال پروژه** به هاست (مثلاً `/home/user/domain.com/`)
2. **محیط مجازی** بسازید:
   ```bash
   python3.11 -m venv venv
   bash scripts/install_dependencies.sh ./venv/bin/python
   ```
3. **`.env`** بسازید و `SECRET_KEY` امن بگذارید:
   ```bash
   cp .env.example .env
   python3 -c "import secrets; print(secrets.token_hex(32))"   # خروجی را در .env بگذارید
   ```
4. **`.htaccess`** (نمونه آماده: `deploy/passenger.htaccess`):
   ```
   PassengerAppRoot /home/user/domain.com
   PassengerPython  /home/user/domain.com/venv/bin/python
   PassengerAppEnv  production
   ```
5. **ریاستارت**: `touch passenger_wsgi.py` یا از پنل هاست.

### نکات امنیتی خودکار در passenger_wsgi.py:
- در حالت production اگر `SECRET_KEY` خالی یا پیشفرض باشد → خطای واضح با راهنمای تولید کلید (اجرای اپ با کلید ناامن غیرممکن است)
- محیط مجازی بهصورت خودکار پیدا و استفاده میشود (venv / .venv / env / myenv)
- مسیر کاری به ریشه پروژه ست میشود تا `instance/` و دیتابیس درست کار کنند

---

## ⚙️ متغیرهای محیطی (.env) — مرجع کامل

| متغیر | پیشفرض | توضیح |
|---|---|---|
| `SECRET_KEY` | — | **الزامی در production** — کلید جلسات (تولید: `python3 -c "import secrets; print(secrets.token_hex(32))"`) |
| `FLASK_ENV` / `APP_ENV` | development | `production` = کوکی امن + نیاز به کلید امن |
| `DATABASE_URL` | SQLite محلی | `postgresql://...` یا `mysql+pymysql://...` برای دیتابیس مرکزی |
| `LOG_DIR` | logs | پوشه لاگها |
| `MAX_CONTENT_LENGTH` | ۵۰MB | سقف آپلود (بایت) |
| `REDIS_URL` | (حافظه) | ردیس برای rate limit در چند-پردازنده |
| `SESSION_COOKIE_SECURE` | 0 | در production=1 (کوکی فقط HTTPS) |
| `TRUST_PROXY` | 0 | در پشت nginx=1 (IP واقعی کاربر برای rate limit) |
| `CLARITY_ID` | — | Microsoft Clarity (رایگان) |
| `CRISP_WEBSITE_ID` | — | Crisp Chat (رایگان) |
| `GROQ_API_KEY` | — | Groq AI (رایگان) |
| `BING_API_KEY` | — | Bing IndexNow (رایگان) |
| `BING_KEY_LOCATION` | — | آدرس عمومی فایل کلید IndexNow |

> تنظیمات پرداخت/پیامک/ایمیل/مارکتپلیس **در دیتابیس** ذخیره میشوند و از پنل «⚙️ تنظیمات سوپر» قابل مدیریتاند (نه در .env).

---

## 🗄 اتصال MySQL (هاست اشتراکی) — جایگزین SQLite محلی

اپ به‌صورت خودکار تشخیص می‌دهد: `DATABASE_URL` خالی → SQLite محلی | شروع با `mysql+pymysql://` → MySQL.

### ۱) ساخت دیتابیس در هاست (phpMyAdmin یا پنل)
```
CREATE DATABASE academy CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
کاربر + رمز همان کاربری که پنل هاست می‌دهد.

### ۲) تنظیم .env
```
DATABASE_URL=mysql+pymysql://USER:PASS@localhost/DBNAME?charset=utf8mb4
```
> charset=utf8mb4 به‌صورت خودکار اضافه می‌شود (فارسی + ایموجی) — pool_recycle و pool_pre_ping هم خودکار تنظیم می‌شوند (جلوگیری از قطعی اتصال در هاست).

### ۳) اولین اجرا — ساخت جدول‌ها
اپ هنگام استارت جدول‌ها را خودکار می‌سازد (`db.create_all`).

### ۴) انتقال داده‌های فعلی (SQLite → MySQL)
```
python3 scripts/migrate_sqlite_to_mysql.py
```
- همه ۶۵ جدول + ۸۶۰۰+ ردیف را با ترتیب درست FK منتقل می‌کند
- اجرای مجدد امن است (اول پاک می‌کند)

### ۵) بکاپ در حالت MySQL
پنل ادمین ← بکاپ‌ها: دامپ JSON همه جدول‌ها ساخته می‌شود (`-mysql.json`).
بازیابی خودکار فقط برای SQLite است — برای MySQL از بکاپ پنل هاست/phpMyAdmin استفاده کنید.

### نکات سازگاری (تست‌شده روی MariaDB 11.8)
- ✅ گزارش‌های ادمین (func.date → سازگار شد)
- ✅ سهم استاد/درآمد (Decimal از SUM → int تبدیل شد)
- ✅ چرخ شانس (spin_date طولانی‌تر شد)
- ✅ فیدها، صفحه‌ساز، چت، انجمن — همه تست شدند (191 GET + 12 POST + 123 سلامت)
