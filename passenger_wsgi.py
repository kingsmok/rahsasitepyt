# -*- coding: utf-8 -*-
"""
Phusion Passenger WSGI — نقطه ورود برای هاست‌های اشتراکی
(هاستینگر، سی‌پنل، DirectAdmin، DreamHost و...)

═══════════════════════════════════════════════════════════════
نصب گام‌به‌گام روی هاست:
  1) این فایل در ریشه پروژه (کنار app.py) قرار دارد — تغییری ندهید.
  2) محیط مجازی بسازید:
        python3 -m venv venv
        ./venv/bin/pip install -r requirements.txt
  3) فایل .env بسازید (از روی نمونه):
        cp .env.example .env
     و حتماً SECRET_KEY را عوض کنید:
        python3 -c "import secrets; print(secrets.token_hex(32))"
  4) فایل .htaccess در همین پوشه بسازید (نمونه در deploy/passenger.htaccess):
        PassengerAppRoot /home/USER/پوشه‌پروژه
        PassengerPython /home/USER/پوشه‌پروژه/venv/bin/python
        PassengerAppEnv production
  5) ری‌استارت برنامه:
        touch passenger_wsgi.py        (روش ۱ — ساده)
        یا از پنل هاست ری‌استارت بدهید  (روش ۲)
═══════════════════════════════════════════════════════════════
Passenger به‌طور خودکار متغیر «application» را از این فایل می‌خواند.
"""
import os
import sys

# ── ۱) ریشه پروژه + مسیر کاری درست (مهم برای instance/ و مسیرهای نسبی) ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
try:
    os.chdir(BASE_DIR)
except Exception:
    pass


# ── ۲) پیدا کردن خودکار محیط مجازی ──
# اگر پایتون فعلی (سیستم) flask ندارد، site-packages محیط مجازی را اضافه کن.
def _ensure_venv():
    try:
        import flask  # noqa: F401
        return
    except ImportError:
        pass
    import glob
    for venv in ('venv', '.venv', 'env', 'myenv'):
        for sp in sorted(glob.glob(os.path.join(BASE_DIR, venv, 'lib', 'python*', 'site-packages')), reverse=True):
            if sp not in sys.path:
                sys.path.insert(0, sp)
            try:
                import flask  # noqa: F401
                return
            except ImportError:
                if sp in sys.path:
                    sys.path.remove(sp)


_ensure_venv()

# ── ۳) بارگذاری .env — قبل از import اپلیکیشن ──
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, '.env'), override=False)
except Exception:
    pass

# ── ۴) حالت اجرا: پیش‌فرض production روی هاست ──
os.environ.setdefault('FLASK_ENV', 'production')
os.environ.setdefault('APP_ENV', 'production')

# ── ۵) امنیت SECRET_KEY: قبل از ساخت اپ ──
# حالت‌ها:
#   نصب نشده             → کلید موقت (ویزارد نصب اجرا شود)
#   نصب ناقص (دیتابیس خراب) → کلید موقت (ویزارد تعمیر اجرا شود)
#   نصب کامل و سالم       → کلید امن الزامی است
import secrets  # noqa: E402
from installer import is_installed as _is_installed, check_db_health as _cdh
_sk = os.environ.get('SECRET_KEY', '')
_installed = _is_installed()
_db_ok = True
if _installed:
    try:
        _db_ok, _ = _cdh()
    except Exception:
        _db_ok = False
if (not _installed) or (not _db_ok):
    if not _sk or 'dev-only' in _sk:
        os.environ['SECRET_KEY'] = secrets.token_hex(32)
else:
    if not _sk or 'dev-only' in _sk:
        raise RuntimeError(
            'SECRET_KEY امن تنظیم نشده است! در فایل .env (کنار این فایل) بنویسید:\n'
            f'SECRET_KEY={secrets.token_hex(32)}\n'
            'سپس با «touch passenger_wsgi.py» برنامه را ری‌استارت کنید.'
        )

# ── ۶) ساخت اپلیکیشن ──
# اگر import شکست خورد (پکیج ناقص/پایتون قدیمی)، یک صفحه خطای استندرد (بدون flask)
# با پیام دقیق + دستور نصب نشان می‌دهیم — به‌جای 500 خام هاست.
try:
    from app import app as application  # noqa: E402
except Exception as _boot_err:
    import traceback as _tb
    _boot_tb = _tb.format_exc()

    def _err_page(environ, start_response):
        body = _boot_tb.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')[-4000:]
        html = f"""<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>خطای راه‌اندازی — آکادمی آنلاین</title>
<style>
@font-face{{font-family:'Vazirmatn';src:url('/static/fonts/Vazirmatn-Variable.woff2') format('woff2-variations');font-weight:100 900;}}
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Vazirmatn',Tahoma,sans-serif;background:linear-gradient(160deg,#0f2557,#1d4ed8);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}}
.card{{background:#fff;border-radius:18px;padding:28px;max-width:720px;width:100%;box-shadow:0 30px 80px rgba(2,8,30,.4)}}
h1{{font-size:19px;font-weight:800;color:#b91c1c;margin-bottom:12px}}
p{{font-size:13.5px;color:#334155;line-height:2;margin-bottom:14px}}
code{{background:#f1f5f9;border:1px solid #e2e8f0;border-radius:8px;padding:2px 10px;direction:ltr;display:inline-block;font-size:12.5px;margin:2px 0}}
pre{{background:#0f172a;color:#7dd3fc;border-radius:12px;padding:14px;font-size:11px;direction:ltr;text-align:left;overflow:auto;max-height:220px}}
</style></head><body><div class="card">
<h1>⚠️ برنامه بالا نیامد — دلیل دقیق:</h1>
<p>۱) مطمئن شوید پکیج‌ها نصب شده‌اند (در ترمینال هاست):</p>
<p><code>python3 -m venv venv</code> &nbsp; <code>./venv/bin/pip install -r requirements.txt</code></p>
<p>۲) سپس ری‌استارت: <code>touch passenger_wsgi.py</code></p>
<p>۳) اگر خطا ادامه داشت این بخش را برای پشتیبانی بفرستید:</p>
<pre>{body}</pre>
</div></body></html>"""
        start_response('500 Internal Server Error',
                       [('Content-Type', 'text/html; charset=utf-8')])
        return [html.encode('utf-8')]

    application = _err_page

# نکته: متغیرهای اختیاری که روی هاست می‌توانید ست کنید:
#   DATABASE_URL=sqlite:////home/USER/پوشه/academy.db   (جابه‌جایی دیتابیس)
#   BASE_URL=https://دامنه‌شما.com                     (آدرس پایه برای ایمیل/سئو)
