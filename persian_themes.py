# -*- coding: utf-8 -*-
"""۲۰ طرح اختصاصی با هویت بصری ایرانی — طراحی‌های سایت
هر طرح = پالت کامل رنگی (توکن‌های CSS سراسری) + چیدمان صفحه اصلی (JSON صفحه‌ساز)
+ کامپوننت‌های نمونه (HTML راست‌چین) برای خروجی JSON مستندات.
"""
import json

# ---------------------------------------------------------------
# ابزار رنگ — تبدیل و تولید توکن‌ها از پالت پایه
# ---------------------------------------------------------------
def _hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(*[max(0, min(255, int(round(c)))) for c in rgb])


def _rgb_to_hsl(rgb):
    r, g, b = (c / 255.0 for c in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        return (0, 0, l)
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = (g - b) / d + (6 if g < b else 0)
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return (h / 6, s, l)


def _hsl_to_rgb(hsl):
    h, s, l = hsl
    h = h % 1.0
    def hue(p, q, t):
        if t < 0: t += 1
        if t > 1: t -= 1
        if t < 1 / 6: return p + (q - p) * 6 * t
        if t < 1 / 2: return q
        if t < 2 / 3: return p + (q - p) * (2 / 3 - t) * 6
        return p
    if s == 0:
        return (l * 255,) * 3
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    return tuple(round(hue(p, q, t + 1 / 3) * 255) for t in (0, 1, 2)) or (0, 0, 0)


def lighten(h, amt):
    r, g, b = _hex_to_rgb(h)
    hh, s, l = _rgb_to_hsl((r / 255, g / 255, b / 255))
    return _rgb_to_hex(_hsl_to_rgb((hh, s, min(1, l + amt))))


def darken(h, amt):
    return lighten(h, -amt)


def mix(h1, h2, w1=0.5):
    a, b = _hex_to_rgb(h1), _hex_to_rgb(h2)
    return _rgb_to_hex(tuple(a[i] * w1 + b[i] * (1 - w1) for i in range(3)))


def alpha(h, a):
    r, g, b = _hex_to_rgb(h)
    return f'rgba({r},{g},{b},{a})'


def _brightness(h):
    r, g, b = _hex_to_rgb(h)
    return (r * 299 + g * 587 + b * 114) / 1000 / 255


def is_dark(h):
    r, g, b = _hex_to_rgb(h)
    return (r * 299 + g * 587 + b * 114) / 1000 < 140


# ---------------------------------------------------------------
# ۲۰ طرح ایرانی
# ---------------------------------------------------------------
PERSIAN_THEMES = [
    # ── ۱ ────────────────────────────────────────────────
    dict(id='pd-01', key='isfahan_turquoise', name='فیروزه‌ای اصفهان',
         category='سنتی - رسمی', desc='فیروزه تیره، کرم عاجی و طلایی سنتی — مناسب دوره‌های رسمی و دانشگاهی',
         dark=False, container='1240', radius='16',
         colors=dict(primary='#0F766E', secondary='#F4F1DE', accent='#D9A441', background='#FAF9F4', text='#1D2A44'),
         hero=[dict(img='hero.webp', title='آکادمی دانش — پنجره‌ای به دانایی بی‌پایان',
                    sub='سرفصل، مدرس و جزئیات دوره‌های منتشرشده را بررسی کنید.',
                    btn_text='🎓 مشاهده دوره‌های رسمی', btn_url='/courses', align='right'),
               dict(img='cover-flask.webp', title='علم را با هنر اصفهان بیاموز',
                    sub='کاشی‌های فیروزه‌ای و کرم عاجی — فضایی اصیل برای یادگیری عمیق.',
                    btn_text='شروع یادگیری', btn_url='/courses', align='center')],
         features=[('🕌', 'ساختار آموزشی', 'نمایش منظم سرفصل‌های هر دوره'),
                   ('🏛', 'گواهی قابل استعلام', 'کد رهگیری پس از تکمیل دوره'),
                   ('👤', 'پروفایل مدرس', 'معرفی و دوره‌های منتشرشده'),
                   ('📜', 'منابع دوره', 'فایل‌ها و محتوای ثبت‌شده مدرس'),
                   ('⚖️', 'قوانین روشن', 'دسترسی به قوانین پیش از خرید'),
                   ('📈', 'پیگیری پیشرفت', 'ثبت جلسات تکمیل‌شده در حساب')],
         course_title='📚 دوره‌های دانشکده', course_sub='منتخب استادان دانشگاه',
         cta=dict(title='دوره مناسب خود را پیدا کنید', text='موضوع و سطح دوره‌ها را مقایسه کنید.',
                  btn_text='مشاهده دوره‌ها', btn_url='/courses')),
    # ── ۲ ────────────────────────────────────────────────
    dict(id='pd-02', key='saffron_qainat', name='زعفرانی قائنات',
         category='مهارتی - پرانرژی', desc='زرد زعفرانی، سرمه‌ای عمیق و سفید برفی — پرانرژی برای دوره‌های مهارتی',
         dark=False, container='1280', radius='10',
         colors=dict(primary='#C9962E', secondary='#1B2A4A', accent='#F4B41A', background='#FDFDF9', text='#17202A'),
         hero=[dict(img='hero.webp', title='مهارتت را طلایی کن',
                    sub='دوره‌های عملی و بازارمحور با رنگ زعفران — ارزشمند مثل طلای سرخ.',
                    btn_text='🚀 شروع مسیر مهارت', btn_url='/courses', align='right'),
               dict(img='cover-marketing.webp', title='از صفر تا درآمد',
                    sub='مهارت‌های پولساز را همین امروز یاد بگیر؛ آینده‌ات را خودت بساز.',
                    btn_text='مشاهده دوره‌ها', btn_url='/courses', align='center')],
         features=[('💪', 'مهارت عملی', 'تمرین واقعی در هر جلسه'),
                   ('📈', 'بازارمحور', 'مطابق نیاز روز بازار کار'),
                   ('⏱', 'یادگیری سریع', 'مسیر آموزشی فشرده و هدفمند'),
                   ('🏆', 'نتیجه‌گرا', 'پروژه پایانی با خروجی واقعی'),
                   ('🤝', 'شبکه سازی', 'ارتباط با حرفه‌ای‌های صنعت'),
                   ('💼', 'آماده استخدام', 'رزومه و نمونه‌کار حرفه‌ای')],
         course_title='⭐ دوره‌های مهارتی طلایی', course_sub='پربازده‌ترین انتخاب‌ها',
         cta=dict(title='وقت طلاست — مسیر خود را شروع کنید', text='دوره‌های منتشرشده را بررسی کنید.',
                  btn_text='مشاهده دوره‌ها', btn_url='/courses')),
    # ── ۳ ────────────────────────────────────────────────
    dict(id='pd-03', key='shiraz_lapis', name='لاجوردی شیراز',
         category='آرامش - علوم انسانی', desc='آبی لاجوردی، مس روشن و خاکستری مات — آرامش‌بخش برای علوم انسانی و روانشناسی',
         dark=False, container='1240', radius='14',
         colors=dict(primary='#2E4E8F', secondary='#C97B4A', accent='#8FA3BF', background='#F5F6F8', text='#2B3440'),
         hero=[dict(img='hero.webp', title='سفری به عمق اندیشه',
                    sub='علوم انسانی، روانشناسی و فلسفه — با الهام از شبستان‌های آرام شیراز.',
                    btn_text='📖 دوره‌های علوم انسانی', btn_url='/courses', align='right'),
               dict(img='cover-uiux.webp', title='آرامش در یادگیری',
                    sub='محیطی متمرکز و بدون حواس‌پرتی برای تفکر عمیق.',
                    btn_text='شروع', btn_url='/courses', align='center')],
         features=[('🕊', 'یادگیری آرام', 'بدون عجله، با تمرکز کامل'),
                   ('📚', 'متن‌های بنیادین', 'مطالعه منابع اصلی و کلاسیک'),
                   ('🧠', 'تفکر نقاد', 'پرورش ذهن پرسشگر'),
                   ('🌙', 'شب‌های مطالعه', 'جلسات پرسش و پاسخ شبانه'),
                   ('✍️', 'مقاله‌نویسی', 'راهنمای نگارش علمی'),
                   ('🎧', 'پادکست درسی', 'یادگیری هنگام قدم زدن')],
         course_title='📖 علوم انسانی و هنر', course_sub='با نگاه شیرازی',
         cta=dict(title='ذهنت را آزاد کن', text='دوره‌های منتشرشده را بررسی کنید',
                  btn_text='مشاهده دوره‌ها', btn_url='/courses')),
    # ── ۴ ────────────────────────────────────────────────
    dict(id='pd-04', key='yazd_pomegranate', name='اناری یزد',
         category='هنر و خلاقیت', desc='قرمز اناری، شنی کویر و زیتونی تیره — مدرن و پویا برای دوره‌های هنر و طراحی',
         dark=False, container='1260', radius='18',
         colors=dict(primary='#B3272E', secondary='#E3CFA4', accent='#5A6B3A', background='#FAF6EF', text='#33261C'),
         hero=[dict(img='hero.webp', title='هنر را با رنگ انار بیامیز',
                    sub='طراحی، نقاشی و هنرهای تجسمی — الهام‌گرفته از بادگیرهای کویر.',
                    btn_text='🎨 ورود به گالری دوره‌ها', btn_url='/courses', align='right'),
               dict(img='cover-uiux.webp', title='خلاقیت بدون مرز',
                    sub='از ایده تا اثر؛ پرورش ذهن هنرمند با تکنیک‌های روز.',
                    btn_text='شروع خلق', btn_url='/courses', align='center')],
         features=[('🎨', 'کارگاه عملی', 'تمرین هنری در هر جلسه'),
                   ('🖌', 'تکنیک‌های روز', 'آخرین متدهای طراحی'),
                   ('🏜', 'الهام کویر', 'رنگ و فرم از معماری ایرانی'),
                   ('🖼', 'نمایشگاه مجازی', 'نمایش آثار هنرجویان'),
                   ('⭐', 'اساتید هنرمند', 'هنرمندان شناخته‌شده'),
                   ('📐', 'ابزار حرفه‌ای', 'آموزش نرم‌افزارهای تخصصی')],
         course_title='🎨 کارگاه‌های هنر و طراحی', course_sub='با طعم انار یزدی',
         cta=dict(title='اثر هنری بعدی، اثر توست', text='دوره‌های هنر و طراحی را ببینید.',
                  btn_text='مشاهده دوره‌ها', btn_url='/courses')),
    # ── ۵ ────────────────────────────────────────────────
    dict(id='pd-05', key='kavir_terracotta', name='سفال کویر',
         category='تخصصی - اصیل', desc='آجری، خاکستری گرم و سفید — حس اصالت و اعتماد برای آموزش‌های تخصصی',
         dark=False, container='1240', radius='12',
         colors=dict(primary='#B85C38', secondary='#8A8A86', accent='#D9A05B', background='#F8F5F0', text='#3A322C'),
         hero=[dict(img='hero.webp', title='تخصص، ساخته‌شده با دست‌های توانا',
                    sub='آموزش‌های فنی و حرفه‌ای با استانداردهای جهانی — مثل سفالگری استادکار.',
                    btn_text='🔧 دوره‌های تخصصی', btn_url='/courses', align='right'),
               dict(img='cover-excel.webp', title='ساخته از خاک، استوار مثل کوه',
                    sub='مهارت‌هایی که سال‌ها ماندگار می‌مانند.',
                    btn_text='مشاهده دوره‌ها', btn_url='/courses', align='center')],
         features=[('⚒', 'مهارت فنی', 'آموزش تخصصی و دقیق'),
                   ('🏺', 'اصالت', 'روش‌های آزموده‌شده'),
                   ('🛠', 'کارگاهی', 'تمرین با ابزار واقعی'),
                   ('🎓', 'مدرک فنی', 'گواهینامه مهارت'),
                   ('⏳', 'ماندگاری', 'دانش بی‌زمان'),
                   ('🛡', 'ضمانت کیفیت', 'پشتیبانی پس از آموزش')],
         course_title='⚙️ آموزش‌های فنی و تخصصی', course_sub='سفالینه‌های دانایی',
         cta=dict(title='استادکار شو', text='جزئیات مسیرهای آموزشی را بررسی کنید',
                  btn_text='دریافت مشاوره', btn_url='/consultation')),
    # ── ۶ ────────────────────────────────────────────────
    dict(id='pd-06', key='termeh_yazdi', name='ترمه یزدی',
         category='لوکس - مدیریتی', desc='بنفش ترمه‌ای، طلایی مات و صورتی ملایم — لوکس و مناسب آموزش‌های مدیریتی',
         dark=False, container='1240', radius='20',
         colors=dict(primary='#5B3E8F', secondary='#C9A227', accent='#E8B4C8', background='#FBF8F5', text='#2C2340'),
         hero=[dict(img='hero.webp', title='مدیریت، هنر بافت ترمه',
                    sub='دوره‌های مدیریتی و MBA با ظرافت ترمه‌های یزد — فاخر و ماندگار.',
                    btn_text='💎 دوره‌های مدیریت', btn_url='/courses', align='right'),
               dict(img='cover-marketing.webp', title='رهبری با وقار',
                    sub='مهارت‌های رهبری، مذاکره و برندسازی شخصی.',
                    btn_text='شروع', btn_url='/courses', align='center')],
         features=[('👔', 'مدیریت نوین', 'آخرین متدهای رهبری'),
                   ('💎', 'محتوا فاخر', 'کیفیت در سطح بین‌المللی'),
                   ('📊', 'تحلیل کسب‌وکار', 'مطالعه موردی واقعی'),
                   ('🗣', 'مذاکره حرفه‌ای', 'تمرین عملی مذاکره'),
                   ('🌐', 'شبکه مدیران', 'ارتباط با مدیران ارشد'),
                   ('📜', 'گواهی MBA', 'مدرک معتبر مدیریتی')],
         course_title='💼 آکادمی مدیریت و رهبری', course_sub='به سبک ترمه‌های یزد',
         cta=dict(title='مدیر فردا، امروز ساخته می‌شود', text='اطلاعات دوره‌های مدیریت را ببینید',
                  btn_text='رزرو جلسه', btn_url='/consultation')),
    # ── ۷ ────────────────────────────────────────────────
    dict(id='pd-07', key='mina_pottery', name='میناکاری',
         category='فناوری - مدرن', desc='آبی کاربنی، فیروزه‌ای روشن و سفید — شفاف و تمیز برای علوم کامپیوتر',
         dark=False, container='1280', radius='10',
         colors=dict(primary='#16324F', secondary='#2EC4B6', accent='#48A9A6', background='#F6F9FB', text='#14212E'),
         hero=[dict(img='hero.webp', title='کدت را مثل میناکاری صیقل بده',
                    sub='برنامه‌نویسی، هوش مصنوعی و مهندسی نرم‌افزار — دقیق، تمیز و شفاف.',
                    btn_text='💻 دوره‌های برنامه‌نویسی', btn_url='/courses', align='right'),
               dict(img='cover-python.webp', title='از صفر تا استادی در پایتون',
                    sub='مسیر یادگیری قدم‌به‌قدم با پروژه‌های واقعی.',
                    btn_text='مشاهده دوره پایتون', btn_url='/courses', align='center')],
         features=[('💻', 'کدنویسی تمیز', 'استانداردهای مهندسی'),
                   ('🤖', 'هوش مصنوعی', 'از مفاهیم تا استقرار مدل'),
                   ('🔬', 'دقت و شفافیت', 'مثل مینای شفاف'),
                   ('⚡', 'پرفورمنس', 'بهینه‌سازی کد'),
                   ('🛠', 'ابزارهای روز', 'تکنولوژی‌های ۲۰۲۶'),
                   ('🚀', 'استقرار سریع', 'از IDE تا سرور')],
         course_title='💻 دانشکده کامپیوتر', course_sub='مهندسی مثل میناکاری',
         cta=dict(title='کدنویسی را حرفه‌ای شروع کن', text='با تخفیف ۳۰٪ دوره‌های ترم پاییز',
                  btn_text='ثبت‌نام با تخفیف', btn_url='/register')),
    # ── ۸ ────────────────────────────────────────────────
    dict(id='pd-08', key='rosewater_qamsar', name='گلاب قمصر',
         category='عمومی - سبک زندگی', desc='صورتی رز، طوسی روشن و سبز نود — مدرن برای دوره‌های عمومی و سبک زندگی',
         dark=False, container='1240', radius='20',
         colors=dict(primary='#D98CA3', secondary='#E8E8EC', accent='#9DB89A', background='#FCF9FA', text='#3A3340'),
         hero=[dict(img='hero.webp', title='زندگی را با عطر گلاب قمصر بیاموز',
                    sub='دوره‌های سبک زندگی، سلامت و توسعه فردی — لطیف و دلنشین.',
                    btn_text='🌸 دوره‌های سبک زندگی', btn_url='/courses', align='right'),
               dict(img='cover-excel.webp', title='هر روز، یک قدم بهتر',
                    sub='عادت‌های کوچک، تغییرات بزرگ.',
                    btn_text='شروع', btn_url='/courses', align='center')],
         features=[('🌸', 'لطافت', 'محتوای نرم و الهام‌بخش'),
                   ('🌿', 'سلامت', 'روانشناسی و تغذیه'),
                   ('🧘‍♀️', 'آرامش', 'مدیتیشن و تمرکز'),
                   ('📔', 'توسعه فردی', 'عادت‌سازی و هدف‌گذاری'),
                   ('🏡', 'خانه و خانواده', 'مهارت‌های زندگی'),
                   ('💐', 'جامعه دوستانه', 'گروه‌های گفتگو')],
         course_title='🌸 سبک زندگی و توسعه فردی', course_sub='با عطر گلاب',
         cta=dict(title='زندگی زیباتر می‌شود', text='دوره‌های سبک زندگی را بررسی کنید',
                  btn_text='مشاهده دوره‌ها', btn_url='/courses')),
    # ── ۹ ────────────────────────────────────────────────
    dict(id='pd-09', key='pistachio_rafsanjan', name='پسته رفسنجان',
         category='طبیعت - رشد', desc='سبز پسته‌ای، کرم روشن و قهوه‌ای شکلاتی — حس رشد و یادگیری',
         dark=False, container='1240', radius='16',
         colors=dict(primary='#7CAF5A', secondary='#F4EDDD', accent='#6B4A2F', background='#FBF9F2', text='#2E3329'),
         hero=[dict(img='hero.webp', title='مثل پسته رفسنجان، ارزشمند رشد کن',
                    sub='کشاورزی، محیط زیست و مهارت‌های سبز — رشد با ریشه‌های محکم.',
                    btn_text='🌱 دوره‌های سبز', btn_url='/courses', align='right'),
               dict(img='cover-marketing.webp', title='ریشه در خاک، شاخه در آسمان',
                    sub='یادگیری پایدار برای آینده‌ای سبز.',
                    btn_text='شروع', btn_url='/courses', align='center')],
         features=[('🌱', 'رشد پایدار', 'یادگیری گام‌به‌گام'),
                   ('🥜', 'ارزش واقعی', 'محتوا با کیفیت پسته'),
                   ('🌳', 'محیط زیست', 'دوره‌های سبز'),
                   ('🚜', 'کشاورزی مدرن', 'تکنولوژی در کشاورزی'),
                   ('🍫', 'گرم و صمیمی', 'جامعه‌ای مهربان'),
                   ('📈', 'بهبود مستمر', 'به‌روزرسانی محتوا')],
         course_title='🌱 دوره‌های رشد و توسعه', course_sub='مثل پسته رفسنجان',
         cta=dict(title='ریشه‌هایت را عمیق کن', text='دوره‌های رشد و توسعه را بررسی کنید.',
                  btn_text='مشاهده دوره‌ها', btn_url='/courses')),
    # ── ۱۰ ───────────────────────────────────────────────
    dict(id='pd-10', key='ancient_marble', name='مرمر کهن',
         category='تیره - لوکس', desc='مشکی زغالی، طلایی و سفید مرمری — تم تاریک لوکس و حرفه‌ای',
         dark=True, container='1240', radius='18',
         colors=dict(primary='#C9A227', secondary='#17181C', accent='#8E8E93', background='#121316', text='#F5F2EA'),
         hero=[dict(img='hero.webp', title='دانایی، حجاری‌شده بر مرمر',
                    sub='تجربه‌ای لوکس و تاریک برای حرفه‌ای‌ها — مثل کاخ‌های مرمرین تخت جمشید.',
                    btn_text='✨ دوره‌های ویژه', btn_url='/courses', align='right'),
               dict(img='cover-ml.webp', title='درخشش در تاریکی',
                    sub='دوره‌های پیشرفته با ظاهری باشکوه.',
                    btn_text='شروع', btn_url='/courses', align='center')],
         features=[('🏛', 'شکوه', 'طراحی لوکس و ماندگار'),
                   ('🌑', 'حالت تاریک', 'کم‌آزار برای چشم'),
                   ('✨', 'درخشش طلا', 'جزئیات طلایی'),
                   ('🎯', 'حرفه‌ای', 'ویژه متخصصان'),
                   ('🕯', 'تمرکز', 'بدون حواس‌پرتی'),
                   ('💎', 'انحصاری', 'محتوا VIP')],
         course_title='✨ دوره‌های ویژه متخصصان', course_sub='به سبک مرمر کهن',
         cta=dict(title='به باشگاه متخصصان بپیوند', text='عضویت VIP با امکانات ویژه',
                  btn_text='عضویت VIP', btn_url='/register')),
    # ── ۱۱ ───────────────────────────────────────────────
    dict(id='pd-11', key='traditional_tile', name='کاشی سنتی',
         category='سنتی - فرهنگی', desc='آبی متمایل به سبز، کرم نان و زرد لیمویی سنتی',
         dark=False, container='1240', radius='14',
         colors=dict(primary='#1D6E7A', secondary='#F0E3C0', accent='#F2C94C', background='#FAF7EE', text='#26323A'),
         hero=[dict(img='hero.webp', title='آموزش، کاشی‌کاشی چیده می‌شود',
                    sub='دوره‌های فرهنگی و هنری با نقش‌های کاشی‌های هفت‌رنگ ایرانی.',
                    btn_text='🏺 دوره‌های فرهنگی', btn_url='/courses', align='right'),
               dict(img='cover-uiux.webp', title='هفت‌رنگ، هفت مهارت',
                    sub='هر رنگ یک مهارت تازه برای زندگی.',
                    btn_text='شروع', btn_url='/courses', align='center')],
         features=[('🧱', 'ساختارمند', 'مسیر آموزشی منظم'),
                   ('🎨', 'هفت‌رنگ', 'تنوع در آموزش'),
                   ('🏠', 'فرهنگ ایرانی', 'هویت در محتوا'),
                   ('✨', 'ظریف‌کاری', 'دقت در جزئیات'),
                   ('📿', 'نقوش سنتی', 'الهام از هنر ایرانی'),
                   ('🖐', 'دست‌ساز', 'محتوا با وسواس')],
         course_title='🏺 فرهنگ و هنر ایرانی', course_sub='با نقش کاشی',
         cta=dict(title='هفت‌رنگ یاد بگیر', text='دوره‌های فرهنگ و هنر را بررسی کنید.',
                  btn_text='مشاهده دوره‌ها', btn_url='/courses')),
    # ── ۱۲ ───────────────────────────────────────────────
    dict(id='pd-12', key='orosi_stained_glass', name='شیشه رنگی ارسی',
         category='کودک و نوجوان - پویا', desc='چندرنگ کنترل‌شده (قرمز، آبی، زرد، سبز) با زمینه سفید — پویا برای کودکان و نوجوانان',
         dark=False, container='1240', radius='22',
         colors=dict(primary='#E63946', secondary='#F1FAEE', accent='#2A9D8F', background='#FFFFFF', text='#2B2D42'),
         hero=[dict(img='hero.webp', title='رنگارنگ یاد بگیر، مثل شیشه‌های ارسی',
                    sub='دوره‌های سرگرم‌کننده برای کودکان و نوجوانان — با بازی و خلاقیت.',
                    btn_text='🌈 دوره‌های کودکان', btn_url='/courses', align='right'),
               dict(img='cover-android.webp', title='هر پنجره، یک دنیای تازه',
                    sub='برنامه‌نویسی، رباتیک، نقاشی و موسیقی.',
                    btn_text='شروع بازی', btn_url='/courses', align='center')],
         features=[('🎈', 'سرگرمی', 'یادگیری با بازی'),
                   ('🟥', 'رنگارنگ', 'محتوا بصری جذاب'),
                   ('🟦', 'خلاقیت', 'پرورش استعداد'),
                   ('🟨', 'انرژی', 'کلاس‌های پرنشاط'),
                   ('🟩', 'ایمن', 'محیط امن کودکان'),
                   ('👨‍👩‍👧', 'خانواده', 'گزارش پیشرفت برای والدین')],
         course_title='🌈 آکادمی کودکان و نوجوانان', course_sub='پنجره‌های رنگی یادگیری',
         cta=dict(title='کودک خلاقت را خوشحال کن', text='دوره‌های کودک و نوجوان را بررسی کنید',
                  btn_text='ثبت‌نام کودک', btn_url='/register')),
    # ── ۱۳ ───────────────────────────────────────────────
    dict(id='pd-13', key='wood_mat', name='چوب و حصیر',
         category='طبیعت - آرامش', desc='قهوه‌ای خاکی، کرم چرمی و سبز زیتونی — حس طبیعت و آرامش',
         dark=False, container='1240', radius='14',
         colors=dict(primary='#7B5B3A', secondary='#D9C2A7', accent='#6B705C', background='#F7F3EC', text='#35291C'),
         hero=[dict(img='hero.webp', title='دانایی، مثل بافت حصیر',
                    sub='دوره‌های صنایع دستی، چوب و طبیعت — آرامش در هر گره.',
                    btn_text='🪵 کارگاه‌های طبیعت', btn_url='/courses', align='right'),
               dict(img='cover-marketing.webp', title='دست‌ها، بهترین معلم‌ها',
                    sub='یادگیری عملی با چوب، حصیر و خاک.',
                    btn_text='شروع', btn_url='/courses', align='center')],
         features=[('🪵', 'صنایع دستی', 'چوب، حصیر و سفال'),
                   ('🌿', 'طبیعت', 'محتوا با ریتم طبیعت'),
                   ('🕰', 'آرامش', 'یادگیری بدون استرس'),
                   ('🤲', 'کار دست', 'پروژه‌های دست‌ساز'),
                   ('🔥', 'گرما', 'جامعه صمیمی'),
                   ('🏡', 'سبک ساده', 'زندگی مینیمال')],
         course_title='🪵 کارگاه طبیعت و دست‌سازه', course_sub='با ریتم چوب و حصیر',
         cta=dict(title='با دست‌هایت بساز', text='دوره‌های صنایع دستی را بررسی کنید',
                  btn_text='رزرو کارگاه', btn_url='/consultation')),
    # ── ۱۴ ───────────────────────────────────────────────
    dict(id='pd-14', key='iranian_miniature', name='مینیاتور ایرانی',
         category='هنر - سنتی', desc='نارنجی مینیاتوری، آبی نفتی و طوسی فیلی',
         dark=False, container='1240', radius='16',
         colors=dict(primary='#E07B39', secondary='#1F3A5F', accent='#9AA0A8', background='#FBF6EE', text='#3A2E24'),
         hero=[dict(img='hero.webp', title='هر درس، یک نگاره مینیاتور',
                    sub='هنرهای تجسمی، خوشنویسی و نگارگری — با ظرافت مینیاتورهای ایرانی.',
                    btn_text='🖌 گالری هنر', btn_url='/courses', align='right'),
               dict(img='cover-uiux.webp', title='ظرافت در جزئیات',
                    sub='طراحی و نگارگری با چشم‌های دقیق.',
                    btn_text='شروع', btn_url='/courses', align='center')],
         features=[('🖌', 'نگارگری', 'آموزش مینیاتور کلاسیک'),
                   ('🦚', 'ظرافت', 'جزئیات دقیق و چشم‌نواز'),
                   ('🎨', 'رنگ‌سازی', 'تکنیک رنگ‌های سنتی'),
                   ('✒️', 'خوشنویسی', 'نستعلیق و شکسته'),
                   ('📜', 'تذهیب', 'حاشیه‌سازی طلایی'),
                   ('🏵', 'هویت', 'هنر اصیل ایرانی')],
         course_title='🖌 نگارخانه هنر ایرانی', course_sub='ظریف مثل مینیاتور',
         cta=dict(title='نگاره بعدی را تو بکش', text='دوره‌های هنر ایرانی را بررسی کنید',
                  btn_text='شرکت در کارگاه', btn_url='/register')),
    # ── ۱۵ ───────────────────────────────────────────────
    dict(id='pd-15', key='desert_night', name='شب کویر',
         category='تیره - برنامه‌نویسی', desc='سرمه‌ای بسیار تیره، زرد ستاره‌ای و بنفش تیره — تم تاریک جذاب برای کدنویسی',
         dark=True, container='1280', radius='10',
         colors=dict(primary='#FFD166', secondary='#0D1B2A', accent='#3A2E5C', background='#0A1420', text='#E8ECF1'),
         hero=[dict(img='hero.webp', title='در شب کویر، کد بنویس',
                    sub='دوره‌های برنامه‌نویسی در تم تاریک — مثل ستاره‌های شب یزد.',
                    btn_text='💻 شروع کدنویسی', btn_url='/courses', align='right'),
               dict(img='cover-python.webp', title='هر ستاره، یک الگوریتم',
                    sub='از پایه تا پیشرفته، زیر آسمان پرستاره.',
                    btn_text='مشاهده دوره‌ها', btn_url='/courses', align='center')],
         features=[('🌌', 'تاریک‌ملایم', 'مناسب کدنویسی طولانی'),
                   ('⭐', 'الگوریتم', 'تفکر محاسباتی'),
                   ('🐍', 'پایتون', 'دوره‌های کامل'),
                   ('🕸', 'وب', 'فرانت و بک‌اند'),
                   ('🤖', 'هوش مصنوعی', 'مدل‌های زبانی'),
                   ('🚀', 'دواپس', 'استقرار و ابر')],
         course_title='💻 برنامه‌نویسی در شب کویر', course_sub='تا روشنایی، ادامه بده',
         cta=dict(title='ساعت کدت را شروع کن', text='تخفیف ۴۰٪ برای برنامه‌نویسان شب‌بیدار',
                  btn_text='شروع کدنویسی', btn_url='/register')),
    # ── ۱۶ ───────────────────────────────────────────────
    dict(id='pd-16', key='mountain_snow', name='سهند و سبلان',
         category='مینیمال - سریع', desc='آبی یخی، طوسی فضایی و سفید خالص — کم‌حجم، مینیمال و بسیار سریع',
         dark=False, container='1280', radius='8',
         colors=dict(primary='#5C8FA8', secondary='#E8EDF2', accent='#8FA3B8', background='#FBFCFD', text='#2A3440'),
         hero=[dict(img='hero.webp', title='سبک مثل برف سهند، سریع مثل باد',
                    sub='تجربه‌ای مینیمال و فوق‌سریع — تمرکز خالص بر یادگیری.',
                    btn_text='⛰ دوره‌ها', btn_url='/courses', align='right'),
               dict(img='cover-flask.webp', title='ارتفاع بگیر',
                    sub='از پایه تا قله، قدم‌به‌قدم.',
                    btn_text='شروع صعود', btn_url='/courses', align='center')],
         features=[('❄️', 'مینیمال', 'بدون شلوغی'),
                   ('⚡', 'سریع', 'بارگذاری آنی'),
                   ('🏔', 'ارتفاع', 'محتوا در سطح بالا'),
                   ('🎿', 'روان', 'تجربه کاربری نرم'),
                   ('🌨', 'ساده', 'سادگی در طراحی'),
                   ('🧗', 'چالش', 'مسیر پیشرفت')],
         course_title='⛰ دوره‌های مینیمال', course_sub='سبک و سریع',
         cta=dict(title='ساده و مؤثر بیاموز', text='دوره‌های منتشرشده را بررسی کنید',
                  btn_text='مشاهده دوره‌ها', btn_url='/courses')),
    # ── ۱۷ ───────────────────────────────────────────────
    dict(id='pd-17', key='persian_gulf', name='خلیج فارس',
         category='ساحلی - روشن', desc='آبی نیلگون، طلایی ساحلی و سفید اکلیلی',
         dark=False, container='1260', radius='16',
         colors=dict(primary='#0077B6', secondary='#E9C46A', accent='#48CAE4', background='#F5FAFD', text='#1C3140'),
         hero=[dict(img='hero.webp', title='یادگیری، مثل موج‌های خلیج فارس',
                    sub='دوره‌های دریایی، گردشگری و کسب‌وکار ساحلی — با طراوت نیلگون.',
                    btn_text='🌊 دوره‌های ساحلی', btn_url='/courses', align='right'),
               dict(img='cover-marketing.webp', title='طلوع یادگیری',
                    sub='هر روز صبح، یک مهارت تازه.',
                    btn_text='شروع', btn_url='/courses', align='center')],
         features=[('🌊', 'طراوت', 'محتوای تازه'),
                   ('⛵', 'گردشگری', 'دوره‌های تخصصی'),
                   ('🐚', 'مروارید', 'کیفیت انتخابی'),
                   ('☀️', 'روشنایی', 'فضای مثبت'),
                   ('🪸', 'اکوسیستم', 'جامعه فعال'),
                   ('🏖', 'آرامش', 'یادگیری لذت‌بخش')],
         course_title='🌊 دوره‌های خلیج فارس', course_sub='نیلگون و پرطراوت',
         cta=dict(title='موج یادگیری را بگیر', text='تخفیف ساحل‌نشین‌ها',
                  btn_text='شروع', btn_url='/courses')),
    # ── ۱۸ ───────────────────────────────────────────────
    dict(id='pd-18', key='khorasan_agate', name='عقیق خراسانی',
         category='سنتی - اصیل', desc='عقیقی/عنابی، طوسی موشی و کرم خاکی',
         dark=False, container='1240', radius='14',
         colors=dict(primary='#6D2E46', secondary='#8D99AE', accent='#D6C7A1', background='#F8F5F0', text='#332A2E'),
         hero=[dict(img='hero.webp', title='دانایی، عقیق‌وار گران‌بها',
                    sub='دوره‌های ادبیات، تاریخ و علوم انسانی — با اصالت خراسان.',
                    btn_text='📖 ادبیات و تاریخ', btn_url='/courses', align='right'),
               dict(img='cover-django.webp', title='از نیشابور تا نوآوری',
                    sub='علم و هنر در امتداد جاده ابریشم.',
                    btn_text='شروع', btn_url='/courses', align='center')],
         features=[('💎', 'ارزشمند', 'محتوا ناب و گزیده'),
                   ('📜', 'تاریخ', 'مطالعه اسناد و متون'),
                   ('✍️', 'ادبیات', 'شعر و نثر فارسی'),
                   ('🕌', 'فرهنگ', 'میراث خراسان'),
                   ('🧭', 'جهت‌گیری', 'مسیر مشخص یادگیری'),
                   ('🪨', 'استوار', 'پایه‌های محکم')],
         course_title='📖 ادبیات و میراث خراسان', course_sub='عقیق‌وار',
         cta=dict(title='گوهر دانش را صیقل بده', text='دوره‌های ادبیات و تاریخ را بررسی کنید.',
                  btn_text='مشاهده دوره‌ها', btn_url='/courses')),
    # ── ۱۹ ───────────────────────────────────────────────
    dict(id='pd-19', key='persian_garden', name='باغ ایرانی',
         category='طبیعت - شاد', desc='سبز زمردی، زرد آفتابی و استخوانی',
         dark=False, container='1260', radius='16',
         colors=dict(primary='#1B7A4A', secondary='#F4D03F', accent='#F2EFE7', background='#FAFCF7', text='#26382C'),
         hero=[dict(img='hero.webp', title='در باغ ایرانی، دانش می‌روید',
                    sub='دوره‌های کشاورزی، باغبانی و محیط زیست — چهارباغ یادگیری.',
                    btn_text='🌳 باغ‌بانی و طبیعت', btn_url='/courses', align='right'),
               dict(img='cover-marketing.webp', title='هر فصل، یک میوه تازه',
                    sub='مهارت‌های فصلی و به‌روز.',
                    btn_text='شروع', btn_url='/courses', align='center')],
         features=[('🌳', 'باغبانی', 'کاشت تا برداشت'),
                   ('💧', 'آبیاری هوشمند', 'مدیریت منابع آب'),
                   ('🌻', 'شادابی', 'محیط پرانرژی'),
                   ('🐝', 'اکولوژی', 'تعادل طبیعی'),
                   ('🏡', 'چهارباغ', 'مسیرهای متنوع'),
                   ('🍃', 'سرسبزی', 'یادگیری پایدار')],
         course_title='🌳 آکادمی باغ ایرانی', course_sub='چهارباغ دانش',
         cta=dict(title='باغت را آب بده', text='تخفیف فصل بهار',
                  btn_text='شروع کاشت', btn_url='/register')),
    # ── ۲۰ ───────────────────────────────────────────────
    dict(id='pd-20', key='tehran_modern', name='مدرن تهران',
         category='مدرن - گلسمورفیسم', desc='گلسمورفیسم مدرن با رگه‌های خطاطی نستعلیق و رنگ‌های خنثی',
         dark=False, container='1280', radius='24',
         colors=dict(primary='#4F5D75', secondary='#B08D57', accent='#7A8B99', background='#F3F4F7', text='#22262E'),
         hero=[dict(img='hero.webp', title='مدرن فکر کن، اصیل بیاموز',
                    sub='ترکیب تکنولوژی روز با ظرافت خط نستعلیق — تجربه‌ای شیشه‌ای و شفاف.',
                    btn_text='🚀 دوره‌های مدرن', btn_url='/courses', align='right'),
               dict(img='cover-ml.webp', title='شفاف مثل شیشه، دقیق مثل خط',
                    sub='هوش مصنوعی، دیتا و دیزاین در قلب تهران.',
                    btn_text='شروع', btn_url='/courses', align='center')],
         features=[('🫧', 'گلسمورفیسم', 'طراحی شیشه‌ای مدرن'),
                   ('✒️', 'خطاطی', 'نستعلیق در هویت بصری'),
                   ('📊', 'دیتا', 'علم داده و هوش مصنوعی'),
                   ('🎯', 'هدفمند', 'دوره‌های فشرده'),
                   ('🕶', 'مدرن', 'رویکرد ۲۰۲۶'),
                   ('🏙', 'شهری', 'ریتم زندگی مدرن')],
         course_title='🚀 دوره‌های مدرن تهران', course_sub='شفاف و دقیق',
         cta=dict(title='به آینده بپیوند', text='دوره‌های فناوری را بررسی کنید',
                  btn_text='شروع یادگیری', btn_url='/register')),
]

# ── ادغام پالت‌های دست‌چین‌شده (رنگ‌های نهایی هر طرح) ──
from persian_palettes import PALETTES as _PALETTES
for _t in PERSIAN_THEMES:
    _p = _PALETTES.get(_t['id'])
    if _p:
        _t['colors'] = {**_t['colors'], **_p['colors']}
        _t['tokens'] = _p['tokens']

PERSIAN_THEME_IDS = [t['id'] for t in PERSIAN_THEMES]
CATEGORIES = sorted({t['category'] for t in PERSIAN_THEMES})


def get_theme(tid):
    for t in PERSIAN_THEMES:
        if t['id'] == tid:
            return t
    return None


# ---------------------------------------------------------------
# توکن‌های کامل CSS از پالت پایه هر طرح
# ---------------------------------------------------------------
def tokens(t):
    c = t['colors']
    o = t.get('tokens') or {}
    primary = c['primary']
    dark = t.get('dark', False)
    bg = c['background']
    text = c['text']
    accent = c['accent']
    # توکن‌های دستی اولویت دارند؛ بقیه با الگوریتم بهینه مشتق می‌شوند
    if dark:
        card = o.get('card', lighten(bg, 0.05))
        bg2 = o.get('bg2', lighten(bg, 0.03))
        border = o.get('border', lighten(bg, 0.13))
        border2 = o.get('border2', lighten(bg, 0.22))
        text2 = o.get('text2', mix(text, bg, 0.30))
        text3 = o.get('text3', mix(text, bg, 0.52))
        header_bg = o.get('header_bg', 'rgba(10,14,20,.82)')
    else:
        card = o.get('card', '#FFFFFF')
        bg2 = o.get('bg2', lighten(bg, -0.022))
        border = o.get('border', mix(text, bg, 0.86))
        border2 = o.get('border2', mix(text, bg, 0.74))
        text2 = o.get('text2', mix(text, bg, 0.38))
        text3 = o.get('text3', mix(text, bg, 0.58))
        header_bg = o.get('header_bg', 'rgba(255,255,255,.92)')
    primary2 = o.get('primary2', darken(primary, 0.15))
    accent2 = o.get('accent2', darken(accent, 0.13))
    # نرم‌ها: ترکیب با سفید (پاستل تمیز) به‌جای روشن‌سازی ساده
    primary_soft = o.get('primary_soft', mix(primary, '#FFFFFF', 0.88) if not dark else mix(primary, bg, 0.78))
    accent_soft = o.get('accent_soft', mix(accent, '#FFFFFF', 0.86) if not dark else mix(accent, bg, 0.75))
    footer_bg = o.get('footer_bg', darken(text, 0.10))
    footer_text = o.get('footer_text', '#C9CFD8')
    footer_text2 = o.get('footer_text2', '#8D96A3')
    # رنگ متن روی دکمه‌ها — رنگ‌های روشن متن تیره می‌گیرند (کنتراست امن)
    on_primary = '#14202E' if _brightness(primary) > 0.50 else '#FFFFFF'
    on_accent = '#14202E' if _brightness(accent) > 0.52 else '#FFFFFF'
    hero_from = o.get('hero_from', primary)
    hero_to = o.get('hero_to', primary2)
    hero_deep = mix(hero_to, '#0B0F14', 0.82)  # تیره‌تر بدون سیاه خالص
    hero_grad = f'linear-gradient(135deg,{hero_from} 0%,{hero_to} 55%,{hero_deep} 100%)'
    shadow_rgb = _hex_to_rgb(text)
    shadow = f'rgba({shadow_rgb[0]},{shadow_rgb[1]},{shadow_rgb[2]},'
    return dict(
        primary=primary, primary2=primary2, primary_soft=primary_soft,
        accent=accent, accent2=accent2, accent_soft=accent_soft,
        bg=bg, bg2=bg2, card=card, border=border, border2=border2,
        text=text, text2=text2, text3=text3,
        header_bg=header_bg, footer_bg=footer_bg, footer_text=footer_text,
        footer_text2=footer_text2, footer_head='#FFFFFF',
        on_primary=on_primary, on_accent=on_accent,
        hero_grad=hero_grad, hero_text='#FFFFFF', hero_text2='rgba(255,255,255,.88)',
        hero_card='rgba(255,255,255,.12)',
        grad_brand=f'linear-gradient(135deg,{primary},{primary2})',
        grad_accent=f'linear-gradient(135deg,{accent},{accent2})',
        radius=t.get('radius', 14), container=t.get('container', '1240'),
        success='#15803D', danger='#DC2626', warning=accent, info=primary,
        shadow_sm=f'{shadow}.05)', shadow_md=f'{shadow}.08)', shadow_lg=f'{shadow}.12)',
        dark=dark,
    )


# ---------------------------------------------------------------
# تولید CSS کامل هر طرح
# ---------------------------------------------------------------
def build_css(t):
    k = tokens(t)
    dark = t['dark']
    # فوتر تیره‌تر برای تم روشن
    footer_bg2 = darken(k['footer_bg'], 0.12)
    return f'''/* {t['name']} — {t['category']} | تولیدشده از {t['id']} */
:root{{
--primary:{k['primary']};--primary-2:{k['primary2']};--primary-soft:{k['primary_soft']};
--on-primary:{k['on_primary']};--on-accent:{k['on_accent']};
--accent:{k['accent']};--accent-2:{k['accent2']};--accent-soft:{k['accent_soft']};
--success:#15803d;--success-soft:#f0fdf4;--danger:#dc2626;--danger-soft:#fef2f2;--warning:{k['accent']};--info:{k['primary']};
--bg:{k['bg']};--bg-2:{k['bg2']};--card:{k['card']};--card-2:{k['card']};
--border:{k['border']};--border-2:{k['border2']};
--text:{k['text']};--text-2:{k['text2']};--text-3:{k['text3']};
--header-bg:{k['header_bg']};--header-border:{k['border']};--header-text:{k['text']};--header-text-2:{k['text2']};
--hero-bg:{k['hero_grad']};--hero-text:{k['hero_text']};--hero-text-2:{k['hero_text2']};--hero-card:{k['hero_card']};
--footer-bg:{k['footer_bg']};--footer-text:{k['footer_text']};--footer-text-2:{k['footer_text2']};--footer-head:{k['footer_head']};
--grad-brand:{k['grad_brand']};--grad-accent:{k['grad_accent']};
--radius-sm:8px;--radius-md:{max(10, int(k['radius']) - 2)}px;--radius-lg:{k['radius']}px;
--shadow-sm:{k['shadow_sm']};--shadow-md:{k['shadow_md']};--shadow-lg:{k['shadow_lg']};
}}
.builder-site-header .dk-logo-ic{{background:{k['grad_brand']};border-radius:{int(k['radius']) - 4}px;box-shadow:0 6px 16px {k['shadow_md']}}}
.builder-site-header .dk-search{{border:2px solid {k['primary']}}}
.builder-site-header .dk-search:focus-within{{box-shadow:0 0 0 4px {k['primary_soft']}}}
.builder-site-header .dk-search button{{background:{k['primary']};color:{k['on_primary']}}}
.builder-site-header .dk-search button:hover{{background:{k['primary2']}}}
.builder-site-header .dk-icon-link:hover{{background:{k['primary_soft']};color:{k['primary']}}}
.builder-site-header .dk-badge{{background:{k['primary']}}}
.builder-site-header .dk-auth a{{background:{k['primary']};color:{k['on_primary']}}}
.builder-site-header .dk-auth a:hover{{background:{k['primary2']}}}
.builder-site-header .dk-user-dd{{border-top:3px solid {k['primary']}}}
.builder-site-header .dk-mega-trigger{{background:{k['primary']};color:{k['on_primary']};box-shadow:0 6px 16px {k['shadow_md']}}}
.builder-site-header .dk-nav a:hover{{color:{k['primary']};background:{k['primary_soft']}}}
.builder-site-header .dk-mega-panel{{border-top:3px solid {k['primary']}}}
.builder-site-header .dk-mega-head:hover,.builder-site-header .dk-mega-link:hover{{color:{k['primary']};background:{k['primary_soft']}}}
.builder-site-header .dk-mega-all{{color:{k['primary']}}}
.builder-site-footer{{background:radial-gradient(700px 300px at 90% -20%,{k['accent_soft']},transparent 60%),linear-gradient(180deg,{k['footer_bg']} 0%,{k['footer_bg']} 50%,{footer_bg2} 100%);border-top:3px solid {k['primary']}}}
.builder-site-footer .pb-f-links h2::after,.builder-site-footer .pb-f-contact h2::after{{background:{k['primary']}}}
.builder-site-footer .pb-f-links ul a::before{{color:{k['primary']}}}
.builder-site-footer .pb-f-about .dk-logo-ic{{background:{k['grad_brand']}}}
.builder-site-footer .pb-f-about .pb-f-socials a:hover{{background:{k['primary']};border-color:{k['primary']}}}
.builder-site-footer .pb-f-contact ul li span{{color:{k['primary']}}}
.builder-site-footer .newsletter-box .btn{{background:{k['primary']};color:{k['on_primary']}}}
.builder-site-footer .pb-trust-badges a:hover{{border-color:{k['primary']}}}
.pb-slide-overlay{{background:linear-gradient(120deg,rgba(8,15,35,.88),{k['primary']} 75%)}}
.pb-slide-content h1,.pb-slide-content h2{{color:#fff}}
.dk-topbar a:hover{{color:{k['accent']}}}
.btn-primary{{color:{k['on_primary']}}}
.btn-accent{{background:{k['grad_accent']};color:{k['on_accent']}}}
.pb-slide-arrow{{color:{k['primary']}}}
.chart-bar span{{background:{k['grad_brand']}}}
'''


# ---------------------------------------------------------------
# چیدمان صفحه اصلی هر طرح (JSON صفحه‌ساز)
# ---------------------------------------------------------------
def home_rows(t):
    feats = [dict(icon=i, title=tt, text=tx) for i, tt, tx in t['features']]
    # ⚠️ آمار پیش‌فرض «پویا» است (از دیتابیس پر می‌شود). عدد ثابت مثل
    # «۵۰,۰۰۰+ دانشجو» روی سایتی که تازه راه‌اندازی شده، از دید
    # Google Safe Browsing محتوای فریب‌دهنده است.
    st = t.get('stats') or [
        dict(value='{courses}', label='دوره آموزشی'),
        dict(value='{students}', label='دانشجوی فعال'),
        dict(value='{hours}', label='ساعت آموزش'),
        dict(value='{lessons}', label='درس منتشرشده'),
    ]
    cta = t['cta']
    return [
        {'id': 'sld', 'settings': {'gap': 0, 'py': 0}, 'cols': [[
            {'id': 'w_sl', 'type': 'slider', 'data': {
                'height': '430', 'autoplay': True, 'interval': '5', 'dots': True, 'arrows': True, 'swipe': True,
                'slides': t['hero']}}]]},
        {'id': 'stt', 'settings': {'gap': 0, 'py': 50}, 'cols': [[
            {'id': 'w_st', 'type': 'stats', 'data': {'columns': '4', 'items': st}}]]},
        {'id': 'ftr', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
            {'id': 'w_ft', 'type': 'feature', 'data': {'columns': '3', 'items': feats}}]]},
        {'id': 'crs', 'settings': {'gap': 24, 'py': 60}, 'cols': [[
            {'id': 'w_cr', 'type': 'courses', 'data': {
                'title': t['course_title'], 'subtitle': t['course_sub'],
                'limit': '8', 'columns': '4', 'sort': 'popular'}}]]},
        {'id': 'tst', 'settings': {'gap': 22, 'py': 60, 'bg': '#ffffff', 'radius': 24}, 'cols': [[
            {'id': 'w_ts', 'type': 'reviews', 'data': {'title': '⭐ نظرات واقعی دانشجویان', 'limit': '6'}}]]},
        {'id': 'cta', 'settings': {'gap': 0, 'py': 30}, 'cols': [[
            {'id': 'w_ct', 'type': 'cta', 'data': {
                'title': cta['title'], 'text': cta['text'],
                'btn_text': cta['btn_text'], 'btn_url': cta['btn_url']}}]]},
    ]


# ---------------------------------------------------------------
# کامپوننت‌های HTML نمونه (راست‌چین) برای خروجی JSON
# ---------------------------------------------------------------
def _section(t, html, title):
    return (f'<section dir="rtl" style="font-family:Vazirmatn,Tahoma,sans-serif;'
            f'background:{t["colors"]["background"]};color:{t["colors"]["text"]};'
            f'padding:40px 20px;line-height:1.9">{html}</section>')


def component_html(t):
    c = t['colors']
    p, a, s = c['primary'], c['accent'], c['secondary']
    bg, tx = c['background'], c['text']
    return dict(
        homepage=_section(t, f'''
  <div style="max-width:1100px;margin:0 auto;text-align:center">
    <span style="display:inline-block;background:{a}22;color:{a};font-weight:800;border-radius:99px;padding:6px 18px;font-size:13px">{t['name']}</span>
    <h1 style="font-size:clamp(26px,4.5vw,44px);font-weight:900;margin:18px 0 12px;color:{tx}">{t['hero'][0]['title']}</h1>
    <p style="max-width:620px;margin:0 auto 26px;color:{tx}99;font-size:15px">{t['hero'][0]['sub']}</p>
    <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
      <a href="/courses" style="background:{p};color:#fff;text-decoration:none;font-weight:800;padding:13px 30px;border-radius:14px;box-shadow:0 10px 24px {p}44">{t['hero'][0]['btn_text']}</a>
      <a href="/about" style="border:2px solid {a};color:{a};text-decoration:none;font-weight:800;padding:12px 30px;border-radius:14px">درباره ما</a>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-top:34px">
      <div style="background:#fff;border-radius:16px;padding:18px;border:1px solid {p}22"><b style="font-size:22px;color:{p}">—</b><div style="font-size:12.5px;color:{tx}88">دوره آموزشی</div></div>
      <div style="background:#fff;border-radius:16px;padding:18px;border:1px solid {p}22"><b style="font-size:22px;color:{p}">—</b><div style="font-size:12.5px;color:{tx}88">دانشجوی فعال</div></div>
      <div style="background:#fff;border-radius:16px;padding:18px;border:1px solid {p}22"><b style="font-size:22px;color:{p}">—</b><div style="font-size:12.5px;color:{tx}88">ساعت آموزش</div></div>
      <div style="background:#fff;border-radius:16px;padding:18px;border:1px solid {p}22"><b style="font-size:22px;color:{p}">—</b><div style="font-size:12.5px;color:{tx}88">رضایت</div></div>
    </div>
  </div>''', 'homepage'),
        course_card=_section(t, f'''
  <div style="max-width:380px;margin:0 auto;background:#fff;border-radius:20px;overflow:hidden;border:1px solid {p}22;box-shadow:0 14px 34px {tx}12">
    <div style="height:170px;background:linear-gradient(135deg,{p},{s})"></div>
    <div style="padding:20px">
      <span style="font-size:11px;color:{p};font-weight:800;background:{p}14;padding:4px 12px;border-radius:99px">دوره جامع</span>
      <h3 style="font-size:17px;font-weight:900;margin:12px 0 8px;color:{tx}">عنوان دوره — {t['name']}</h3>
      <p style="font-size:12.5px;color:{tx}88;margin-bottom:14px">توضیح کوتاه درباره سرفصل‌ها و دستاوردهای این دوره آموزشی…</p>
      <div style="display:flex;align-items:center;justify-content:space-between;border-top:1px dashed {p}33;padding-top:14px">
        <div><b style="font-size:18px;color:{p}">۱,۲۵۰,۰۰۰</b> <small style="color:{tx}77">تومان</small></div>
        <a href="/courses" style="background:{p};color:#fff;text-decoration:none;font-weight:800;padding:10px 22px;border-radius:12px">خرید سریع 🛒</a>
      </div>
    </div>
  </div>''', 'course_card'),
        video_player=_section(t, f'''
  <div style="max-width:900px;margin:0 auto;display:grid;grid-template-columns:1fr 280px;gap:16px" class="resp">
    <div style="border-radius:18px;overflow:hidden;background:#000;aspect-ratio:16/9;display:flex;align-items:center;justify-content:center;color:#fff;font-size:52px">▶</div>
    <div style="background:#fff;border:1px solid {p}22;border-radius:18px;padding:14px">
      <h4 style="font-size:14px;font-weight:900;margin-bottom:10px;color:{tx}">🎬 لیست پخش</h4>
      {''.join(f'<div style="display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:10px;background:{p}0d;margin-bottom:6px;font-size:12.5px"><b style="color:{p}">{i+1}</b> قسمت {i+1} — عنوان درس</div>' for i in range(4))}
      <div style="margin-top:12px;padding:10px;background:{a}14;border-radius:12px;font-size:12px;color:{a};font-weight:700">📝 یادداشت‌برداری و فایل ضمیمه این قسمت</div>
    </div>
  </div>''', 'video_player'),
        about_us=_section(t, f'''
  <div style="max-width:1000px;margin:0 auto">
    <h2 style="font-size:26px;font-weight:900;text-align:center;margin-bottom:8px;color:{tx}">داستان {t['name']}</h2>
    <p style="text-align:center;color:{tx}88;max-width:640px;margin:0 auto 30px;font-size:14px">ما با عشق به فرهنگ ایرانی و باور به آموزش باکیفیت، این آکادمی را بنا کردیم.</p>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px">
      <div style="background:#fff;border-radius:18px;padding:20px;border-top:4px solid {p}"><b style="color:{p}">🎯 مأموریت</b><p style="font-size:12.5px;color:{tx}88;margin-top:8px">آموزش مهارت‌های واقعی به زبان ساده برای همه ایرانیان.</p></div>
      <div style="background:#fff;border-radius:18px;padding:20px;border-top:4px solid {a}"><b style="color:{a}">👁 چشم‌انداز</b><p style="font-size:12.5px;color:{tx}88;margin-top:8px">مرجع اول آموزش آنلاین با هویت ایرانی در منطقه.</p></div>
      <div style="background:#fff;border-radius:18px;padding:20px;border-top:4px solid {p}"><b style="color:{p}">🏆 دستاوردها</b><p style="font-size:12.5px;color:{tx}88;margin-top:8px">آمار و دستاوردهای واقعی مجموعه خود را در این بخش بنویسید.</p></div>
    </div>
  </div>''', 'about_us'),
        contact_us=_section(t, f'''
  <div style="max-width:1000px;margin:0 auto;display:grid;grid-template-columns:1fr 1fr;gap:18px" class="resp">
    <form style="background:#fff;border-radius:18px;padding:22px;border:1px solid {p}22">
      <h3 style="font-weight:900;margin-bottom:14px;color:{tx}">📨 فرم تماس</h3>
      <input placeholder="نام و نام خانوادگی" style="width:100%;padding:11px 14px;border:1.5px solid {p}33;border-radius:11px;margin-bottom:10px">
      <input placeholder="ایمیل" style="width:100%;padding:11px 14px;border:1.5px solid {p}33;border-radius:11px;margin-bottom:10px">
      <textarea placeholder="پیام شما…" rows="4" style="width:100%;padding:11px 14px;border:1.5px solid {p}33;border-radius:11px;margin-bottom:12px"></textarea>
      <button style="background:{p};color:#fff;border:none;font-weight:800;padding:12px 30px;border-radius:12px;cursor:pointer">ارسال پیام</button>
    </form>
    <div style="background:#fff;border-radius:18px;padding:22px;border:1px solid {p}22;font-size:13px;color:{tx}88">
      <h3 style="font-weight:900;margin-bottom:14px;color:{tx}">📍 اطلاعات دسترسی</h3>
      <div style="margin-bottom:10px">🏢 آدرس ثبت‌شده مجموعه</div>
      <div style="margin-bottom:10px">📞 شماره تماس مجموعه</div>
      <div style="margin-bottom:10px">✉️ ایمیل پشتیبانی</div>
      <div style="height:140px;border-radius:14px;background:linear-gradient(135deg,{s},{p}22);display:flex;align-items:center;justify-content:center;color:{p};font-weight:800;margin-top:12px">🗺 نقشه — شبکه سراسری پشتیبانی</div>
    </div>
  </div>''', 'contact_us'),
    )


# ---------------------------------------------------------------
# خروجی JSON هر طرح (فرمت درخواستی)
# ---------------------------------------------------------------
def to_export_json(t):
    c = t['colors']
    comps = component_html(t)
    return dict(
        theme_id=t['id'],
        theme_name=t['name'],
        category=t['category'],
        colors=dict(primary=c['primary'], secondary=c['secondary'],
                    accent=c['accent'], background=c['background'], text=c['text']),
        layout_components=comps,
        homepage_rows=home_rows(t),
        dark=t.get('dark', False),
        container=t.get('container', '1240'),
        radius=t.get('radius', 14),
    )


def all_export_json():
    return [to_export_json(t) for t in PERSIAN_THEMES]
