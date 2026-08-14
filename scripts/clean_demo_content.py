# -*- coding: utf-8 -*-
"""🧹 پاک‌سازی محتوای نمایشی/جعلی از سایت زنده

چرا این اسکریپت لازم است؟
--------------------------
اصلاح فایل seed.py فقط روی نصب‌های *جدید* اثر دارد. سایتی که همین حالا بالاست،
داده‌های نمایشی را داخل دیتابیس دارد و همچنان نمایش می‌دهد:

  • آمار جعلی: «۵۰,۰۰۰+ دانشجوی فعال» روی سایتی که ۰ دانشجو دارد
  • نظرات جعلی: «بعد از ۴ ماه استخدام شدم» از افرادی که وجود ندارند
  • اطلاعات تماس نمونه: ۰۲۱-۹۱۰۰۱۲۳۴ / info@academy.ir / t.me/academy_ir
  • ادعای «۵ سال سابقه» برای سایت تازه‌تأسیس

از دید Google Safe Browsing این‌ها «محتوای فریب‌دهنده» (Deceptive Content)
هستند — همان دسته‌ای که باعث پیام «Attackers on the site you tried visiting
might trick you into revealing things like your passwords...» می‌شود.

اجرا:
    python scripts/clean_demo_content.py            # فقط گزارش (تغییری نمی‌دهد)
    python scripts/clean_demo_content.py --apply    # اعمال تغییرات
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

APPLY = '--apply' in sys.argv

# مقادیر نمونه‌ای که نباید روی سایت واقعی بمانند
PLACEHOLDER_VALUES = {
    'phone': ('021-91001234', '02191001234', '۰۲۱-۹۱۰۰۱۲۳۴'),
    'email': ('info@academy.ir',),
    'telegram': ('academy_ir',),
    'instagram': ('academy.ir',),
    'whatsapp': ('98910001234', '98'),
    'seo_twitter': ('@academy_ir',),
    'address': ('تهران، خیابان ولیعصر، برج آکادمی، طبقه ۱۲',),
}

FAKE_TESTIMONIAL_NAMES = {'علی محمدی', 'فاطمه احمدی', 'نگار کریمی', 'فاطمه', 'رضا'}
FAKE_STAT_VALUES = {'۱۵۰+', '۵۰,۰۰۰+', '۲,۰۰۰+', '٪۹۸', '150+', '50,000+', '2,000+'}
# نگاشت آمار ثابت → تگ پویا (از دیتابیس پر می‌شود)
STAT_LABEL_TO_TOKEN = {
    'دوره': '{courses}', 'دوره آموزشی': '{courses}',
    'دانشجو': '{students}', 'دانشجوی فعال': '{students}',
    'ساعت': '{hours}', 'ساعت آموزش': '{hours}', 'ساعت آموزش ویدیویی': '{hours}',
    'رضایت': '٪{satisfaction}', 'رضایت دانشجویان': '٪{satisfaction}',
}

changes = []


def clean_settings(db, Setting):
    for key, bad_values in PLACEHOLDER_VALUES.items():
        row = db.session.get(Setting, key)
        if row and (row.value or '').strip() in bad_values:
            changes.append(f'تنظیم «{key}»: «{row.value}» → خالی (اطلاعات تماس نمونه)')
            if APPLY:
                row.value = ''
    # متن درباره ما با ادعای سابقه
    about = db.session.get(Setting, 'about_text')
    if about and 'بیش از ۵ سال سابقه' in (about.value or ''):
        changes.append('متن «درباره ما»: ادعای «۵ سال سابقه» حذف شد')
        if APPLY:
            about.value = ('این آکادمی بستری برای یادگیری مهارت‌های دیجیتال است. '
                           'متن معرفی خود را از پنل مدیریت ویرایش کنید.')


# مقادیر نمونه‌ای که داخل ویجت‌های صفحه‌ساز (هدر/فوتر/تماس) تکرار شده‌اند
WIDGET_PLACEHOLDERS = (
    'info@academy.ir', '021-91001234', '02191001234', '۰۲۱-۹۱۰۰۱۲۳۴',
    'academy_ir', 'academy.ir', '98910001234',
    'تهران، خیابان ولیعصر، برج آکادمی، طبقه ۱۲',
)
# کلیدهایی از data که اگر مقدارشان نمونه باشد باید خالی شوند
CONTACT_KEYS = ('phone', 'email', 'address', 'telegram', 'instagram', 'whatsapp',
                'hours', 'url', 'link')


def clean_widget(w):
    """پاک‌سازی بازگشتی یک ویجت صفحه‌ساز"""
    touched = False
    if not isinstance(w, dict):
        return False
    wtype = w.get('type')
    data = w.get('data')
    if not isinstance(data, dict):
        return False

    # ── اطلاعات تماس نمونه در هر ویجتی (هدر/فوتر/تماس) ──
    for k in CONTACT_KEYS:
        v = data.get(k)
        if isinstance(v, str) and v.strip() in WIDGET_PLACEHOLDERS:
            changes.append(f'ویجت «{wtype}» فیلد «{k}»: «{v}» → خالی (اطلاعات تماس نمونه)')
            if APPLY:
                data[k] = ''
            touched = True

    # ── لینک‌های تماس نمونه داخل repeater ها (topbar/link_list/socials) ──
    for list_key in ('right', 'left', 'links', 'items'):
        lst = data.get(list_key)
        if not isinstance(lst, list):
            continue
        keep = []
        for it in lst:
            if isinstance(it, dict):
                blob = f"{it.get('text', '')} {it.get('url', '')}"
                if any(ph in blob for ph in WIDGET_PLACEHOLDERS):
                    changes.append(f'ویجت «{wtype}»: لینک تماس نمونه '
                                   f'«{str(it.get("text", ""))[:34]}» حذف شد')
                    continue
            keep.append(it)
        if len(keep) != len(lst):
            if APPLY:
                data[list_key] = keep
            touched = True

    # ── ادعای سابقه در متن‌های معرفی ──
    for k in ('text', 'content', 'desc', 'about'):
        v = data.get(k)
        if isinstance(v, str) and 'بیش از ۵ سال سابقه' in v:
            changes.append(f'ویجت «{wtype}»: ادعای «۵ سال سابقه» حذف شد')
            if APPLY:
                data[k] = ('بستری برای یادگیری مهارت‌های دیجیتال — '
                           'این متن را از پنل مدیریت ویرایش کنید.')
            touched = True

    if wtype == 'stats':
        for it in data.get('items') or []:
            if not isinstance(it, dict):
                continue
            val = str(it.get('value') or '').strip()
            if val in FAKE_STAT_VALUES:
                label = str(it.get('label') or '').strip()
                token = STAT_LABEL_TO_TOKEN.get(label, '{courses}')
                changes.append(f'آمار جعلی «{val} {label}» → «{token}» (عدد واقعی از دیتابیس)')
                if APPLY:
                    it['value'] = token
                touched = True

    if wtype == 'testimonials':
        items = data.get('items') or []
        keep = [it for it in items
                if not (isinstance(it, dict) and
                        str(it.get('name') or '').strip() in FAKE_TESTIMONIAL_NAMES)]
        if len(keep) != len(items):
            changes.append(f'{len(items) - len(keep)} نظر جعلی حذف شد '
                           '(نظر ساختگی = محتوای فریب‌دهنده)')
            if APPLY:
                data['items'] = keep
            touched = True

    # ویجت‌های تودرتو
    for col in data.get('cols') or []:
        if isinstance(col, list):
            for inner in col:
                touched = clean_widget(inner) or touched
    return touched


def clean_pages(db, Page):
    for pg in Page.query.all():
        raw = pg.content or ''
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except Exception:
            continue
        # ساختار صفحه یا {"settings": {...}, "rows": [...]} است یا مستقیماً [...]
        if isinstance(parsed, dict):
            rows = parsed.get('rows')
        elif isinstance(parsed, list):
            rows = parsed
        else:
            continue
        if not isinstance(rows, list):
            continue
        touched = False
        for r in rows:
            if not isinstance(r, dict):
                continue
            for col in r.get('cols') or []:
                if isinstance(col, list):
                    for w in col:
                        touched = clean_widget(w) or touched
        if touched:
            changes.append(f'  ↳ صفحه «{pg.slug}» به‌روزرسانی شد')
            if APPLY:
                # ساختار اصلی (dict یا list) باید حفظ شود
                pg.content = json.dumps(parsed, ensure_ascii=False)


def main():
    from app import app
    from models import db, Setting, Page
    with app.app_context():
        clean_settings(db, Setting)
        clean_pages(db, Page)
        if APPLY:
            db.session.commit()

    print('=' * 60)
    print(' 🧹 پاک‌سازی محتوای نمایشی/جعلی')
    print('=' * 60)
    if not changes:
        print('\n✅ محتوای جعلی/نمونه‌ای پیدا نشد — سایت تمیز است.')
        return 0
    for c in changes:
        print(f'  • {c}')
    print()
    if APPLY:
        print(f'✅ {len(changes)} مورد اصلاح و ذخیره شد.')
        print('   حالا کش سایت را پاک و سرور را ری‌استارت کنید.')
    else:
        print(f'⚠️  {len(changes)} مورد پیدا شد (هنوز چیزی تغییر نکرده).')
        print('   برای اعمال: python scripts/clean_demo_content.py --apply')
    return 0


if __name__ == '__main__':
    sys.exit(main())
