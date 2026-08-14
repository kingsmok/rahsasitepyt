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
                        {'img': 'hero.webp', 'title': 'آینده‌ات را با مهارت‌های دیجیتال قدرتمندتر بساز',
                         'sub': 'دوره‌های پروژه‌محور با برترین مدرسان ایران — همین امروز شروع کن!',
                         'btn_text': '🚀 مشاهده همه دوره‌ها', 'btn_url': '/courses', 'align': 'right'},
                        {'img': 'cover-python.webp', 'title': 'دوره جامع پایتون با تخفیف ویژه',
                         'sub': 'از صفر تا استخدام — با کد WELCOME20 تخفیف بگیرید!',
                         'btn_text': 'مشاهده دوره پایتون', 'btn_url': '/courses', 'align': 'center'},
                    ]}}]],
            },
            {'id': 'd1_feat', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'd1_w2', 'type': 'feature', 'data': {'columns': '3', 'items': [
                    {'icon': '🎬', 'title': 'ویدیوهای باکیفیت', 'text': 'تدریس قدم‌به‌قدم Full HD با دسترسی مادام‌العمر'},
                    {'icon': '🏅', 'title': 'گواهینامه معتبر', 'text': 'دریافت گواهی پایان دوره با کد رهگیری'},
                    {'icon': '🎓', 'title': 'اساتید حرفه‌ای', 'text': 'همکاری با برترین مدرسان بازار'},
                    {'icon': '🧩', 'title': 'پروژه‌محور', 'text': 'یادگیری با ساخت پروژه‌های واقعی'},
                    {'icon': '💬', 'title': 'پشتیبانی فعال', 'text': 'پاسخگویی سریع در تیکت و پیام‌رسان‌ها'},
                    {'icon': '🛡️', 'title': 'پرداخت امن', 'text': 'درگاه‌های معتبر با ضمانت بازگشت وجه'},
                ]}}]],
            },
            {'id': 'd1_cats', 'settings': {'gap': 16, 'py': 60, 'bg': '#ffffff', 'radius': 24}, 'cols': [[
                {'id': 'd1_w3', 'type': 'categories', 'data': {'title': 'موضوع مورد علاقه‌ات را انتخاب کن', 'limit': '9', 'columns': '4'}}]],
            },
            {'id': 'd1_courses', 'settings': {'gap': 24, 'py': 60}, 'cols': [[
                {'id': 'd1_w4', 'type': 'courses', 'data': {'title': '⭐ پرفروش‌ترین دوره‌ها', 'subtitle': 'انتخاب بیشتر دانشجویان', 'limit': '8', 'columns': '4', 'sort': 'popular'}}]],
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
                    'text': 'همین حالا ثبت‌نام کن و با کد WELCOME20 از تخفیف بهره‌مند شو!',
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
                {'id': 'd3_w2', 'type': 'counter', 'data': {'columns': '4', 'color': '#f2640c', 'items': [
                    {'target': '150', 'suffix': '+', 'label': 'دوره'},
                    {'target': '50000', 'suffix': '+', 'label': 'دانشجو'},
                    {'target': '2000', 'suffix': '+', 'label': 'ساعت ویدیو'},
                    {'target': '120', 'suffix': '+', 'label': 'مدرس'}]}}]],
            },
            {'id': 'd3_courses', 'settings': {'gap': 24, 'py': 60}, 'cols': [[
                {'id': 'd3_w3', 'type': 'courses', 'data': {'title': 'دوره‌های ویژه', 'limit': '8', 'columns': '4', 'sort': 'popular'}}]],
            },
            {'id': 'd3_testi', 'settings': {'gap': 22, 'py': 60, 'bg': '#ffffff', 'radius': 24}, 'cols': [[
                {'id': 'd3_w4', 'type': 'testimonials', 'data': {'columns': '3', 'items': [
                    {'name': 'رضا موسوی', 'role': 'دانشجوی ML', 'stars': '5', 'color': '#0891b2', 'text': 'کیفیت تدریس فوق‌العاده بود.'},
                    {'name': 'سارا رحیمی', 'role': 'دانشجوی ری‌اکت', 'stars': '5', 'color': '#16a34a', 'text': 'بهترین سرمایه‌گذاری آموزشی من.'}]}}]],
            },
            {'id': 'd3_stories', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'd3_ws', 'type': 'success_stories', 'data': {'title': '🌟 داستان‌های موفقیت دانشجویان', 'limit': '3'}}]],
            },
            {'id': 'd3_price', 'settings': {'gap': 24, 'py': 60}, 'cols': [[
                {'id': 'd3_w5', 'type': 'pricing', 'data': {'columns': '3', 'items': [
                    {'name': 'پایه', 'price': 'رایگان', 'period': 'برای همیشه', 'features': 'دسترسی به دوره‌های رایگان\nگواهینامه رایگان\nپشتیبانی انجمن', 'btn_text': 'شروع رایگان', 'btn_url': '/auth/register'},
                    {'name': 'حرفه‌ای', 'price': '۲۹۰,۰۰۰', 'period': 'ماهانه', 'features': 'دسترسی به همه دوره‌ها\nگواهینامه معتبر\nپشتیبانی تیکت اولویت‌دار', 'btn_text': 'انتخاب', 'btn_url': '/auth/register', 'featured': True},
                    {'name': 'سازمانی', 'price': 'تماس بگیرید', 'period': 'سالیانه', 'features': 'آموزش تیمی\nگزارش پیشرفت\nمدرس اختصاصی', 'btn_text': 'ارتباط', 'btn_url': '/contact'}]}}]],
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
                        {'img': 'cover-django.webp', 'title': 'جشنواره فروش ویژه 🎉', 'sub': 'تا ۵۰٪ تخفیف روی پرفروش‌ترین دوره‌ها — فرصت محدود!', 'btn_text': 'خرید با تخفیف', 'btn_url': '/courses?sort=cheap', 'align': 'center'},
                        {'img': 'cover-python.webp', 'title': 'دوره جامع پایتون', 'sub': 'پرفروش‌ترین دوره آکادمی', 'btn_text': 'مشاهده', 'btn_url': '/courses', 'align': 'right'},
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
                    {'icon': '🚚', 'title': 'دسترسی فوری', 'text': 'بلافاصله پس از پرداخت'},
                    {'icon': '💰', 'title': 'تخفیف دائمی', 'text': 'قیمت‌های رقابتی'},
                    {'icon': '🛡️', 'title': 'ضمانت بازگشت', 'text': 'تا ۷ روز ضمانت'},
                    {'icon': '🎁', 'title': 'هدیه ویژه', 'text': 'برای خریدهای بالای ۱ میلیون'}]}}]],
            },
            {'id': 'd4_stories', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'd4_ws', 'type': 'success_stories', 'data': {'title': '🌟 داستان‌های موفقیت دانشجویان', 'limit': '3'}}]],
            },
                        {'id': 'd4_exam', 'settings': {'gap': 0, 'py': 40}, 'cols': [[
                {'id': 'd4_we', 'type': 'exam_cta', 'data': {'title': 'آماده آزمون کنکور؟ 🎯', 'text': 'با شبیه‌ساز آزمون، سوالات تصادفی از بانک سوال را با تایمر تمرین کن.'}}]],
            },
{'id': 'd4_cta', 'settings': {'gap': 0, 'py': 30}, 'cols': [[
                {'id': 'd4_w5', 'type': 'cta', 'data': {'title': 'پیشنهاد محدود ⏳', 'text': 'همین حالا دوره‌ها را با تخفیف تهیه کن.', 'btn_text': 'مشاهده تخفیف‌ها', 'btn_url': '/courses?sort=cheap'}}]],
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
                {'id': 'd5_w6', 'type': 'teachers', 'data': {'title': 'هیئت علمی', 'limit': '4', 'columns': '4'}}]],
            },
            {'id': 'd5_faq', 'settings': {'gap': 0, 'py': 60}, 'cols': [[
                {'id': 'd5_w7', 'type': 'faq', 'data': {'title': 'پرسش‌های متداول', 'items': [
                    {'q': 'چگونه دوره بخرم؟', 'a': 'دوره را به سبد اضافه کنید و با درگاه امن پرداخت کنید.'},
                    {'q': 'دسترسی تا کی معتبر است؟', 'a': 'مادام‌العمر — با همه آپدیت‌های بعدی.'},
                    {'q': 'گواهینامه دارید؟', 'a': 'بله، با کد رهگیری منحصربه‌فرد.'}]}}]],
            },
            {'id': 'd5_stories', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
                {'id': 'd5_ws', 'type': 'success_stories', 'data': {'title': '🌟 داستان‌های موفقیت دانشجویان', 'limit': '3'}}]],
            },
                        {'id': 'd5_exam', 'settings': {'gap': 0, 'py': 40}, 'cols': [[
                {'id': 'd5_we', 'type': 'exam_cta', 'data': {'title': 'آماده آزمون کنکور؟ 🎯', 'text': 'با شبیه‌ساز آزمون، سوالات تصادفی از بانک سوال را با تایمر تمرین کن.'}}]],
            },
{'id': 'd5_cta', 'settings': {'gap': 0, 'py': 30}, 'cols': [[
                {'id': 'd5_w8', 'type': 'cta', 'data': {'title': 'به خانواده آکادمی بپیوند 🎓', 'text': 'بیش از ۵۰ هزار دانشجو از ما یاد می‌گیرند.', 'btn_text': 'ثبت‌نام', 'btn_url': '/auth/register'}}]],
            },
        ]),
}

HOME_DESIGN_NAMES = {k: v['title'] for k, v in HOME_DESIGNS.items()}
