# -*- coding: utf-8 -*-
"""۵ طرح آماده برای صفحه اصلی + ۵ طراحی کلی سایت + توضیحات"""

# ============================================================
# طراحی‌های کلی سایت (پیش‌تنظیم‌های سراسری)
# ============================================================
from persian_themes import PERSIAN_THEMES as _PT

SITE_DESIGNS = {
    '1': dict(name='کلاسیک', desc='سرمه‌ای و نارنجی — منو و فوتر کلاسیک آکادمیک',
              theme='theme-22', container='1280', radius='8'),
    '2': dict(name='ایرانی', desc='فیروزه‌ای و لاجورد با نقوش اسلیمی و گره‌چینی',
              theme='theme-21', container='1240', radius='14'),
    '3': dict(name='مدرن', desc='بنفش سلطنتی مدرن با گوشه‌های نرم',
              theme='theme-02', container='1240', radius='18'),
    '4': dict(name='شب', desc='تم تیره با آبی روشن — مناسب نمایشگر OLED',
              theme='theme-08', container='1240', radius='12'),
    '5': dict(name='مینیمال', desc='طوسی روشن و ساده، بدون شلوغی',
              theme='theme-10', container='1280', radius='8'),
    'amoozino': dict(name='آموزینو (Amoozino)', desc='سبز زمردی و جنگلی مدرن — پلتفرم فروش دوره‌های ویدیویی و فایل‌های آموزشی',
                     theme='pd-19', container='1240', radius='16'),
}
for _t in _PT:
    SITE_DESIGNS[_t['id']] = dict(name=_t['name'], desc=_t['desc'],
                                  theme=_t['id'], container=_t.get('container', '1240'),
                                  radius=_t.get('radius', 14), persian=True,
                                  category=_t['category'], dark=_t.get('dark', False))

# ============================================================
# ۵ طرح صفحه اصلی (بر پایه ویجت‌های صفحه‌ساز)
# ============================================================
HOME_DESIGNS = {
    '1': dict(
        title='صفحه اصلی — کلاسیک',
        desc='اسلایدر بزرگ + ویژگی‌ها + دسته‌بندی + دوره‌ها + آمار + اساتید + نظرات',
        settings={'seo_title': 'آکادمی آنلاین — مرجع تخصصی آموزش‌های آنلاین فارسی'},
        rows=[
            {'id': 'd1_slider', 'settings': {'gap': 0, 'py': 0}, 'cols': [[
                {'id': 'd1_w1', 'type': 'slider', 'data': {
                    'height': '440', 'autoplay': True, 'interval': '5', 'dots': True, 'arrows': True,
                    'slides': [
                        {'img': 'hero.webp', 'title': 'دوره‌های آموزشی منتشرشده',
                         'sub': 'سرفصل، مدرس، مدت و شرایط هر دوره را پیش از ثبت‌نام بررسی کنید.',
                         'btn_text': 'مشاهده همه دوره‌ها', 'btn_url': '/courses', 'align': 'right'},
                        {'img': 'cover-python.webp', 'title': 'مسیر یادگیری خود را انتخاب کنید',
                         'sub': 'آموزش گام‌به‌گام با تمرین و پروژه‌های کاربردی.',
                         'btn_text': 'مشاهده دوره پایتون', 'btn_url': '/courses', 'align': 'center'},
                    ]}}]],
            },
            {'id': 'd1_feat', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'd1_w2', 'type': 'feature', 'data': {'columns': '3', 'items': [
                    {'icon': '🎬', 'title': 'جلسات دوره', 'text': 'مشاهده سرفصل و مدت هر دوره پیش از خرید'},
                    {'icon': '🏅', 'title': 'گواهی قابل استعلام', 'text': 'کد رهگیری منحصربه‌فرد پس از تکمیل دوره'},
                    {'icon': '🎓', 'title': 'پروفایل مدرس', 'text': 'مشاهده معرفی و دوره‌های منتشرشده مدرس'},
                    {'icon': '📈', 'title': 'پیگیری پیشرفت', 'text': 'ثبت جلسات تکمیل‌شده در حساب کاربری'},
                    {'icon': '💬', 'title': 'تیکت پشتیبانی', 'text': 'ثبت و پیگیری درخواست از داخل حساب'},
                    {'icon': '🛡️', 'title': 'روش‌های پرداخت فعال', 'text': 'نمایش فقط روش‌هایی که مدیر تکمیل کرده است'},
                ]}}]],
            },
            {'id': 'd1_cats', 'settings': {'gap': 16, 'py': 60, 'bg': '#ffffff', 'radius': 24}, 'cols': [[
                {'id': 'd1_w3', 'type': 'categories', 'data': {'title': 'موضوع مورد علاقه‌ات را انتخاب کن', 'limit': '9', 'columns': '4'}}]],
            },
            {'id': 'd1_courses', 'settings': {'gap': 24, 'py': 60}, 'cols': [[
                {'id': 'd1_w4', 'type': 'courses', 'data': {'title': 'دوره‌های منتشرشده', 'subtitle': 'سرفصل و جزئیات دوره‌ها را مقایسه کنید', 'limit': '8', 'columns': '4', 'sort': 'newest'}}]],
            },
            {'id': 'd1_stats', 'settings': {'gap': 0, 'py': 50}, 'cols': [[
                # ⚠️ آمار پویا از دیتابیس — عدد ثابت جعلی روی سایت واقعی
                # «محتوای فریب‌دهنده» است و باعث هشدار «Dangerous site» می‌شود.
                {'id': 'd1_w5', 'type': 'stats', 'data': {'columns': '4', 'items': [
                    {'value': '{courses}', 'label': 'دوره آموزشی'},
                    {'value': '{students}', 'label': 'دانشجوی فعال'},
                    {'value': '{hours}', 'label': 'ساعت آموزش'},
                    {'value': '{lessons}', 'label': 'درس منتشرشده'},
                ]}}]],
            },
            {'id': 'd1_teach', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'd1_w6', 'type': 'teachers', 'data': {'title': '👨‍🏫 اساتید برتر آکادمی', 'limit': '4', 'columns': '4'}}]],
            },
            {'id': 'd1_testi', 'settings': {'gap': 22, 'py': 60, 'bg': '#ffffff', 'radius': 24}, 'cols': [[
                # نظرات واقعی از پنل مدیریت اضافه می‌شوند — نظر ساختگی ممنوع
                {'id': 'd1_w7', 'type': 'testimonials', 'data': {'columns': '3', 'items': []}}]],
            },
            {'id': 'd1_stories', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'd1_ws', 'type': 'success_stories', 'data': {'title': '🌟 داستان‌های موفقیت دانشجویان', 'limit': '3'}}]],
            },
            {'id': 'd1_cta', 'settings': {'gap': 0, 'py': 30}, 'cols': [[
                {'id': 'd1_w8', 'type': 'cta', 'data': {
                    'title': 'آماده شروع یادگیری هستی؟ 🚀',
                    'text': 'حساب خود را بسازید و از دوره‌های منتشرشده دیدن کنید.',
                    'btn_text': 'ثبت‌نام رایگان', 'btn_url': '/auth/register'}}]],
            },
                        {'id': 'd1_exam', 'settings': {'gap': 0, 'py': 40}, 'cols': [[
                {'id': 'd1_we', 'type': 'exam_cta', 'data': {'title': 'آماده آزمون کنکور؟ 🎯', 'text': 'با شبیه‌ساز آزمون، سوالات تصادفی از بانک سوال را با تایمر تمرین کن.'}}]],
            },
{'id': 'd1_news', 'settings': {'gap': 0, 'py': 20}, 'cols': [[
                {'id': 'd1_w9', 'type': 'newsletter', 'data': {'title': 'عضویت در خبرنامه', 'text': 'جدیدترین دوره‌ها و تخفیف‌ها را از دست ندهید!'}}]],
            },
        ]),

    '2': dict(
        title='صفحه اصلی — مینیمال',
        desc='تیتر ساده + نماد اعتماد + گرید دوره‌ها + آمار + وبلاگ',
        settings={'seo_title': 'آکادمی آنلاین — یادگیری ساده و حرفه‌ای'},
        rows=[
            {'id': 'd2_hero', 'settings': {'gap': 0, 'py': 70}, 'cols': [[
                {'id': 'd2_w1', 'type': 'heading', 'data': {'text': 'یادگیری را ساده شروع کن', 'tag': 'h1', 'align': 'center', 'color': '#14283c', 'mb': '12'}},
                {'id': 'd2_w2', 'type': 'text', 'data': {'content': 'دسترسی به بهترین دوره‌های آموزشی فارسی — هر زمان، هر مکان.', 'align': 'center', 'color': '#4a5a6a', 'size': '16'}},
                {'id': 'd2_w3', 'type': 'button', 'data': {'text': 'مشاهده دوره‌ها', 'url': '/courses', 'style': 'primary', 'size': 'lg', 'align': 'center'}},
            ]]},
            {'id': 'd2_trust', 'settings': {'gap': 0, 'py': 30}, 'cols': [[
                {'id': 'd2_w4', 'type': 'trust_badges', 'data': {'size': '70', 'items': [
                    {'type': 'enamad'}, {'type': 'samandehi'}, {'type': 'etehadiye'}]}}]],
            },
            {'id': 'd2_courses', 'settings': {'gap': 24, 'py': 60}, 'cols': [[
                {'id': 'd2_w5', 'type': 'courses', 'data': {'title': 'دوره‌های محبوب', 'limit': '8', 'columns': '4', 'sort': 'newest'}}]],
            },
            {'id': 'd2_stats', 'settings': {'gap': 0, 'py': 50}, 'cols': [[
                {'id': 'd2_w6', 'type': 'stats', 'data': {'columns': '4', 'items': [
                    {'value': '{students}', 'label': 'دانشجو'}, {'value': '{courses}', 'label': 'دوره'},
                    {'value': '{teachers}', 'label': 'مدرس'}, {'value': '{lessons}', 'label': 'درس'}]}}]],
            },
            {'id': 'd2_posts', 'settings': {'gap': 24, 'py': 60, 'bg': '#ffffff', 'radius': 24}, 'cols': [[
                {'id': 'd2_w7', 'type': 'posts', 'data': {'title': 'آخرین مقالات', 'limit': '3', 'columns': '3'}}]],
            },
            {'id': 'd2_stories', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'd2_ws', 'type': 'success_stories', 'data': {'title': '🌟 داستان‌های موفقیت دانشجویان', 'limit': '3'}}]],
            },
                        {'id': 'd2_exam', 'settings': {'gap': 0, 'py': 40}, 'cols': [[
                {'id': 'd2_we', 'type': 'exam_cta', 'data': {'title': 'آماده آزمون کنکور؟ 🎯', 'text': 'با شبیه‌ساز آزمون، سوالات تصادفی از بانک سوال را با تایمر تمرین کن.'}}]],
            },
{'id': 'd2_cta', 'settings': {'gap': 0, 'py': 30}, 'cols': [[
                {'id': 'd2_w8', 'type': 'cta', 'data': {'title': 'شروع کن 🚀', 'text': 'همین امروز مسیر یادگیری‌ات را بساز.', 'btn_text': 'ثبت‌نام', 'btn_url': '/auth/register'}}]],
            },
        ]),

    '3': dict(
        title='صفحه اصلی — ویدیویی',
        desc='ویدیو پس‌زمینه + شمارنده‌ها + دوره‌ها + قیمت‌گذاری',
        settings={'seo_title': 'آکادمی آنلاین — آموزش ویدیویی مدرن'},
        rows=[
            {'id': 'd3_vb', 'settings': {'gap': 0, 'py': 0}, 'cols': [[
                {'id': 'd3_w1', 'type': 'video_bg', 'data': {
                    'title': 'تجربه یادگیری مدرن',
                    'sub': 'دوره‌های ویدیویی باکیفیت، پروژه‌محور و همیشه در دسترس',
                    'btn_text': 'شروع یادگیری', 'btn_url': '/courses'}}]],
            },
            {'id': 'd3_count', 'settings': {'gap': 0, 'py': 50}, 'cols': [[
                {'id': 'd3_w2', 'type': 'stats', 'data': {'columns': '4', 'items': [
                    {'value': '{courses}', 'label': 'دوره منتشرشده'},
                    {'value': '{students}', 'label': 'دانشجو'},
                    {'value': '{hours}', 'label': 'ساعت آموزش'},
                    {'value': '{teachers}', 'label': 'مدرس'}]}}]],
            },
            {'id': 'd3_courses', 'settings': {'gap': 24, 'py': 60}, 'cols': [[
                {'id': 'd3_w3', 'type': 'courses', 'data': {'title': 'دوره‌های ویژه', 'limit': '8', 'columns': '4', 'sort': 'popular'}}]],
            },
            {'id': 'd3_testi', 'settings': {'gap': 22, 'py': 60, 'bg': '#ffffff', 'radius': 24}, 'cols': [[
                {'id': 'd3_w4', 'type': 'testimonials', 'data': {'columns': '3', 'items': []}}]],
            },
            {'id': 'd3_stories', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'd3_ws', 'type': 'success_stories', 'data': {'title': '🌟 داستان‌های موفقیت دانشجویان', 'limit': '3'}}]],
            },
            {'id': 'd3_price', 'settings': {'gap': 24, 'py': 60}, 'cols': [[
                {'id': 'd3_w5', 'type': 'courses', 'data': {'title': 'تازه‌ترین دوره‌ها', 'subtitle': 'اطلاعات واقعی از دوره‌های منتشرشده', 'limit': '4', 'columns': '4', 'sort': 'newest'}}]],
            },
                        {'id': 'd3_exam', 'settings': {'gap': 0, 'py': 40}, 'cols': [[
                {'id': 'd3_we', 'type': 'exam_cta', 'data': {'title': 'آماده آزمون کنکور؟ 🎯', 'text': 'با شبیه‌ساز آزمون، سوالات تصادفی از بانک سوال را با تایمر تمرین کن.'}}]],
            },
{'id': 'd3_news', 'settings': {'gap': 0, 'py': 20}, 'cols': [[
                {'id': 'd3_w6', 'type': 'newsletter', 'data': {}}]],
            },
        ]),

    '4': dict(
        title='صفحه اصلی — فروشگاهی',
        desc='اسلایدر فروش + محصولات تخفیف‌دار + نماد اعتماد + ویژگی‌ها',
        settings={'seo_title': 'آکادمی آنلاین — فروشگاه دوره‌های آموزشی'},
        rows=[
            {'id': 'd4_slider', 'settings': {'gap': 0, 'py': 0}, 'cols': [[
                {'id': 'd4_w1', 'type': 'slider', 'data': {
                    'height': '420', 'autoplay': True, 'interval': '6', 'dots': True, 'arrows': True,
                    'slides': [
                        {'img': 'cover-django.webp', 'title': 'دوره‌های منتشرشده', 'sub': 'سرفصل و شرایط هر دوره را پیش از ثبت‌نام بررسی کنید.', 'btn_text': 'مشاهده دوره‌ها', 'btn_url': '/courses?sort=cheap', 'align': 'center'},
                        {'img': 'cover-python.webp', 'title': 'مسیر یادگیری خود را شروع کنید', 'sub': 'دوره‌های موجود را بر اساس نیاز خود مقایسه کنید.', 'btn_text': 'مشاهده', 'btn_url': '/courses', 'align': 'right'},
                    ]}}]],
            },
            {'id': 'd4_products', 'settings': {'gap': 24, 'py': 60}, 'cols': [[
                {'id': 'd4_w2', 'type': 'products', 'data': {'title': '🔥 دوره‌های تخفیف‌دار', 'filter': 'sale', 'limit': '8', 'columns': '4'}}]],
            },
            {'id': 'd4_trust', 'settings': {'gap': 0, 'py': 40, 'bg': '#ffffff', 'radius': 20}, 'cols': [[
                {'id': 'd4_w3', 'type': 'trust_badges', 'data': {'size': '80', 'items': [
                    {'type': 'enamad'}, {'type': 'samandehi'}, {'type': 'etehadiye'}]}}]],
            },
            {'id': 'd4_feat', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'd4_w4', 'type': 'feature', 'data': {'columns': '4', 'items': [
                    {'icon': '📚', 'title': 'اطلاعات دوره', 'text': 'سرفصل، مدرس و مدت ثبت‌شده'},
                    {'icon': '💰', 'title': 'قیمت شفاف', 'text': 'نمایش مبلغ نهایی پیش از پرداخت'},
                    {'icon': '🛡️', 'title': 'روش پرداخت فعال', 'text': 'فقط درگاه‌های تکمیل‌شده'},
                    {'icon': '👤', 'title': 'حساب کاربری', 'text': 'پیگیری سفارش و دسترسی‌ها'}]}}]],
            },
            {'id': 'd4_stories', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'd4_ws', 'type': 'success_stories', 'data': {'title': '🌟 داستان‌های موفقیت دانشجویان', 'limit': '3'}}]],
            },
                        {'id': 'd4_exam', 'settings': {'gap': 0, 'py': 40}, 'cols': [[
                {'id': 'd4_we', 'type': 'exam_cta', 'data': {'title': 'آماده آزمون کنکور؟ 🎯', 'text': 'با شبیه‌ساز آزمون، سوالات تصادفی از بانک سوال را با تایمر تمرین کن.'}}]],
            },
{'id': 'd4_cta', 'settings': {'gap': 0, 'py': 30}, 'cols': [[
                {'id': 'd4_w5', 'type': 'cta', 'data': {'title': 'دوره مناسب خود را پیدا کنید', 'text': 'دوره‌ها را بر اساس موضوع، سطح و قیمت مقایسه کنید.', 'btn_text': 'مشاهده دوره‌ها', 'btn_url': '/courses'}}]],
            },
        ]),

    '5': dict(
        title='صفحه اصلی — آکادمیک',
        desc='تیتر بزرگ + مسیر یادگیری + دسته‌ها + اساتید + سوالات متداول',
        settings={'seo_title': 'آکادمی آنلاین — دانشگاه آنلاین مهارت‌ها'},
        rows=[
            {'id': 'd5_hero', 'settings': {'gap': 0, 'py': 70}, 'cols': [[
                {'id': 'd5_w1', 'type': 'heading', 'data': {'text': 'دانشگاه آنلاین مهارت‌ها', 'tag': 'h1', 'align': 'center', 'color': '#14283c', 'mb': '12'}},
                {'id': 'd5_w2', 'type': 'text', 'data': {'content': 'با مسیرهای یادگیری هدفمند، از مبتدی به حرفه‌ای برس.', 'align': 'center', 'color': '#4a5a6a', 'size': '16'}},
                {'id': 'd5_w3', 'type': 'button', 'data': {'text': 'شروع مسیر یادگیری', 'url': '/courses', 'style': 'accent', 'size': 'lg', 'align': 'center'}},
            ]]},
            {'id': 'd5_cats', 'settings': {'gap': 16, 'py': 60}, 'cols': [[
                {'id': 'd5_w4', 'type': 'categories', 'data': {'title': 'مسیرهای یادگیری', 'limit': '9', 'columns': '4'}}]],
            },
            {'id': 'd5_courses', 'settings': {'gap': 24, 'py': 60, 'bg': '#ffffff', 'radius': 24}, 'cols': [[
                {'id': 'd5_w5', 'type': 'courses', 'data': {'title': 'جدیدترین دوره‌ها', 'limit': '8', 'columns': '4', 'sort': 'newest'}}]],
            },
            {'id': 'd5_teach', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'd5_w6', 'type': 'teachers', 'data': {'title': 'مدرسان', 'limit': '4', 'columns': '4'}}]],
            },
            {'id': 'd5_faq', 'settings': {'gap': 0, 'py': 60}, 'cols': [[
                {'id': 'd5_w7', 'type': 'faq', 'data': {'title': 'پرسش‌های متداول', 'items': [
                    {'q': 'چگونه دوره بخرم؟', 'a': 'دوره را به سبد اضافه کنید و یکی از روش‌های پرداخت فعال را انتخاب کنید.'},
                    {'q': 'دوره‌های خریداری‌شده کجا هستند؟', 'a': 'پس از تایید پرداخت در بخش دوره‌های من نمایش داده می‌شوند.'},
                    {'q': 'گواهی پایان دوره چگونه است؟', 'a': 'پس از تکمیل دوره با کد رهگیری قابل استعلام صادر می‌شود.'}]}}]],
            },
            {'id': 'd5_stories', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'd5_ws', 'type': 'success_stories', 'data': {'title': '🌟 داستان‌های موفقیت دانشجویان', 'limit': '3'}}]],
            },
                        {'id': 'd5_exam', 'settings': {'gap': 0, 'py': 40}, 'cols': [[
                {'id': 'd5_we', 'type': 'exam_cta', 'data': {'title': 'آماده آزمون کنکور؟ 🎯', 'text': 'با شبیه‌ساز آزمون، سوالات تصادفی از بانک سوال را با تایمر تمرین کن.'}}]],
            },
            {'id': 'd5_cta', 'settings': {'gap': 0, 'py': 30}, 'cols': [[
                {'id': 'd5_w8', 'type': 'cta', 'data': {'title': 'حساب یادگیری خود را بسازید 🎓', 'text': 'ثبت‌نام کنید و دوره‌های منتشرشده را در یک پنل مدیریت کنید.', 'btn_text': 'ثبت‌نام', 'btn_url': '/auth/register'}}]],
            },
        ]),

    '6': dict(
        title='صفحه اصلی — فرادرس/لیموناد',
        desc='هیرو با نوار جستجو + دسته‌ها + کارت‌های درشت دوره + آمار + اساتید + خبرنامه (الهام‌گرفته از فرادرس و لیموناد)',
        settings={'seo_title': 'آکادمی آنلاین — آموزش آنلاین با ضبط جلسات و گواهی معتبر'},
        rows=[
            {'id': 'd6_hero', 'settings': {'gap': 0, 'py': 0}, 'cols': [[
                {'id': 'd6_w1', 'type': 'slider', 'data': {
                    'height': '500', 'overlay': '70', 'radius': '0', 'autoplay': False,
                    'interval': '6', 'dots': False, 'arrows': False, 'swipe': True,
                    'search': True,
                    'search_hint': 'مثلاً «پایتون» — جستجو در عنوان و سرفصل دوره‌ها',
                    'slides': [
                        {'img': 'hero.webp', 'title': 'همین امروز یادگیری را شروع کنید', 'sub': 'آموزش‌های گام‌به‌گام فارسی با پروژه واقعی، مدرس متخصص و گواهی قابل استعلام', 'align': 'center'},
                        {'img': 'cover-python.webp', 'title': 'از صفر تا اولین پروژه', 'sub': 'مسیر یادگیری منظم با تمرین و پشتیبانی تیکت', 'btn_text': 'مشاهده همه دوره‌ها', 'btn_url': '/courses', 'align': 'center'},
                    ]}}]],
            },
            {'id': 'd6_cats', 'settings': {'gap': 14, 'py': 56, 'bg': '#ffffff', 'radius': 0}, 'cols': [[
                {'id': 'd6_w2', 'type': 'categories', 'data': {'title': 'موضوع موردعلاقه‌ات را انتخاب کن', 'limit': '12', 'columns': '6'}}]],
            },
            {'id': 'd6_courses', 'settings': {'gap': 24, 'py': 64}, 'cols': [[
                {'id': 'd6_w3', 'type': 'courses', 'data': {'title': 'جدیدترین دوره‌های آموزشی', 'subtitle': 'سرفصل، مدرس و نظرات دانشجویان را ببینید و مقایسه کنید', 'limit': '9', 'columns': '3', 'sort': 'newest', 'link_text': 'مشاهده همه دوره‌ها', 'link_url': '/courses'}}]],
            },
            {'id': 'd6_feat', 'settings': {'gap': 22, 'py': 56, 'bg': '#ffffff', 'radius': 0}, 'cols': [[
                {'id': 'd6_w4', 'type': 'feature', 'data': {'columns': '4', 'items': [
                    {'icon': '🎬', 'title': 'ضبط جلسات', 'text': 'جلسات برگزارشده با زیرنویس در همان‌جا پخش می‌شود'},
                    {'icon': '🏅', 'title': 'گواهی معتبر', 'text': 'کد رهگیری منحصربه‌فرد و قابل استعلام'},
                    {'icon': '👨‍🏫', 'title': 'مدرس متخصص', 'text': 'معرفی کامل مدرس پیش از ثبت‌نام'},
                    {'icon': '💬', 'title': 'پشتیبانی تیکت', 'text': 'پیگیری درخواست از داخل حساب کاربری'}]}}]],
            },
            {'id': 'd6_stats', 'settings': {'gap': 0, 'py': 50}, 'cols': [[
                {'id': 'd6_w5', 'type': 'stats', 'data': {'columns': '4', 'items': [
                    {'value': '{courses}', 'label': 'دوره آموزشی'},
                    {'value': '{students}', 'label': 'دانشجوی فعال'},
                    {'value': '{hours}', 'label': 'ساعت آموزش'},
                    {'value': '{lessons}', 'label': 'درس منتشرشده'}]}}]],
            },
            {'id': 'd6_teach', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'd6_w6', 'type': 'teachers', 'data': {'title': 'اساتید آکادمی', 'limit': '4', 'columns': '4'}}]],
            },
            {'id': 'd6_stories', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'd6_ws', 'type': 'success_stories', 'data': {'title': '🌟 داستان‌های موفقیت دانشجویان', 'limit': '3'}}]],
            },
            {'id': 'd6_news', 'settings': {'gap': 0, 'py': 56, 'bg': '#ffffff', 'radius': 0}, 'cols': [[
                {'id': 'd6_w7', 'type': 'newsletter', 'data': {'title': 'از تخفیف‌ها و دوره‌های جدید زودتر باخبر شو', 'text': 'عضویت در خبرنامه — بدون اسپم، انصراف یک‌کلیکی', 'btn_text': 'عضویت خبرنامه'}}]],
            },
        ]),

    'amoozino': dict(
        title='صفحه اصلی — آموزینو (Amoozino)',
        desc='هیرو آموزینو با دکمه مشاوره + خدمات تخصصی + دوره‌های ویدیویی + درباره آموزینو و سفارش پروژه + محصولات دانلودی + صدای هنرجویان + مقالات دانش روز',
        settings={'seo_title': 'آموزینو — پلتفرم آموزش آنلاین و فروش دوره و فایل آموزشی'},
        rows=[
            {'id': 'amz_hero', 'settings': {'gap': 0, 'py': 0}, 'cols': [[
                {'id': 'amz_w1', 'type': 'slider', 'data': {
                    'height': '460', 'autoplay': True, 'interval': '6', 'dots': True, 'arrows': True, 'swipe': True,
                    'slides': [
                        {'img': 'hero.webp', 'title': 'آموزش تخصصی و دوره‌های جامع آنلاین',
                         'sub': 'با شرکت در دوره‌های آموزینو به راحتی مهارت دلخواهت رو یاد بگیر و وارد بازار کار شو! قدم به قدم کنارتیم.',
                         'btn_text': 'مشاهده دوره‌ها', 'btn_url': '/courses', 'align': 'right'},
                        {'img': 'cover-flask.webp', 'title': 'فروش فایل‌ها، پکیج‌ها و محصولات دانلودی',
                         'sub': 'کتاب‌های الکترونیکی، جزوات تخصصی، سورس کدهای پروژه‌محور با دریافت آنی لینک دانلود.',
                         'btn_text': 'فروشگاه فایل و محصولات', 'btn_url': '/products', 'align': 'center'},
                    ]}}]],
            },
            {'id': 'amz_cats', 'settings': {'gap': 16, 'py': 50, 'bg': '#ffffff', 'radius': 24}, 'cols': [[
                {'id': 'amz_w2', 'type': 'categories', 'data': {'title': '✨ خدمات و دسته‌بندی‌های تخصصی', 'limit': '8', 'columns': '4'}}]],
            },
            {'id': 'amz_courses', 'settings': {'gap': 24, 'py': 60}, 'cols': [[
                {'id': 'amz_w3', 'type': 'courses', 'data': {'title': '🎓 دوره‌های آموزشی آنلاین', 'subtitle': 'دوره‌های ویدیویی با سرفصل‌بندی دقیق و پشتیبانی مدرس', 'limit': '8', 'columns': '4', 'sort': 'newest'}}]],
            },
            {'id': 'amz_feat', 'settings': {'gap': 22, 'py': 60, 'bg': '#ffffff', 'radius': 24}, 'cols': [[
                {'id': 'amz_w4', 'type': 'feature', 'data': {'columns': '4', 'items': [
                    {'icon': '🎬', 'title': 'ویدیو پلیر محافظت‌شده', 'text': 'پخش روان آنلاین بدون امکان دانلود غیرمجاز با واترمارک امنیتی'},
                    {'icon': '📦', 'title': 'فروش فایل و پکیج', 'text': 'امکان دانلود مستقیم فایل‌ها، جزوات PDF و سورس کدها پس از خرید'},
                    {'icon': '💳', 'title': 'پرداخت آنلاین و اقساطی', 'text': 'اتصال به درگاه‌های بانکی عضو شتاب و سرویس‌های پرداخت اقساطی'},
                    {'icon': '👨‍🏫', 'title': 'پنل اختصاصی اساتید', 'text': 'امکان جذب و مدیریت مدرسین با تسویه‌حساب و پنل مجزا'}
                ]}}]],
            },
            {'id': 'amz_prods', 'settings': {'gap': 24, 'py': 60}, 'cols': [[
                {'id': 'amz_w5', 'type': 'products', 'data': {'title': '📦 محصولات، پکیج‌ها و فایل‌های دانلودی', 'filter': 'all', 'limit': '4', 'columns': '4'}}]],
            },
            {'id': 'amz_stats', 'settings': {'gap': 0, 'py': 50}, 'cols': [[
                {'id': 'amz_w6', 'type': 'stats', 'data': {'columns': '4', 'items': [
                    {'value': '{courses}', 'label': 'دوره آموزشی'},
                    {'value': '{students}', 'label': 'هنرجوی موفق'},
                    {'value': '{hours}', 'label': 'ساعت آموزش'},
                    {'value': '{lessons}', 'label': 'جلسه تدوین‌شده'},
                ]}}]],
            },
            {'id': 'amz_testi', 'settings': {'gap': 22, 'py': 60, 'bg': '#ffffff', 'radius': 24}, 'cols': [[
                {'id': 'amz_w7', 'type': 'testimonials', 'data': {'columns': '3', 'items': []}}]],
            },
            {'id': 'amz_posts', 'settings': {'gap': 24, 'py': 60}, 'cols': [[
                {'id': 'amz_w8', 'type': 'posts', 'data': {'title': '📰 دانش روز — آخرین مقالات و آموزش‌ها', 'limit': '3', 'columns': '3'}}]],
            },
            {'id': 'amz_cta', 'settings': {'gap': 0, 'py': 30}, 'cols': [[
                {'id': 'amz_w9', 'type': 'cta', 'data': {
                    'title': 'آماده شروع یادگیری با آموزینو هستید؟ 🚀',
                    'text': 'همین الان حساب کاربری خود را بسازید و به هزاران هنرجوی موفق بپیوندید.',
                    'btn_text': 'ثبت‌نام و شروع یادگیری', 'btn_url': '/auth/register'}}]],
            },
        ]),

    # ------------------------------------------------------------
    # طرح ۶ — مدرن ۲۰۲۶ (دیزاین سیستم v2)
    # سازه‌های اختصاصی: معرفی برند، مسیر یادگیری، باکس اعتماد،
    # پیشنهادهای ویژهٔ پویا، گواهی‌ها، عضویت ویژه و …
    # ------------------------------------------------------------
    '6': dict(
        title='صفحه اصلی — مدرن ۲۰۲۶',
        desc='هیرو متنی + معرفی برند + دسته‌ها + پیشنهاد ویژهٔ پویا + مسیر یادگیری + دوره‌ها + گواهی‌ها + نظرات + FAQ + CTA',
        settings={'seo_title': 'آکادمی آنلاین — یادگیری حرفه‌ای، مسیر روشن'},
        rows=[
            {'id': 'm6_hero', 'settings': {'gap': 0, 'py': 70}, 'cols': [[
                {'id': 'm6_h1', 'type': 'heading', 'data': {
                    'text': 'مسیر یادگیری حرفه‌ای‌ات را از همین‌جا شروع کن',
                    'tag': 'h1', 'align': 'center', 'mb': '12'}},
                {'id': 'm6_h2', 'type': 'text', 'data': {
                    'content': 'دوره‌های تخصصی با سرفصل شفاف، مدرس واقعی و پشتیبانی پاسخ‌گو — آنلاین و آفلاین.',
                    'align': 'center', 'size': '16'}},
                {'id': 'm6_h3', 'type': 'course_search', 'data': {}},
            ]]},
            {'id': 'm6_trust', 'settings': {'gap': 16, 'py': 30}, 'cols': [[
                {'id': 'm6_t1', 'type': 'trust_box', 'data': {'columns': '4', 'items': [
                    {'icon': '↩️', 'title': 'ضمانت بازگشت وجه', 'text': 'تا ۷ روز اول، بدون قید و شرط'},
                    {'icon': '💳', 'title': 'پرداخت امن', 'text': 'درگاه بانکی رسمی و رمز پویا'},
                    {'icon': '🎧', 'title': 'پشتیبانی پاسخ‌گو', 'text': 'پاسخ تیکت زیر ۲۴ ساعت کاری'},
                    {'icon': '♾️', 'title': 'دسترسی دائمی', 'text': 'بعد از خرید، همیشه در پنل شما'},
                ]}}]],
            },
            {'id': 'm6_brand', 'settings': {'gap': 30, 'py': 60}, 'cols': [[
                {'id': 'm6_b1', 'type': 'brand_intro', 'data': {
                    'eyebrow': 'چرا این آکادمی؟',
                    'title': 'آکادمی‌ای که فقط دوره نمی‌فروشد؛ مسیر می‌سازد',
                    'subtitle': 'از انتخاب درست مهارت تا پروژهٔ پایانی و ورود به بازار کار، کنار شما هستیم.',
                    'media': 'hero.webp',
                    'media_badge_value': '{students}+',
                    'media_badge_label': 'دانشجوی فعال',
                    'points': 'سرفصل و مدت هر جلسه پیش از خرید مشخص است\nگواهی پایان دوره با کد استعلام رسمی\nپنل پیشرفت یادگیری و یادآوری تمرین‌ها\nباشگاه دانشجویی و پرسش‌وپاسخ با مدرس',
                    'btn_text': 'آشنایی بیشتر با آکادمی', 'btn_url': '/about',
                    'btn2_text': 'مشاهده دوره‌ها', 'btn2_url': '/courses',
                    'layout': 'image-left',
                    'stats': [
                        {'icon': '🎓', 'value': '{courses}', 'label': 'دوره منتشرشده'},
                        {'icon': '⏱', 'value': '{hours}', 'label': 'ساعت آموزش'},
                        {'icon': '📚', 'value': '{lessons}', 'label': 'جلسه آموزشی'},
                    ]}}]],
            },
            {'id': 'm6_cats', 'settings': {'gap': 16, 'py': 50}, 'cols': [[
                {'id': 'm6_c1', 'type': 'categories', 'data': {
                    'title': 'از کجا شروع کنیم؟', 'limit': '8', 'columns': '4'}}]],
            },
            {'id': 'm6_offers', 'settings': {'gap': 24, 'py': 50}, 'cols': [[
                {'id': 'm6_o1', 'type': 'special_offers', 'data': {
                    'title': 'پیشنهادهای ویژه',
                    'subtitle': 'تخفیف‌های واقعی روی دوره‌های منتشرشده — تا پایان مهلت',
                    'limit': '4', 'columns': '4',
                    'btn_text': 'مشاهده همه تخفیف‌ها', 'btn_url': '/courses?sort=cheap'}}]],
            },
            {'id': 'm6_path', 'settings': {'gap': 24, 'py': 60, 'bg': '#ffffff', 'radius': 24}, 'cols': [[
                {'id': 'm6_p1', 'type': 'learning_path', 'data': {
                    'eyebrow': 'مسیر یادگیری',
                    'title': 'گام‌به‌گام تا تخصص',
                    'subtitle': 'هر مسیر چند دورهٔ مرتبط دارد؛ به ترتیب جلو بروید.',
                    'columns': '4',
                    'steps': [
                        {'title': 'شروع و آشنایی', 'text': 'مبانی و مفاهیم پایه با زبان ساده', 'chip': '۲ تا ۳ دوره', 'state': ''},
                        {'title': 'تثبیت مهارت', 'text': 'تمرین‌های هدفمند و پروژه‌های کوچک', 'chip': 'پروژه‌محور', 'state': ''},
                        {'title': 'پروژهٔ واقعی', 'text': 'ساخت نمونه‌کار قابل ارائه به کارفرما', 'chip': 'مربی‌دار', 'state': ''},
                        {'title': 'ورود به بازار کار', 'text': 'رزومه، مصاحبه و معرفی به فرصت‌ها', 'chip': 'همراهی شغلی', 'state': ''},
                    ]}}]],
            },
            {'id': 'm6_courses', 'settings': {'gap': 24, 'py': 60}, 'cols': [[
                {'id': 'm6_cr1', 'type': 'courses', 'data': {
                    'title': 'دوره‌های منتشرشده',
                    'subtitle': 'سرفصل، مدرس و قیمت هر دوره را مقایسه کنید',
                    'limit': '8', 'columns': '4', 'sort': 'newest'}}]],
            },
            {'id': 'm6_teach', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'm6_te1', 'type': 'teachers', 'data': {
                    'title': 'اساتید آکادمی', 'limit': '4', 'columns': '4'}}]],
            },
            {'id': 'm6_certs', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'm6_ce1', 'type': 'certificates', 'data': {
                    'eyebrow': 'مدرک معتبر',
                    'title': 'گواهی پایان دوره، قابل استعلام',
                    'subtitle': 'پس از تکمیل دوره، گواهی با کد رهگیری صادر می‌شود.',
                    'columns': '3',
                    'items': [
                        {'icon': '🏅', 'title': 'گواهی پایان دوره', 'text': 'با نام دانشجو، عنوان دوره و ساعت آموزش'},
                        {'icon': '🛡', 'title': 'کد استعلام رسمی', 'text': 'کارفرما می‌تواند اصالت گواهی را بررسی کند'},
                        {'icon': '📈', 'title': 'کارنامهٔ یادگیری', 'text': 'درصد پیشرفت و نمرهٔ آزمون‌ها در پنل شما'},
                    ],
                    'verify_text': 'استعلام گواهینامه', 'verify_url': '/verify-certificate'}}]],
            },
            {'id': 'm6_testi', 'settings': {'gap': 22, 'py': 60, 'bg': '#ffffff', 'radius': 24}, 'cols': [[
                {'id': 'm6_ti1', 'type': 'reviews', 'data': {
                    'title': 'نظرات واقعی دانشجویان', 'limit': '6'}}]],
            },
            {'id': 'm6_faq', 'settings': {'gap': 0, 'py': 60}, 'cols': [[
                {'id': 'm6_f1', 'type': 'faq', 'data': {
                    'title': 'سوالات متداول', 'items': [
                        {'q': 'دوره‌ها به‌صورت آنلاین است یا حضوری؟',
                         'a': 'هر دو! نوع ارائه (آنلاین/آفلاین/حضوری) در صفحهٔ هر دوره مشخص شده است.'},
                        {'q': 'پس از خرید چقدر دسترسی دارم؟',
                         'a': 'دسترسی به محتوای دوره در پنل کاربری شما دائمی است مگر خلاف آن در صفحهٔ دوره ذکر شود.'},
                        {'q': 'اگر از دوره راضی نباشم چه؟',
                         'a': 'تا ۷ روز اول امکان درخواست بازگشت وجه از طریق پنل کاربری وجود دارد.'},
                        {'q': 'گواهی پایان دوره معتبر است؟',
                         'a': 'بله؛ گواهی دارای کد رهگیری است و از صفحهٔ استعلام گواهینامه قابل بررسی است.'},
                    ]}}]],
            },
            {'id': 'm6_cta', 'settings': {'gap': 0, 'py': 30}, 'cols': [[
                {'id': 'm6_ct1', 'type': 'cta', 'data': {
                    'title': 'همین امروز شروع کن 🚀',
                    'text': 'حساب رایگان بساز، دوره‌ها را ببین و اولین جلسه را رایگان تماشا کن.',
                    'btn_text': 'ثبت‌نام رایگان', 'btn_url': '/auth/register'}}]],
            },
        ]),
}

HOME_DESIGN_NAMES = {k: v['title'] for k, v in HOME_DESIGNS.items()}
