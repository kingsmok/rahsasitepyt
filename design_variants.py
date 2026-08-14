# -*- coding: utf-8 -*-
"""موتور تولید ۲۰ واریانت UI/UX — ۸ بخش: هدر دسکتاپ/موبایل، فوتر دسکتاپ/موبایل،
کارت دوره، پلیر ویدیو، درباره ما، تماس با ما.

خروجی: HTML راست‌چین با کلاس‌های «dv-*» (شبیه Tailwind با پیشوند اختصاصی تا هیچ
نشتی با base.css نداشته باشد). رنگ‌ها از توکن‌های CSS هر طرح (--primary و...) می‌آیند.
"""
import json
from models import db
from jdates import fa as _fa
from persian_themes import PERSIAN_THEMES


def _hex2rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgba(h, a):
    r, g, b = _hex2rgb(h)
    return f'rgba({r},{g},{b},{a})'


_STATS_CACHE = {'t': 0, 'd': {}}
def _real_stats():
    """آمار واقعی دیتابیس با کش ۳۰ ثانیه — برای درج در HTML واریانت‌ها"""
    import time as _t
    now = _t.time()
    if now - _STATS_CACHE['t'] < 30 and _STATS_CACHE['d']:
        return _STATS_CACHE['d']
    try:
        from models import User as _U, Course as _C, Lesson as _L, Review as _R
        d = dict(
            students=_U.query.filter_by(role='student').count(),
            teachers=_U.query.filter(_U.role.in_(['teacher', 'admin'])).count(),
            courses=_C.query.filter_by(status='published').count(),
            lessons=_L.query.count(),
            hours=int(sum((c.duration_hours or 0) for c in _C.query.all())),
            reviews=_R.query.filter_by(is_approved=True).count(),
        )
        avg = db.query(db.func.avg(_R.rating)).filter(_R.is_approved == True).scalar() or 0
        d['satisfaction'] = round(float(avg) / 5 * 100) if avg else 90
        _STATS_CACHE['d'] = d
        _STATS_CACHE['t'] = now
        return d
    except Exception:
        return dict(students=49, teachers=6, courses=12, lessons=221, hours=359, reviews=48, satisfaction=90)


def _bright(h):
    r, g, b = _hex2rgb(h)
    return (r * 299 + g * 587 + b * 114) / 1000 > 150


def on_primary(t):
    """رنگ متن روی پس‌زمینه primary"""
    return '#0f172a' if _bright(t['colors']['primary']) else '#ffffff'


def accent_on(t):
    return '#0f172a' if _bright(t['colors']['accent']) else '#ffffff'


# =====================================================================
# ۱) هدر دسکتاپ — ۵ واریانت ساختاری
# =====================================================================
def desktop_header(t, idx):
    c = t['colors']
    site = 'آکادمی آنلاین'
    logo = f'''<div class="dv-flex dv-items-center dv-gap-2">
      <div class="dv-logo-ic">{t['name'][0]}</div>
      <div><b class="dv-text-lg dv-font-black" style="color:var(--text)">{site}</b>
      <small class="dv-block dv-text-xs" style="color:var(--primary)">{t['name']}</small></div>
    </div>'''
    search = '''<div class="dv-search">
      <input type="text" placeholder="جستجوی دوره، استاد، مهارت..." class="dv-search-in">
      <button class="dv-search-btn">🔍</button>
    </div>'''
    nav = ('<a href="#">خانه</a><a href="#">دوره‌ها</a><a href="#">اساتید</a>'
           '<a href="#">وبلاگ</a><a href="#">درباره ما</a>')
    cta = '<a class="dv-btn dv-btn-primary" href="#">ورود / ثبت‌نام</a>'
    v = idx % 5

    if v == 0:      # هدر یک‌طبقه مدرن با جستجوی زنده
        return f'''<header class="dv-widget dv-header-glass">
  <div class="dv-container dv-flex dv-items-center dv-justify-between dv-gap-4">
    {logo}
    {search}
    <div class="dv-flex dv-items-center dv-gap-3">{nav.replace('<a ', '<a class="dv-nav-a" ')}{cta}</div>
  </div>
</header>'''
    if v == 1:      # مگامنو دوطبقه با دسته‌بندی دوره‌ها
        return f'''<header class="dv-widget" style="background:var(--card);border-bottom:1px solid var(--border)">
  <div class="dv-container dv-py-2 dv-flex dv-items-center dv-justify-between" style="border-bottom:1px solid var(--border)">
    <div class="dv-flex dv-gap-3" style="color:var(--text-2);font-size:12px">
      <span>📞 ۰۲۱-۱۲۳۴۵۶۷۸</span><span>✉️ info@academy.ir</span>
    </div>
    <div class="dv-flex dv-gap-3" style="color:var(--text-2);font-size:12px">
      <a href="#" style="color:var(--primary)">ورود</a><span>|</span><a href="#">ثبت‌نام</a>
    </div>
  </div>
  <div class="dv-container dv-py-3 dv-flex dv-items-center dv-justify-between dv-gap-4">
    {logo}
    <div class="dv-mega">
      <button class="dv-mega-trigger">☰ همه دسته‌ها</button>
      <div class="dv-mega-panel">
        <div class="dv-mega-col"><b>برنامه‌نویسی</b><a href="#">پایتون</a><a href="#">جنگو</a><a href="#">ری‌اکت</a></div>
        <div class="dv-mega-col"><b>طراحی</b><a href="#">UI/UX</a><a href="#">فتوشاپ</a><a href="#">موشن</a></div>
        <div class="dv-mega-col"><b>بازاریابی</b><a href="#">دیجیتال</a><a href="#">سئو</a><a href="#">تبلیغات</a></div>
      </div>
    </div>
    {search}
    {cta}
  </div>
</header>'''
    if v == 2:      # گلسمورفیسم شیشه‌ای
        return f'''<header class="dv-widget" style="padding:14px 0;background:var(--header-bg);backdrop-filter:blur(16px);border-bottom:1px solid var(--header-border)">
  <div class="dv-container dv-flex dv-items-center dv-justify-between dv-gap-4">
    {logo}
    <nav class="dv-flex dv-gap-1">{nav.replace('<a ', '<a class="dv-nav-pill" ')}</nav>
    <div class="dv-flex dv-items-center dv-gap-3">{search}{cta}</div>
  </div>
</header>'''
    if v == 3:      # منوی خطی سنتی با حاشیه پایین رنگی
        return f'''<header class="dv-widget" style="background:var(--card)">
  <div class="dv-container dv-py-4">
    <div class="dv-flex dv-items-center dv-justify-between">{logo}{cta}</div>
    <nav class="dv-nav-line dv-mt-3">{nav}</nav>
  </div>
</header>'''
    return f'''<header class="dv-widget" style="background:var(--bg-2)">
  <div class="dv-container dv-py-3 dv-flex dv-items-center dv-justify-between dv-gap-4">
    {logo}
    <div class="dv-flex dv-items-center dv-gap-4 dv-flex-1">{search}</div>
    <nav class="dv-flex dv-gap-2">{nav.replace('<a ', '<a class="dv-nav-a" ')}</nav>
    {cta}
  </div>
</header>'''


# =====================================================================
# ۲) منوی موبایل — ۴ واریانت
# =====================================================================
def mobile_header(t, idx):
    c = t['colors']
    site = 'آکادمی آنلاین'
    v = idx % 4
    links = (('<a href="#"><span>🏠</span>خانه</a>'
              '<a href="#"><span>📚</span>دوره‌ها</a>'
              '<a href="#"><span>👨‍🏫</span>اساتید</a>'
              '<a href="#"><span>📝</span>وبلاگ</a>'
              '<a href="#"><span>✉️</span>تماس</a>'))
    if v == 0:      # کشویی از راست + هدر ساده
        return f'''<div class="dv-widget">
  <header class="dv-mb-bar dv-flex dv-items-center dv-justify-between">
    <button class="dv-mb-fab">☰</button>
    <div class="dv-flex dv-items-center dv-gap-2"><span class="dv-logo-ic">{t['name'][0]}</span><b>{site}</b></div>
    <button class="dv-mb-fab">🛒</button>
  </header>
  <nav class="dv-drawer dv-drawer-right">
    <div class="dv-drawer-head"><b>منوی آکادمی</b><button class="dv-mb-fab">✕</button></div>
    {links}
    <a class="dv-btn dv-btn-primary" href="#">ورود / ثبت‌نام</a>
  </nav>
</div>'''
    if v == 1:      # Bottom Navigation اپ‌مانند + کشویی
        return f'''<div class="dv-widget">
  <header class="dv-mb-bar dv-flex dv-items-center dv-justify-between">
    <button class="dv-mb-fab">☰</button>
    <b style="font-size:15px">{site}</b>
    <button class="dv-mb-fab">🔍</button>
  </header>
  <nav class="dv-drawer dv-drawer-right">
    <div class="dv-drawer-head"><b>منو</b><button class="dv-mb-fab">✕</button></div>
    {links}
  </nav>
  <div class="dv-bottom-nav">
    <a href="#" class="dv-bn-item dv-bn-active"><span>🏠</span><small>خانه</small></a>
    <a href="#" class="dv-bn-item"><span>📚</span><small>دوره‌ها</small></a>
    <a href="#" class="dv-bn-item"><span>🔍</span><small>جستجو</small></a>
    <a href="#" class="dv-bn-item"><span>👤</span><small>پروفایل</small></a>
  </div>
</div>'''
    if v == 2:      # آکاردئونی با دسته‌بندی
        return f'''<div class="dv-widget">
  <header class="dv-mb-bar dv-flex dv-items-center dv-justify-between">
    <button class="dv-mb-fab">☰</button><b>{site}</b><button class="dv-mb-fab">⚙️</button>
  </header>
  <nav class="dv-drawer dv-drawer-right">
    <div class="dv-drawer-head"><b>دسترسی سریع</b><button class="dv-mb-fab">✕</button></div>
    <details class="dv-acc"><summary>📚 دوره‌ها</summary>
      <a href="#">پایتون</a><a href="#">جنگو</a><a href="#">ری‌اکت</a><a href="#">طراحی</a></details>
    <details class="dv-acc"><summary>👨‍🏫 اساتید</summary><a href="#">همه اساتید</a></details>
    <details class="dv-acc"><summary>📝 وبلاگ</summary><a href="#">جدیدترین مقالات</a></details>
    {links.replace('<a href="#">', '<a href="#">').replace('<span>🏠</span>','').replace('<span>📚</span>','').replace('<span>👨‍🏫</span>','').replace('<span>📝</span>','').replace('<span>✉️</span>','')}
  </nav>
</div>'''
    return f'''<div class="dv-widget">
  <header class="dv-mb-bar dv-flex dv-items-center dv-justify-between">
    <button class="dv-mb-fab">☰</button><b>{site}</b><button class="dv-mb-fab">👤</button>
  </header>
  <nav class="dv-drawer dv-drawer-right dv-drawer-glass">
    <div class="dv-drawer-head"><b>خوش آمدید</b><button class="dv-mb-fab">✕</button></div>
    <a class="dv-btn dv-btn-primary" href="#">ورود</a>
    {links}
  </nav>
</div>'''


# =====================================================================
# ۳) فوتر دسکتاپ — ۵ واریانت
# =====================================================================
def desktop_footer(t, idx):
    c = t['colors']
    v = idx % 5
    socials = '<a href="#">✈️</a><a href="#">📷</a><a href="#">💬</a><a href="#">🐦</a>'
    if v == 0:      # چندستونه کامل با خبرنامه و نماد اعتماد
        return f'''<footer class="dv-widget dv-footer" style="background:var(--footer-bg);color:var(--footer-text)">
  <div class="dv-container dv-footer-grid">
    <div>
      <div class="dv-flex dv-items-center dv-gap-2"><span class="dv-logo-ic">{t['name'][0]}</span><b style="color:var(--footer-head)">{t['name']}</b></div>
      <p class="dv-text-sm" style="color:var(--footer-text-2)">مرجع تخصصی آموزش آنلاین با هویت ایرانی — {t['category']}</p>
      <div class="dv-socials">{socials}</div>
    </div>
    <div><b style="color:var(--footer-head)">دسترسی سریع</b>
      <a href="#">خانه</a><a href="#">دوره‌ها</a><a href="#">اساتید</a><a href="#">وبلاگ</a></div>
    <div><b style="color:var(--footer-head)">پشتیبانی</b>
      <a href="#">سوالات متداول</a><a href="#">تماس با ما</a><a href="#">قوانین</a><a href="#">حریم خصوصی</a></div>
    <div><b style="color:var(--footer-head)">خبرنامه</b>
      <p class="dv-text-sm" style="color:var(--footer-text-2)">تخفیف‌ها و مطالب جدید را از دست ندهید</p>
      <div class="dv-news"><input placeholder="ایمیل شما"><button class="dv-btn dv-btn-accent">عضویت</button></div>
      <div class="dv-trust"><span>🛡 ای‌نماد</span><span>🔒 پرداخت امن</span><span>✅ نماد ساماندهی</span></div>
    </div>
  </div>
  <div class="dv-footer-bottom"><span>© ۱۴۰۵ {t['name']} — تمامی حقوق محفوظ است</span></div>
</footer>'''
    if v == 1:      # مینیمال یک‌خطی
        return f'''<footer class="dv-widget" style="background:var(--footer-bg);color:var(--footer-text);padding:22px 0">
  <div class="dv-container dv-flex dv-items-center dv-justify-between dv-gap-3 dv-flex-wrap">
    <div class="dv-flex dv-items-center dv-gap-2"><span class="dv-logo-ic">{t['name'][0]}</span><b style="color:var(--footer-head)">{t['name']}</b></div>
    <div class="dv-flex dv-gap-3" style="font-size:13px"><a href="#">درباره</a><a href="#">تماس</a><a href="#">قوانین</a></div>
    <span style="font-size:12px;color:var(--footer-text-2)">© ۱۴۰۵ — {t['name']}</span>
  </div>
</footer>'''
    if v == 2:      # با نوار بالای رنگی و کاشی‌کاری سنتی
        return f'''<footer class="dv-widget" style="background:var(--footer-bg);color:var(--footer-text)">
  <div style="height:6px;background:linear-gradient(90deg,{c['primary']},{c['accent']},{c['secondary']})"></div>
  <div class="dv-container dv-footer-grid">
    <div>
      <span class="dv-logo-ic">{t['name'][0]}</span>
      <p class="dv-text-sm" style="color:var(--footer-text-2)">یادگیری با طعم فرهنگ ایرانی — {t['category']}</p>
      <div class="dv-socials">{socials}</div>
    </div>
    <div><b style="color:var(--footer-head)">دوره‌ها</b><a href="#">پایتون</a><a href="#">طراحی</a><a href="#">بازاریابی</a><a href="#">همه دوره‌ها</a></div>
    <div><b style="color:var(--footer-head)">آکادمی</b><a href="#">داستان ما</a><a href="#">اساتید</a><a href="#">افتخارات</a><a href="#">همکاری</a></div>
    <div><b style="color:var(--footer-head)">تماس</b>
      <p class="dv-text-sm" style="color:var(--footer-text-2)">تهران، خیابان آزادی<br>۰۲۱-۱۲۳۴۵۶۷۸<br>info@academy.ir</p></div>
  </div>
  <div class="dv-footer-bottom"><span>© ۱۴۰۵ — {t['name']}</span></div>
</footer>'''
    if v == 3:      # با فرم مشاوره + آمار
        return f'''<footer class="dv-widget" style="background:var(--footer-bg);color:var(--footer-text)">
  <div class="dv-container dv-footer-grid">
    <div>
      <span class="dv-logo-ic">{t['name'][0]}</span>
      <div class="dv-stats" style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px">
        <div><b style="color:var(--footer-head)">{_fa(_real_stats()['courses'])}+</b><small>دوره</small></div>
        <div><b style="color:var(--footer-head)">{_fa(_real_stats()['students'])}+</b><small>دانشجو</small></div>
        <div><b style="color:var(--footer-head)">٪{_fa(_real_stats()['satisfaction'])}</b><small>رضایت</small></div>
      </div>
    </div>
    <div><b style="color:var(--footer-head)">لینک‌ها</b><a href="#">خانه</a><a href="#">دوره‌ها</a><a href="#">وبلاگ</a><a href="#">سوالات</a></div>
    <div><b style="color:var(--footer-head)">مشاوره رایگان</b>
      <p class="dv-text-sm" style="color:var(--footer-text-2)">شماره خود را بگذارید تا تماس بگیریم</p>
      <div class="dv-news"><input placeholder="شماره موبایل"><button class="dv-btn dv-btn-accent">درخواست</button></div>
      <div class="dv-socials">{socials}</div></div>
  </div>
</footer>'''
    return f'''<footer class="dv-widget" style="background:var(--card);border-top:3px solid {c['primary']};color:var(--text)">
  <div class="dv-container dv-footer-grid">
    <div><span class="dv-logo-ic">{t['name'][0]}</span><p class="dv-text-sm" style="color:var(--text-2)">{t['desc'][:70]}</p></div>
    <div><b>آموزش</b><a href="#" style="color:var(--text-2)">دوره‌ها</a><a href="#" style="color:var(--text-2)">مسیر یادگیری</a><a href="#" style="color:var(--text-2)">آزمون‌ها</a></div>
    <div><b>شرکت</b><a href="#" style="color:var(--text-2)">درباره</a><a href="#" style="color:var(--text-2)">تماس</a><a href="#" style="color:var(--text-2)">قوانین</a></div>
    <div><b>شبکه‌ها</b><div class="dv-socials">{socials}</div></div>
  </div>
  <div class="dv-footer-bottom" style="color:var(--text-3)"><span>© ۱۴۰۵ {t['name']}</span></div>
</footer>'''


# =====================================================================
# ۴) فوتر موبایل — ۴ واریانت (جمع‌وجور + منوی چسبان)
# =====================================================================
def mobile_footer(t, idx):
    v = idx % 4
    c = t['colors']
    if v == 0:      # جمع‌وجور با لینک‌های سریع
        return f'''<footer class="dv-widget" style="background:var(--footer-bg);color:var(--footer-text);padding:18px 16px;text-align:center">
  <span class="dv-logo-ic" style="margin:0 auto 8px">{t['name'][0]}</span>
  <b style="color:var(--footer-head)">{t['name']}</b>
  <p class="dv-text-sm" style="color:var(--footer-text-2);margin:6px 0 12px">مرجع آموزش آنلاین ایرانی</p>
  <div class="dv-flex dv-justify-center dv-gap-2 dv-flex-wrap" style="font-size:12px">
    <a href="#" style="color:var(--footer-text)">دوره‌ها</a><a href="#" style="color:var(--footer-text)">اساتید</a>
    <a href="#" style="color:var(--footer-text)">تماس</a><a href="#" style="color:var(--footer-text)">قوانین</a>
  </div>
  <div class="dv-footer-bottom" style="font-size:11px;color:var(--footer-text-2);margin-top:12px">© ۱۴۰۵ {t['name']}</div>
</footer>'''
    if v == 1:      # با منوی چسبان پایین (ثبت‌نام/پشتیبانی)
        return f'''<div class="dv-widget">
  <footer style="background:var(--footer-bg);color:var(--footer-text);padding:16px;text-align:center">
    <b style="color:var(--footer-head)">{t['name']}</b>
    <p class="dv-text-sm" style="color:var(--footer-text-2);margin:6px 0 10px">یادگیری مهارت‌های آینده</p>
  </footer>
  <div class="dv-sticky-cta">
    <a class="dv-btn dv-btn-primary" href="#" style="flex:1">✨ ثبت‌نام رایگان</a>
    <a class="dv-btn dv-btn-accent" href="#" style="flex:1">💬 پشتیبانی</a>
  </div>
</div>'''
    if v == 2:      # آکاردئون دسته‌ها
        return f'''<footer class="dv-widget" style="background:var(--footer-bg);color:var(--footer-text);padding:16px">
  <div class="dv-flex dv-items-center dv-gap-2"><span class="dv-logo-ic">{t['name'][0]}</span><b style="color:var(--footer-head)">{t['name']}</b></div>
  <details class="dv-acc" style="margin-top:10px"><summary>📚 دسته‌بندی دوره‌ها</summary>
    <a href="#">برنامه‌نویسی</a><a href="#">طراحی</a><a href="#">بازاریابی</a></details>
  <details class="dv-acc"><summary>🔗 لینک‌های مفید</summary>
    <a href="#">درباره ما</a><a href="#">تماس</a><a href="#">قوانین</a></details>
  <div class="dv-socials dv-justify-center" style="margin-top:10px"><a href="#">✈️</a><a href="#">📷</a><a href="#">💬</a></div>
  <div style="font-size:11px;color:var(--footer-text-2);text-align:center;margin-top:10px">© ۱۴۰۵ {t['name']}</div>
</footer>'''
    return f'''<div class="dv-widget">
  <footer style="background:var(--card);border-top:1px solid var(--border);padding:14px 16px">
    <div class="dv-flex dv-items-center dv-justify-between">
      <b style="font-size:14px">{t['name']}</b>
      <div class="dv-flex dv-gap-2" style="font-size:16px"><a href="#">✈️</a><a href="#">📷</a><a href="#">💬</a></div>
    </div>
    <div class="dv-news dv-mt-2"><input placeholder="ایمیل برای تخفیف‌ها"><button class="dv-btn dv-btn-accent">عضویت</button></div>
    <div style="font-size:11px;color:var(--text-3);text-align:center;margin-top:10px">© ۱۴۰۵ {t['name']}</div>
  </footer>
</div>'''


# =====================================================================
# ۵) کارت دوره — ۵ واریانت (تخفیف/افقی/عمودی/پیش‌فروش/ویدیو)
# =====================================================================
def course_card(t, idx):
    v = idx % 5
    c = t['colors']
    title = 'دوره جامع {0}'.format(['برنامه‌نویسی پایتون', 'طراحی UI/UX', 'بازاریابی دیجیتال',
                                    'یادگیری ماشین', 'توسعه وب با Flask'][idx % 5])
    price = '۸۹۰,۰۰۰'
    old = '۱,۸۵۰,۰۰۰'
    if v == 0:      # عمودی با تخفیف و هاور
        return f'''<div class="dv-widget">
  <article class="dv-card dv-card-course">
    <div class="dv-card-thumb" style="background:linear-gradient(135deg,{c['primary']},{c['accent']})">
      <span class="dv-badge dv-badge-discount">٪۵۲ تخفیف</span>
      <span style="font-size:40px">🎓</span>
    </div>
    <div class="dv-card-body">
      <small style="color:var(--primary)">برنامه‌نویسی</small>
      <h3 class="dv-text-base dv-font-black">{title}</h3>
      <div class="dv-flex dv-gap-2" style="font-size:12px;color:var(--text-3)">
        <span>⏱ ۴۲ ساعت</span><span>👥 ۱۸۴۱ دانشجو</span><span>⭐ ۴.۹</span>
      </div>
      <div class="dv-flex dv-items-center dv-justify-between dv-mt-2">
        <div><s style="color:var(--text-3);font-size:12px">{old} تومان</s>
          <b style="color:var(--primary);font-size:16px;display:block">{price} تومان</b></div>
        <a class="dv-btn dv-btn-primary" href="#">خرید</a>
      </div>
    </div>
  </article>
</div>'''
    if v == 1:      # افقی
        return f'''<div class="dv-widget">
  <article class="dv-card dv-flex" style="max-width:520px">
    <div style="width:150px;background:linear-gradient(160deg,{c['secondary']},{c['primary']});display:flex;align-items:center;justify-content:center;font-size:38px">📚</div>
    <div class="dv-flex-1" style="padding:14px 16px">
      <small style="color:var(--primary);font-weight:700">{t['category']}</small>
      <h3 class="dv-text-sm dv-font-black" style="margin:4px 0 6px">{title}</h3>
      <div style="font-size:12px;color:var(--text-3)">⭐ ۴.۹ · 👥 ۱۸۴۱ · ⏱ ۴۲س</div>
      <div class="dv-flex dv-items-center dv-justify-between dv-mt-2">
        <b style="color:var(--primary)">{price} <small>تومان</small></b>
        <a class="dv-btn dv-btn-outline" href="#">جزئیات</a>
      </div>
    </div>
  </article>
</div>'''
    if v == 2:      # پیش‌فروش با تایمر
        return f'''<div class="dv-widget">
  <article class="dv-card dv-card-course" style="border:2px dashed {c['accent']}">
    <div class="dv-card-thumb" style="background:linear-gradient(135deg,{c['accent']},{c['primary']})">
      <span class="dv-badge" style="background:#fff;color:{c['accent']}">⚡ پیش‌فروش</span><span style="font-size:38px">🚀</span>
    </div>
    <div class="dv-card-body">
      <h3 class="dv-text-base dv-font-black">{title} — ترم جدید</h3>
      <div class="dv-countdown dv-flex dv-gap-1 dv-justify-center" style="margin:10px 0">
        <span class="dv-cd"><b>۰۷</b><small>روز</small></span>
        <span class="dv-cd"><b>۱۴</b><small>ساعت</small></span>
        <span class="dv-cd"><b>۳۲</b><small>دقیقه</small></span>
      </div>
      <div class="dv-flex dv-items-center dv-justify-between">
        <b style="color:var(--primary)">{price} <small>تومان</small></b>
        <a class="dv-btn dv-btn-accent" href="#">رزرو پیش‌فروش</a>
      </div>
    </div>
  </article>
</div>'''
    if v == 3:      # با ویدیوی پیش‌نمایش
        return f'''<div class="dv-widget">
  <article class="dv-card dv-card-course">
    <div class="dv-card-thumb" style="background:#000;position:relative">
      <span style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:42px;color:#fff;opacity:.9">▶</span>
      <span class="dv-badge" style="background:var(--danger);color:#fff">پیش‌نمایش</span>
    </div>
    <div class="dv-card-body">
      <small style="color:var(--primary)">ویدیو معرفی</small>
      <h3 class="dv-text-base dv-font-black">{title}</h3>
      <div class="dv-flex dv-gap-2" style="font-size:12px;color:var(--text-3)"><span>🎬 ۲۷ جلسه</span><span>🏅 گواهینامه</span></div>
      <div class="dv-flex dv-items-center dv-justify-between dv-mt-2">
        <b style="color:var(--primary)">{price} <small>تومان</small></b>
        <a class="dv-btn dv-btn-primary" href="#">مشاهده دوره</a>
      </div>
    </div>
  </article>
</div>'''
    return f'''<div class="dv-widget">
  <article class="dv-card dv-card-course" style="text-align:center">
    <div style="height:90px;background:radial-gradient(circle at 30% 30%,{c['accent']},transparent 60%),linear-gradient(135deg,{c['primary']},{c['secondary']});display:flex;align-items:center;justify-content:center;font-size:40px">🏆</div>
    <div class="dv-card-body" style="text-align:center">
      <span class="dv-badge" style="background:var(--accent-soft);color:var(--accent)">ویژه</span>
      <h3 class="dv-text-base dv-font-black" style="margin-top:6px">{title}</h3>
      <div class="dv-flex dv-justify-center dv-gap-2" style="font-size:12px;color:var(--text-3);margin:6px 0">
        <span>⭐ ۵.۰</span><span>👥 ۳۲۰۰</span><span>🕰 مادام‌العمر</span>
      </div>
      <a class="dv-btn dv-btn-primary dv-w-full" href="#">شروع یادگیری</a>
      <small style="display:block;color:var(--text-3);margin-top:8px">ضمانت بازگشت وجه ۷ روزه</small>
    </div>
  </article>
</div>'''


# =====================================================================
# ۶) پلیر ویدیو — ۴ واریانت (پلیر + پلی‌لیست راست/چپ + یادداشت + دانلود)
# =====================================================================
def video_section(t, idx):
    v = idx % 4
    c = t['colors']
    playlist = ''.join(
        f'<div class="dv-pl-item {"dv-pl-active" if i == 0 else ""}"><span class="dv-pl-num">{i + 1}</span>'
        f'<div><b>قسمت {i + 1} — عنوان درس</b><small>⏱ ۱۲:۳۴</small></div></div>'
        for i in range(4))
    player = f'''<div class="dv-player">
      <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:56px;color:#fff">▶</div>
      <div class="dv-player-bar"><span>قسمت ۱ — {t['name']}</span><span style="font-size:12px">⏱ ۱۲:۳۴ / ۴۵:۰۰</span></div>
    </div>'''
    notes = '''<div class="dv-notes"><b>📝 یادداشت‌های من</b>
      <textarea rows="3" placeholder="نکته‌های این جلسه را بنویسید..."></textarea>
      <button class="dv-btn dv-btn-primary dv-w-full">ذخیره یادداشت</button></div>'''
    attach = '''<div class="dv-attach"><b>📎 فایل‌های ضمیمه</b>
      <a href="#">📄 اسلاید جلسه.pdf</a><a href="#">📦 کد تمرین.zip</a><a href="#">📊 دیتاست.xlsx</a></div>'''
    if v == 0:      # پلی‌لیست سمت راست
        return f'''<div class="dv-widget dv-flex dv-gap-3" style="flex-direction:row-reverse">
  <div style="flex:2">{player}</div>
  <div style="flex:1;min-width:200px"><b style="font-size:14px">🎬 لیست پخش — {t['name']}</b>{playlist}</div>
</div>'''
    if v == 1:      # پلی‌لیست سمت چپ + یادداشت
        return f'''<div class="dv-widget">
  <div class="dv-flex dv-gap-3" style="flex-direction:row">
    <div style="flex:1;min-width:200px"><b style="font-size:14px">🎬 لیست پخش</b>{playlist}{attach}</div>
    <div style="flex:2">{player}{notes}</div>
  </div>
</div>'''
    if v == 2:      # پلیر بالا + دو ستون پایین (یادداشت + دانلود)
        return f'''<div class="dv-widget">
  {player}
  <div class="dv-flex dv-gap-3" style="margin-top:12px;flex-wrap:wrap">
    <div style="flex:1;min-width:220px">{notes}</div>
    <div style="flex:1;min-width:220px">{attach}</div>
    <div style="flex:1;min-width:220px"><b>🎬 لیست پخش</b>{playlist}</div>
  </div>
</div>'''
    return f'''<div class="dv-widget">
  <div class="dv-flex dv-gap-3" style="flex-wrap:wrap">
    <div style="flex:2;min-width:260px">{player}
      <div class="dv-flex dv-gap-2" style="margin-top:10px">
        <button class="dv-btn dv-btn-primary" style="flex:1">⬇ دانلود ویدیو</button>
        <button class="dv-btn dv-btn-outline" style="flex:1">📝 یادداشت</button>
      </div></div>
    <div style="flex:1;min-width:220px"><b>🎬 لیست پخش — {t['name']}</b>{playlist}</div>
  </div>
</div>'''


# =====================================================================
# ۷) درباره ما و اساتید — ۴ واریانت
# =====================================================================
def about_section(t, idx):
    v = idx % 4
    c = t['colors']
    tcolors = [c['primary'], c['accent'], c['secondary']]
    teachers = ''.join(
        f'''<div class="dv-tcard"><span class="dv-tavatar" style="background:{tcolors[i % 3]}">{['د','ع','ن','ا'][i]}</span>
        <b>استاد {['دکتر سارا محمدی', 'مهندس علی رضایی', 'دکتر نگار کریمی', 'مهندس امیر حسینی'][i]}</b>
        <small>{['مدرس ارشد برنامه‌نویسی', 'متخصص طراحی UI/UX', 'دکترای هوش مصنوعی', 'مدرس بازاریابی دیجیتال'][i]}</small>
        <span style="color:var(--accent);font-size:12px">★★★★★</span></div>'''
        for i in range(4))
    _rs = _real_stats()
    stats = (f'<div class="dv-stat"><b>{_fa(_rs["courses"])}+</b><small>دوره آموزشی</small></div>'
             f'<div class="dv-stat"><b>{_fa(_rs["students"])}+</b><small>دانشجوی فعال</small></div>'
             f'<div class="dv-stat"><b>{_fa(_rs["hours"])}+</b><small>ساعت آموزش</small></div>'
             f'<div class="dv-stat"><b>٪{_fa(_rs["satisfaction"])}</b><small>رضایت</small></div>')
    if v == 0:      # داستان + آمار + تیم
        return f'''<div class="dv-widget" style="text-align:center">
  <span class="dv-badge" style="background:var(--primary-soft);color:var(--primary)">داستان ما</span>
  <h2 class="dv-text-2xl dv-font-black" style="margin:10px 0">سفری از دل فرهنگ تا دنیای دیجیتال</h2>
  <p class="dv-text-sm" style="color:var(--text-2);max-width:560px;margin:0 auto 22px">
    {t['name']} با باور به آموزش باکیفیت و هویت ایرانی متولد شد؛ از {t['category']} تا مهارت‌های روز.</p>
  <div class="dv-stats dv-flex dv-gap-2 dv-justify-center dv-flex-wrap" style="margin-bottom:26px">{stats}</div>
  <div class="dv-flex dv-gap-3 dv-flex-wrap" style="justify-content:center">{teachers}</div>
</div>'''
    if v == 1:      # ارزش‌ها + افتخارات
        return f'''<div class="dv-widget">
  <div class="dv-flex dv-gap-3" style="flex-wrap:wrap">
    <div style="flex:1;min-width:240px;background:var(--card);border-radius:16px;padding:20px;border-top:4px solid {c['primary']}">
      <b>🎯 مأموریت ما</b><p class="dv-text-sm" style="color:var(--text-2);margin-top:6px">آموزش مهارت‌های واقعی به زبان ساده برای همه ایرانیان.</p></div>
    <div style="flex:1;min-width:240px;background:var(--card);border-radius:16px;padding:20px;border-top:4px solid {c['accent']}">
      <b>👁 چشم‌انداز</b><p class="dv-text-sm" style="color:var(--text-2);margin-top:6px">مرجع اول آموزش آنلاین با هویت ایرانی در منطقه.</p></div>
    <div style="flex:1;min-width:240px;background:var(--card);border-radius:16px;padding:20px;border-top:4px solid {c['secondary']}">
      <b>🏆 افتخارات</b><p class="dv-text-sm" style="color:var(--text-2);margin-top:6px">۶ سال حضور مستمر، ۵۰ هزار دانشجو، ۲۰۰ دوره موفق.</p></div>
  </div>
  <div class="dv-flex dv-gap-3" style="margin-top:20px;flex-wrap:wrap">
    <div style="flex:2;min-width:240px"><b style="font-size:15px">اساتید برتر</b>{teachers}</div>
    <div style="flex:1;min-width:200px"><b style="font-size:15px">آمار کلیدی</b>{stats}</div>
  </div>
</div>'''
    if v == 2:      # سنتی با قاب کاشی
        return f'''<div class="dv-widget" style="text-align:center;border:1px solid {_rgba(c['primary'], .25)};border-radius:22px;padding:28px;position:relative;overflow:hidden">
  <div style="position:absolute;top:-40px;right:-40px;width:120px;height:120px;border-radius:50%;background:{_rgba(c['accent'], .15)}"></div>
  <span class="dv-badge" style="background:{c['accent']};color:#fff">هنر و اصالت</span>
  <h2 class="dv-text-2xl dv-font-black" style="margin:12px 0">{t['name']}</h2>
  <p class="dv-text-sm" style="color:var(--text-2);max-width:540px;margin:0 auto 20px">
    برگرفته از {t['category']} — تلاش می‌کنیم دانش را با همان ظرافت هنر ایرانی منتقل کنیم.</p>
  <div class="dv-flex dv-gap-2 dv-justify-center dv-flex-wrap" style="margin-bottom:22px">{stats}</div>
  <div class="dv-flex dv-gap-3 dv-flex-wrap" style="justify-content:center">{teachers}</div>
</div>'''
    return f'''<div class="dv-widget">
  <div class="dv-flex dv-gap-3" style="align-items:center;flex-wrap:wrap">
    <div style="flex:1;min-width:230px;height:160px;border-radius:18px;background:linear-gradient(135deg,{c['primary']},{c['secondary']});display:flex;align-items:center;justify-content:center;font-size:56px">🏛</div>
    <div style="flex:1.4;min-width:250px">
      <h2 class="dv-text-xl dv-font-black">درباره {t['name']}</h2>
      <p class="dv-text-sm" style="color:var(--text-2);margin:8px 0 14px">
        {t['desc']} — با تیمی از متخصصان و هنرمندان ایرانی.</p>
      <div class="dv-flex dv-gap-2">{stats}</div>
    </div>
  </div>
  <div class="dv-flex dv-gap-3" style="margin-top:20px;flex-wrap:wrap">{teachers}</div>
</div>'''


# =====================================================================
# ۸) تماس با ما — ۴ واریانت
# =====================================================================
def contact_section(t, idx):
    v = idx % 4
    c = t['colors']
    form = '''<form class="dv-contact-form" onsubmit="return false">
      <div class="dv-flex dv-gap-2"><input placeholder="نام و نام خانوادگی"><input placeholder="شماره موبایل"></div>
      <input placeholder="موضوع پیام">
      <textarea rows="4" placeholder="متن پیام شما..."></textarea>
      <button class="dv-btn dv-btn-primary dv-w-full">📨 ارسال پیام</button>
    </form>'''
    cards = ('<div class="dv-cinfo"><span>🏢</span><div><b>آدرس</b><small>تهران، خیابان آزادی، پلاک ۱۲۳</small></div></div>'
             '<div class="dv-cinfo"><span>📞</span><div><b>تلفن</b><small>۰۲۱-۱۲۳۴۵۶۷۸</small></div></div>'
             '<div class="dv-cinfo"><span>✉️</span><div><b>ایمیل</b><small>info@academy.ir</small></div></div>'
             '<div class="dv-cinfo"><span>🕰</span><div><b>ساعات پاسخگویی</b><small>شنبه تا پنجشنبه ۹ تا ۱۸</small></div></div>')
    if v == 0:      # فرم + اطلاعات + نقشه
        return f'''<div class="dv-widget dv-flex dv-gap-4" style="flex-wrap:wrap">
  <div style="flex:1.2;min-width:260px;background:var(--card);border-radius:18px;padding:22px;border:1px solid var(--border)">
    <b style="font-size:16px">📨 فرم تماس</b>{form}</div>
  <div style="flex:1;min-width:240px;display:flex;flex-direction:column;gap:10px">{cards}
    <div style="flex:1;min-height:130px;border-radius:14px;background:linear-gradient(135deg,{c['primary']},{c['secondary']});display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700">🗺 نقشه</div>
  </div>
</div>'''
    if v == 1:      # مشاوره رایگان
        return f'''<div class="dv-widget" style="background:linear-gradient(135deg,{c['primary']},{_rgba(c['primary'], .75)});border-radius:22px;padding:30px;color:#fff;display:flex;gap:24px;flex-wrap:wrap">
  <div style="flex:1;min-width:230px">
    <h2 class="dv-text-xl dv-font-black" style="color:#fff">🎯 مشاوره رایگان انتخاب مسیر</h2>
    <p style="opacity:.9;font-size:13px;margin:8px 0 16px">کارشناسان ما در کمتر از ۲۴ ساعت با شما تماس می‌گیرند.</p>
    <div style="display:flex;flex-direction:column;gap:8px;font-size:13px">
      <span>📞 ۰۲۱-۱۲۳۴۵۶۷۸</span><span>✉️ info@academy.ir</span><span>💬 تلگرام: @academy_ir</span>
    </div>
  </div>
  <div style="flex:1;min-width:240px">
    <form class="dv-contact-form" onsubmit="return false" style="background:#fff;border-radius:16px;padding:18px;color:var(--text)">
      <b style="color:var(--text)">فرم درخواست مشاوره</b>
      <input placeholder="نام"><input placeholder="شماره موبایل">
      <select><option>دوره برنامه‌نویسی</option><option>دوره طراحی</option><option>دوره بازاریابی</option></select>
      <button class="dv-btn dv-btn-accent dv-w-full">درخواست مشاوره</button>
    </form>
  </div>
</div>'''
    if v == 2:      # کارت‌های ارتباطی + شبکه‌ها
        return f'''<div class="dv-widget" style="text-align:center">
  <h2 class="dv-text-xl dv-font-black">راه‌های ارتباط با {t['name']}</h2>
  <p class="dv-text-sm" style="color:var(--text-2);margin:6px 0 20px">همیشه در کنار شما هستیم</p>
  <div class="dv-flex dv-gap-3 dv-flex-wrap" style="justify-content:center">{cards}</div>
  <div class="dv-socials" style="justify-content:center;margin-top:18px"><a href="#">✈️</a><a href="#">📷</a><a href="#">💬</a><a href="#">🐦</a></div>
  <div style="max-width:520px;margin:18px auto 0">{form}</div>
</div>'''
    return f'''<div class="dv-widget dv-flex dv-gap-4" style="flex-wrap:wrap;align-items:stretch">
  <div style="flex:1;min-width:220px;border-radius:18px;overflow:hidden;display:flex;flex-direction:column">
    <div style="flex:1;min-height:200px;background:linear-gradient(160deg,{c['secondary']},{c['primary']});display:flex;align-items:center;justify-content:center;font-size:54px">📍</div>
  </div>
  <div style="flex:1.2;min-width:260px;background:var(--card);border-radius:18px;padding:22px;border:1px solid var(--border)">
    <b style="font-size:16px">ارتباط با ما</b>
    <div style="display:flex;flex-direction:column;gap:10px;margin:12px 0">{cards}</div>
    {form}
  </div>
</div>'''


# =====================================================================
# تابع اصلی — تولید ۸ کامپوننت برای یک طرح
# =====================================================================
COMPONENT_KEYS = ['desktop_header', 'mobile_header', 'desktop_footer', 'mobile_footer',
                  'course_card', 'video_section', 'about_section', 'contact_section']

_BUILDERS = {
    'desktop_header': desktop_header,
    'mobile_header': mobile_header,
    'desktop_footer': desktop_footer,
    'mobile_footer': mobile_footer,
    'course_card': course_card,
    'video_section': video_section,
    'about_section': about_section,
    'contact_section': contact_section,
}


def build_variant(t, idx):
    """۸ کامپوننت برای طرح t (شاخص idx برای تنوع چیدمان)"""
    return {key: fn(t, idx) for key, fn in _BUILDERS.items()}


def all_variants():
    """لیست کامل ۲۰ واریانت — با ساختار JSON درخواستی"""
    out = []
    for i, t in enumerate(PERSIAN_THEMES):
        out.append(dict(
            design_id=f'design_variant_{i + 1:02d}',
            title=f'طرح {t["name"]} — واریانت {i + 1}',
            theme_id=t['id'],
            theme_name=t['name'],
            category=t['category'],
            dark=t.get('dark', False),
            colors=t['colors'],
            components=build_variant(t, i),
        ))
    return out


def export_json_files(out_dir):
    """نوشتن ۲۰ فایل JSON + یک فایل خلاصه"""
    import os
    os.makedirs(out_dir, exist_ok=True)
    variants = all_variants()
    for v in variants:
        path = os.path.join(out_dir, f'{v["design_id"]}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(v, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, 'ALL_DESIGN_VARIANTS.json'), 'w', encoding='utf-8') as f:
        json.dump(variants, f, ensure_ascii=False, indent=2)
    return len(variants)


if __name__ == '__main__':
    import os
    n = export_json_files(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs', 'design_variants'))
    print(f'{n} واریانت تولید شد')
