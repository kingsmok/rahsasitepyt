# -*- coding: utf-8 -*-
"""داده‌های اولیه دمو برای آکادمی آنلاین"""
from datetime import datetime, timedelta
try:
    from datetime import UTC
except ImportError:  # پایتون < 3.11
    from datetime import timezone as _tz_utc
    UTC = _tz_utc.utc
import random
from validators import gen_national_code
from models import (utcnow, db, User, Category, Course, Section, Lesson, Review, Order,
                    OrderItem, Coupon, Enrollment, BlogPost, BlogComment, Ticket, NewsletterEmail,
                    ContactMessage, Setting, Page)


def slugify(text):
    import re
    text = text.replace(' ', '-')
    text = re.sub(r'[^\w\u0600-\u06FF\-]', '', text)
    return text


def seed():
    print('📦 شروع بارگذاری داده‌های اولیه...')
    # ---------- تنظیمات سایت ----------
    settings = {
        'site_name': 'آکادمی آنلاین',
        'site_desc': 'مرجع تخصصی آموزش‌های آنلاین فارسی — دوره‌های برنامه‌نویسی، طراحی و مهارت‌های دیجیتال',
        'phone': '021-91001234',
        'email': 'info@academy.ir',
        'address': 'تهران، خیابان ولیعصر، برج آکادمی، طبقه ۱۲',
        'telegram': 'academy_ir',
        'instagram': 'academy.ir',
        'default_theme': 'theme-22',
        'sandbox_mode': '0',
        'watermark_enabled': '1',
        'maintenance': '0',
        'allow_register': '1',
        'allow_phone_login': '1',
        'site_design': '1',
        'home_design': '1',
        'about_design': '1',
        'contact_design': '1',
        # سئو
        'seo_title': 'آکادمی آنلاین — مرجع تخصصی آموزش‌های آنلاین فارسی',
        'seo_desc': 'دوره‌های پروژه‌محور برنامه‌نویسی، طراحی و مهارت‌های دیجیتال با برترین مدرسان ایران + گواهینامه معتبر',
        'seo_keywords': 'آموزش آنلاین, دوره برنامه نویسی, آموزش پایتون, آموزش جنگو, آموزش طراحی وب, دوره آموزشی فارسی',
        'seo_author': 'آکادمی آنلاین',
        'seo_twitter': '@academy_ir',
        'ga_code': '',
        'seo_robots_main': 'index,follow',
        'seo_og_image': 'hero.png',
        'zarinpal_merchant': '',
        'currency': 'تومان',
        'support_hours': 'شنبه تا پنجشنبه — ۹ صبح تا ۹ شب',
        'about_text': 'آکادمی آنلاین با بیش از ۵ سال سابقه، بستری حرفه‌ای برای یادگیری مهارت‌های دیجیتال است. ما با همکاری برترین مدرسان کشور، دوره‌های پروژه‌محور و باکیفیتی تولید می‌کنیم تا شما در مسیر پیشرفت شغلی و تحصیلی‌تان قدمی محکم بردارید.',
    }
    for k, v in settings.items():
        if not db.session.get(Setting, k):
            db.session.add(Setting(key=k, value=v))

    # ---------- کاربران ----------
    admin = User(name='مدیر سیستم', email='admin@academy.ir', role='admin',
                 avatar_color='#dc2626', phone='09120000000', national_code=gen_national_code(),
                 bio='مدیر و بنیان‌گذار آکادمی آنلاین')
    admin.set_password('admin123')
    db.session.add(admin)

    demo = User(name='کاربر آزمایشی', email='demo@academy.ir', role='student',
                avatar_color='#2563eb', phone='09120000001', national_code=gen_national_code(),
                bio='دانشجوی نمونه آکادمی')
    demo.set_password('demo123')
    db.session.add(demo)

    teachers_data = [
        ('دکتر سارا محمدی', 'sara@academy.ir', 'برنامه‌نویس ارشد پایتون با ۱۲ سال سابقه؛ مدرس دانشگاه و توسعه‌دهنده سابق دیجی‌کالا', '#7c3aed'),
        ('مهندس امیر رضایی', 'amir@academy.ir', 'توسعه‌دهنده فول‌استک وب؛ متخصص Django و React با بیش از ۱۰۰ پروژه عملی', '#059669'),
        ('مهدی کریمی', 'mehdi@academy.ir', 'متخصص هوش مصنوعی و داده؛ پژوهشگر ML با ۸ سال تجربه در شرکت‌های دانش‌بنیان', '#0891b2'),
        ('نگار حسینی', 'negar@academy.ir', 'طراح محصول و UI/UX؛ ۹ سال تجربه طراحی محصولات دیجیتال در استارتاپ‌ها', '#db2777'),
        ('حسین عابدی', 'hossein@academy.ir', 'مدرس آفیس و اتوماسیون اداری؛ بیش از ۴۰ هزار دانش‌آموز در سراسر کشور', '#ea580c'),
        ('زهرا نادری', 'zahra@academy.ir', 'کارشناس دیجیتال مارکتینگ؛ مدیر مارکتینگ چند برند معتبر ایرانی', '#c026d3'),
    ]
    teachers = []
    for idx, (name, email, bio, color) in enumerate(teachers_data):
        t = User(name=name, email=email, role='teacher', bio=bio, avatar_color=color,
                 phone=f'091200000{10 + idx}', national_code=gen_national_code())
        t.set_password('teacher123')
        db.session.add(t)
        teachers.append(t)

    db.session.flush()

    # ---------- دسته‌بندی‌ها ----------
    cats_data = [
        ('برنامه‌نویسی', 'برنامه-نویسی', '💻', '#2563eb', 'آموزش زبان‌های برنامه‌نویسی از مقدماتی تا پیشرفته'),
        ('وب', 'وب', '🌐', '#059669', 'توسعه وب، فرانت‌اند و بک‌اند'),
        ('هوش مصنوعی', 'هوش-مصنوعی', '🤖', '#7c3aed', 'یادگیری ماشین، دیپ‌لرنینگ و علم داده'),
        ('طراحی', 'طراحی', '🎨', '#db2777', 'طراحی رابط کاربری، تجربه کاربری و گرافیک'),
        ('کسب‌وکار', 'کسب-وکار', '📈', '#ea580c', 'مارکتینگ، فروش و توسعه کسب‌وکار'),
        ('آفیس', 'آفیس', '📊', '#16a34a', 'اکسل، ورد، پاورپوینت و مهارت‌های اداری'),
        ('زبان', 'زبان', '🗣️', '#0ea5e9', 'آموزش زبان انگلیسی و مهارت‌های مکالمه'),
        ('موبایل', 'موبایل', '📱', '#f43f5e', 'توسعه اپلیکیشن اندروید و iOS'),
        ('امنیت', 'امنیت', '🛡️', '#dc2626', 'امنیت اطلاعات و هک اخلاقی'),
    ]
    cats = {}
    for name, slug, icon, color, desc in cats_data:
        c = Category(name=name, slug=slug, icon=icon, color=color, description=desc)
        db.session.add(c)
        db.session.flush()
        cats[slug] = c

    # ---------- دوره‌ها ----------
    courses_data = [
        dict(title='دوره جامع برنامه‌نویسی پایتون', cat='برنامه-نویسی', teacher=0, price=1850000, discount=890000,
             level='مقدماتی', hours=42, image='cover-python.png', featured=True, tags='پایتون, python, برنامه‌نویسی',
             subtitle='از صفر تا استخدام — یادگیری کامل پایتون با پروژه‌های واقعی',
             learn='• نوشتن کدهای تمیز و حرفه‌ای پایتون\n• کار با کتابخانه‌های استاندارد\n• برنامه‌نویسی شیءگرا به زبان ساده\n• ساخت ۶ پروژه عملی از جمله ربات تلگرام و وب‌اسکرپر\n• آمادگی برای بازار کار و مصاحبه',
             req='• آشنایی مقدماتی با کامپیوتر\n• هیچ دانش برنامه‌نویسی لازم نیست!',
             desc='پایتون امروزه محبوب‌ترین زبان برنامه‌نویسی دنیاست. در این دوره جامع، قدم‌به‌قدم از مفاهیم پایه تا مباحث پیشرفته را با پروژه‌های واقعی یاد می‌گیرید. این دوره بر اساس جدیدترین سرفصل‌های آموزشی و نیاز بازار کار ایران و جهان طراحی شده است.'),
        dict(title='توسعه وب با Flask — پروژه‌محور', cat='وب', teacher=1, price=1200000, discount=590000,
             level='متوسط', hours=22, image='cover-flask.png', featured=True, tags='flask, پایتون, وب',
             subtitle='ساخت وب‌سایت‌های مدرن با فریم‌ورک سبک و قدرتمند Flask',
             learn='• آشنایی کامل با Flask و ساختار آن\n• طراحی API با Flask-RESTful\n• اتصال به دیتابیس SQLAlchemy\n• ساخت فروشگاه اینترنتی کامل\n• استقرار پروژه روی سرور',
             req='• آشنایی مقدماتی با پایتون',
             desc='Flask محبوب‌ترین میکروفریم‌ورک پایتون برای توسعه وب است. در این دوره پروژه‌محور، یک فروشگاه اینترنتی کامل را از صفر می‌سازیم و همه مفاهیم را در عمل یاد می‌گیرید.'),
        dict(title='دوره پروژه‌محور Django — فروشگاه اینترنتی', cat='وب', teacher=1, price=2600000, discount=1290000,
             level='متوسط', hours=55, image='cover-django.png', featured=True, tags='django, پایتون, وب',
             subtitle='ساخت فروشگاه اینترنتی واقعی با Django — مناسب بازار کار',
             learn='• معماری MTV در Django\n• احراز هویت و مدیریت کاربران\n• سیستم پرداخت و سبد خرید\n• استقرار روی هاست و لینوکس\n• بهینه‌سازی سئو',
             req='• آشنایی با پایتون',
             desc='در این دوره یک فروشگاه اینترنتی واقعی با تمام امکانات شامل سبد خرید، درگاه پرداخت، پنل مدیریت و... را با Django می‌سازید.'),
        dict(title='آموزش کامل React.js — از مقدماتی تا پیشرفته', cat='وب', teacher=1, price=1500000, discount=790000,
             level='متوسط', hours=30, image='cover-react.png', featured=True, tags='react, javascript, فرانت‌اند',
             subtitle='مدرن‌ترین کتابخانه جاوااسکریپت را به صورت عملی بیاموزید',
             learn='• مفاهیم پایه تا هوک‌های پیشرفته\n• مدیریت state با Redux Toolkit\n• ساخت SPA حرفه‌ای\n• اتصال به API\n• پروژه نهایی: داشبورد مدیریتی',
             req='• آشنایی با HTML و CSS و JavaScript',
             desc='React محبوب‌ترین کتابخانه فرانت‌اند دنیا است. این دوره شما را از صفر به سطح حرفه‌ای می‌رساند.'),
        dict(title='یادگیری ماشین با پایتون', cat='هوش-مصنوعی', teacher=2, price=2200000, discount=1100000,
             level='پیشرفته', hours=38, image='cover-ml.png', featured=False, tags='ماشین لرنینگ, هوش مصنوعی, sklearn',
             subtitle='از مفاهیم پایه تا مدل‌های پیشرفته با Scikit-learn و TensorFlow',
             learn='• ریاضیات لازم برای ML به زبان ساده\n• رگرسیون، طبقه‌بندی و خوشه‌بندی\n• شبکه‌های عصبی با TensorFlow\n• پروژه‌های واقعی داده‌کاوی\n• آمادگی برای شغل دانشمند داده',
             req='• آشنایی با پایتون',
             desc='آموزش کامل یادگیری ماشین با تمرکز بر پیاده‌سازی عملی و پروژه‌محور.'),
        dict(title='طراحی UI/UX — مسیر شغلی طراح محصول', cat='طراحی', teacher=3, price=1350000, discount=690000,
             level='مقدماتی', hours=25, image='cover-uiux.png', featured=False, tags='ui, ux, طراحی',
             subtitle='طراحی رابط کاربری و تجربه کاربری با Figma — پروژه‌محور',
             learn='• اصول طراحی و روانشناسی رنگ\n• کار با Figma از صفر\n• طراحی اپلیکیشن موبایل و وب\n• ساخت Design System\n• ساخت نمونه کار حرفه‌ای',
             req='• هیچ پیش‌نیازی نیاز نیست',
             desc='مسیر شغلی طراحی محصول را با پروژه‌های عملی و نمونه‌کار واقعی شروع کنید.'),
        dict(title='آموزش جامع اکسل — از مقدماتی تا پیشرفته', cat='آفیس', teacher=4, price=480000, discount=290000,
             level='مقدماتی', hours=18, image='cover-excel.png', featured=False, tags='اکسل, excel, آفیس',
             subtitle='مهارت ضروری بازار کار — فرمول‌ها، توابع، داشبورد و ماکرو',
             learn='• توابع پرکاربرد و فرمول‌نویسی\n• جداول محوری PivotTable\n• نمودارهای حرفه‌ای\n• ماکرو و VBA مقدماتی\n• ساخت داشبورد مدیریتی',
             req='• آشنایی مقدماتی با کامپیوتر',
             desc='اکسل پرکاربردترین نرم‌افزار اداری دنیاست. این دوره شما را از صفر به سطح پیشرفته می‌رساند.'),
        dict(title='دیجیتال مارکتینگ — جذب و فروش آنلاین', cat='کسب-وکار', teacher=5, price=980000, discount=490000,
             level='مقدماتی', hours=20, image='cover-marketing.png', featured=False, tags='مارکتینگ, سئو, تبلیغات',
             subtitle='سئو، تبلیغات، شبکه‌های اجتماعی و فروش آنلاین',
             learn='• سئو و بهینه‌سازی موتور جستجو\n• تبلیغات گوگل و کمپین‌های موثر\n• بازاریابی شبکه‌های اجتماعی\n• ایمیل مارکتینگ و قیف فروش\n• آنالیز داده‌های فروش',
             req='• هیچ پیش‌نیازی نیاز نیست',
             desc='هر آنچه برای شروع و رشد کسب‌وکار آنلاین نیاز دارید، در یک دوره کامل.'),
        dict(title='توسعه اپلیکیشن اندروید با Kotlin', cat='موبایل', teacher=0, price=1900000, discount=950000,
             level='متوسط', hours=35, image='cover-android.png', featured=False, tags='اندروید, kotlin, موبایل',
             subtitle='ساخت اپلیکیشن‌های مدرن اندروید با زبان رسمی گوگل',
             learn='• مبانی Kotlin و اندروید استودیو\n• طراحی رابط کاربری با Jetpack Compose\n• کار با API و دیتابیس Room\n• انتشار اپ در بازار و گوگل پلی',
             req='• آشنایی مقدماتی با برنامه‌نویسی',
             desc='با Kotlin — زبان رسمی توسعه اندروید — اپلیکیشن‌های مدرن و حرفه‌ای بسازید.'),
        dict(title='راه‌اندازی سایت فروشگاهی با وردپرس', cat='وب', teacher=4, price=750000, discount=390000,
             level='مقدماتی', hours=16, image='cover-wordpress.svg', featured=False, tags='وردپرس, ووکامرس, سایت',
             subtitle='بدون برنامه‌نویسی، فروشگاه اینترنتی حرفه‌ای بسازید',
             learn='• نصب و راه‌اندازی وردپرس\n• قالب‌ها و افزونه‌های ضروری\n• راه‌اندازی ووکامرس\n• اتصال درگاه پرداخت\n• سئو و افزایش فروش',
             req='• هیچ پیش‌نیازی نیاز نیست',
             desc='با وردپرس و ووکامرس در کمتر از یک هفته فروشگاه اینترنتی خود را راه بیندازید.'),
        dict(title='مکالمه انگلیسی — مسیر روان‌سخنی', cat='زبان', teacher=5, price=890000, discount=450000,
             level='مقدماتی', hours=30, image='cover-english.svg', featured=False, tags='انگلیسی, مکالمه, زبان',
             subtitle='یادگیری مکالمه روزمره و تخصصی با روش نوین آموزش',
             learn='• مکالمه روزمره و موقعیت‌های واقعی\n• گرامر کاربردی بدون حفظ‌کردن\n• تلفظ صحیح و لهجه\n• آمادگی مصاحبه شغلی',
             req='• هیچ پیش‌نیازی نیاز نیست',
             desc='با روش مکالمه‌محور و تمرین‌های روزانه، به راحتی و با اعتمادبه‌نفس انگلیسی صحبت کنید.'),
        dict(title='امنیت اطلاعات و هک اخلاقی', cat='امنیت', teacher=2, price=1650000, discount=820000,
             level='پیشرفته', hours=28, image='cover-security.svg', featured=False, tags='امنیت, هک, kali',
             subtitle='شروع حرفه امنیت سایبری با کالی لینوکس — پروژه‌محور',
             learn='• مبانی شبکه و امنیت سایبری\n• تست نفوذ با Kali Linux\n• شناسایی و رفع آسیب‌پذیری\n• امنیت وب‌اپلیکیشن‌ها\n• ساخت محیط آزمایشگاهی',
             req='• آشنایی مقدماتی با لینوکس',
             desc='مسیر شغلی پرتقاضای امنیت سایبری را با دوره جامع هک اخلاقی شروع کنید.'),
    ]

    sections_lessons = {
        'پایتون': [('آشنایی با پایتون', 6), ('ساختارهای داده', 7), ('برنامه‌نویسی شیءگرا', 6), ('پروژه‌های عملی', 8)],
        'فلاسک': [('شروع کار با Flask', 4), ('دیتابیس و SQLAlchemy', 5), ('پروژه فروشگاه', 6)],
        'جنگو': [('پایه‌های Django', 6), ('مدل‌ها و دیتابیس', 7), ('احراز هویت', 5), ('پروژه فروشگاه', 8)],
        'ری‌اکت': [('مفاهیم پایه', 5), ('هوک‌ها', 5), ('روتر و API', 5), ('پروژه نهایی', 5)],
        'ماشین‌لرنینگ': [('مبانی و ریاضیات', 5), ('یادگیری نظارت‌شده', 6), ('شبکه‌های عصبی', 6), ('پروژه نهایی', 4)],
        'UIUX': [('مبانی طراحی', 5), ('فیگما', 6), ('طراحی اپ موبایل', 5), ('نمونه‌کار', 4)],
        'اکسل': [('مقدمات', 5), ('فرمول‌ها و توابع', 6), ('داشبورد و ماکرو', 4)],
        'مارکتینگ': [('مبانی بازاریابی', 4), ('سئو', 5), ('تبلیغات و شبکه‌های اجتماعی', 5)],
        'اندروید': [('شروع با کاتلین', 6), ('کامپوز', 6), ('API و دیتابیس', 5)],
        'وردپرس': [('نصب و راه‌اندازی', 4), ('ووکامرس', 5), ('افزونه‌ها و سئو', 4)],
        'انگلیسی': [('مکالمه روزمره', 6), ('گرامر کاربردی', 6), ('تمرین مکالمه', 5)],
        'امنیت': [('مبانی شبکه و امنیت', 5), ('کالی لینوکس', 5), ('تست نفوذ', 6)],
    }

    lesson_titles = ['معرفی دوره و نقشه راه', 'نصب و راه‌اندازی', 'مفاهیم پایه و اصطلاحات',
                     'تمرین عملی ۱', 'تمرین عملی ۲', 'مطالعه موردی', 'اشتباهات رایج',
                     'جمع‌بندی و گام بعدی', 'پرسش و پاسخ']

    courses = []
    for i, cd in enumerate(courses_data):
        key = cd['title'].split('—')[0].strip()
        slug = slugify(cd['title'])
        c = Course(
            title=cd['title'], slug=slug + f'-{i+1}', subtitle=cd['subtitle'],
            description=cd['desc'], image=cd['image'],
            category_id=cats[cd['cat']].id, teacher_id=teachers[cd['teacher']].id,
            price=cd['price'], discount_price=cd['discount'], level=cd['level'],
            duration_hours=cd['hours'], featured=cd['featured'], tags=cd['tags'],
            what_you_learn=cd['learn'], requirements=cd['req'],
            views=random.randint(1200, 9500),
            seeded_students=random.randint(900, 7800),
            created_at=utcnow() - timedelta(days=random.randint(5, 200)),
        )
        db.session.add(c)
        db.session.flush()
        courses.append(c)

        # سکشن‌ها و جلسات
        sl = sections_lessons.get(list(sections_lessons.keys())[i % len(sections_lessons)])
        for si, (sname, count) in enumerate(sl):
            sec = Section(course_id=c.id, title=sname, sort=si)
            db.session.add(sec)
            db.session.flush()
            for li in range(count):
                title = lesson_titles[li % len(lesson_titles)]
                if li % 9 == 8:
                    title = f'جلسه {li+1}: ' + 'پروژه عملی: ' + sname
                # انواع منبع ویدیو: مستقیم / یوتیوب / آپارات
                vt, vu = 'direct', '/static/video/sample.mp4'
                if (i + li) % 9 == 3:
                    vt, vu = 'youtube', 'https://www.youtube.com/watch?v=ScMzIvxBSi4'
                elif (i + li) % 9 == 6:
                    vt, vu = 'aparat', 'https://www.aparat.com/v/abc12345'
                # فایل پیوست (پروژه/دیتا) برای اولین جلسه برخی دوره‌ها
                fl = None
                if li == 0 and i % 2 == 0:
                    fl = ('/static/uploads/lessons/sample-project.zip',
                          'فایل‌های پروژه و دیتای دوره', '۲.۴ مگابایت')
                db.session.add(Lesson(
                    section_id=sec.id, title=f'{title} ({li+1})',
                    video_type=vt, video_url=vu,
                    file_url=fl[0] if fl else None,
                    file_name=fl[1] if fl else None,
                    file_size=fl[2] if fl else None,
                    duration='00:1' + str(2 + (li % 4)) + ':00',
                    is_free=(i % 3 == 0 and si == 0 and li == 0),
                    content='در این جلسه، مفاهیم مربوطه به صورت کاملاً عملی و پروژه‌محور آموزش داده می‌شود. همراه با تمرین‌های کاربردی برای تثبیت یادگیری.',
                    sort=li))

        # نظرات
        names = ['علی محمدی', 'فاطمه احمدی', 'رضا کاظمی', 'مینا رحیمی', 'حامد صادقی', 'پریسا موسوی']
        for ri in range(random.randint(2, 5)):
            db.session.add(Review(
                course_id=c.id, user_id=random.choice([demo.id, None]) or demo.id,
                is_approved=(ri != 0),
                rating=random.choice([4, 4, 5, 5, 5, 3]),
                comment=random.choice([
                    'دوره فوق‌العاده‌ای بود! توضیحات کاملاً شفاف و پروژه‌ها خیلی کاربردی‌اند.',
                    'از کیفیت تدریس واقعاً راضی‌ام. پیشنهاد می‌کنم حتماً تهیه کنید.',
                    'مباحث کاملاً به روز و متناسب با بازار کار است.',
                    'پشتیبانی عالی بود و به همه سوالاتم پاسخ دادند.',
                    'بهترین دوره‌ای بود که تا حالا گذروندم، ممنون از تیم آکادمی.']),
                created_at=utcnow() - timedelta(days=random.randint(1, 90))))

    db.session.flush()

    # ---------- سفارش‌ها و ثبت‌نام‌ها ----------
    order = Order(code='AC-140308-001', user_id=demo.id, gateway='zarinpal',
                  status='paid', ref_id='REF-100200300',
                  created_at=utcnow() - timedelta(days=3))
    total = 0
    for cid in [courses[0].id, courses[5].id]:
        price = db.session.get(Course, cid).final_price
        order.items.append(OrderItem(course_id=cid, price=price))
        total += price
    order.total = total
    order.final_total = total
    order.paid_at = utcnow() - timedelta(days=3)
    db.session.add(order)
    db.session.flush()
    for it in order.items:
        en = Enrollment(user_id=demo.id, course_id=it.course_id, order_id=order.id,
                        created_at=order.created_at)
        en.save_progress([])
        db.session.add(en)

    # پیشرفت ساختگی برای دوره اول
    en = Enrollment.query.filter_by(user_id=demo.id, course_id=courses[0].id).first()
    first_course_lessons = [l.id for l in courses[0].lessons[:14]]
    en.save_progress(first_course_lessons)

    # ---------- کوپن‌ها ----------
    db.session.add_all([
        Coupon(code='WELCOME20', type='percent', value=20, max_uses=500, used_count=137, min_amount=100000,
               expires_at=utcnow() + timedelta(days=45)),
        Coupon(code='NOWROOZ10', type='percent', value=10, max_uses=1000, used_count=412,
               expires_at=utcnow() + timedelta(days=90)),
        Coupon(code='FIX500', type='fixed', value=500000, max_uses=50, used_count=8, min_amount=2000000,
               expires_at=utcnow() + timedelta(days=30)),
    ])

    # ---------- وبلاگ ----------
    posts = [
        ('۱۰ ترفند پایتون که هر برنامه‌نویسی باید بداند', 'پایتون', 'cover-python.png',
         'اگر می‌خواهید کدهای تمیزتر و سریع‌تری بنویسید، این ترفندها را از دست ندهید...',
         'پایتون یکی از محبوب‌ترین زبان‌های برنامه‌نویسی دنیاست...'.ljust(400, ' ')),
        ('راهنمای انتخاب اولین زبان برنامه‌نویسی', 'برنامه‌نویسی', 'cover-ml.png',
         'با این راهنما بهترین زبان برنامه‌نویسی را برای شروع انتخاب کنید...',
         'انتخاب اولین زبان برنامه‌نویسی می‌تواند تصمیم مهمی باشد...'.ljust(420, ' ')),
        ('چگونه در ۶ ماه توسعه‌دهنده وب شویم؟', 'وب', 'cover-react.png',
         'برنامه‌ای واقع‌بینانه و عملی برای ورود به بازار کار توسعه وب...',
         'توسعه وب یکی از پردرآمدترین مشاغل فناوری است...'.ljust(450, ' ')),
        ('۵ مهارت نرم که هر متخصص فناوری به آن نیاز دارد', 'مهارت‌های شغلی', 'cover-marketing.png',
         'علاوه بر مهارت فنی، این مهارت‌های نرم مسیر پیشرفت شما را هموار می‌کنند...',
         'مهارت‌های نرم به اندازه مهارت‌های فنی اهمیت دارند...'.ljust(380, ' ')),
    ]
    for title, cat, img, exc, body in posts:
        db.session.add(BlogPost(title=title, slug=slugify(title), excerpt=exc, body=body,
                                image=img, category=cat, author_id=admin.id,
                                views=random.randint(300, 4000),
                                created_at=utcnow() - timedelta(days=random.randint(1, 80))))

    # ---------- دیدگاه‌های وبلاگ ----------
    fp = BlogPost.query.first()
    if fp:
        db.session.add_all([
            BlogComment(post_id=fp.id, name='علی محمدی', comment='مطلب بسیار مفیدی بود، ممنون از تیم آکادمی 🙏'),
            BlogComment(post_id=fp.id, name='مریم رضایی', comment='لطفاً درباره این موضوع بیشتر بنویسید.'),
        ])

    # ---------- تیکت، خبرنامه، پیام ----------
    db.session.add(Ticket(user_id=demo.id, subject='سوال درباره دوره پایتون',
                          body='سلام، آیا بعد از خرید دوره، به آپدیت‌های بعدی هم دسترسی دارم؟',
                          created_at=utcnow() - timedelta(days=2)))
    for e in ['alireza@gmail.com', 'niloofar@yahoo.com', 'mohsen73@gmail.com']:
        db.session.add(NewsletterEmail(email=e))
    db.session.add(ContactMessage(name='رضا کریمی', email='reza@mail.com',
                                  subject='همکاری با آکادمی', message='سلام، مایل به تدریس در آکادمی هستم...'))

    db.session.commit()
    print('✅ داده‌های اولیه با موفقیت بارگذاری شدند.')
    print('   👤 ادمین: admin@academy.ir / admin123')
    print('   👤 دمو:  demo@academy.ir / demo123')
    print(f'   📚 تعداد دوره‌ها: {len(courses)}')





def _make_sample_files():
    """ساخت فایل نمونه پروژه برای پیوست جلسات"""
    import os as _os
    import zipfile as _zip
    d = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'static', 'uploads', 'lessons')
    _os.makedirs(d, exist_ok=True)
    zp = _os.path.join(d, 'sample-project.zip')
    if not _os.path.exists(zp):
        with _zip.ZipFile(zp, 'w') as z:
            z.writestr('README.txt',
                       'فایل‌های نمونه پروژه دوره\n'
                       'شامل سورس‌کد و دیتای تمرینی\n'
                       'این فایل نمونه توسط اسکریپت ساخته شده است.')


def seed_pages():
    """صفحات اولیه صفحه‌ساز: هدر، فوتر، خانه و منوی موبایل"""
    import json as _json
    print('🧩 ساخت صفحات صفحه‌ساز...')

    # ---------------- هدر (سبک فرادرس) ----------------
    header = Page.query.filter_by(ptype='header').first()
    if not header:
        header = Page(title='هدر سایت', slug='site-header', ptype='header')
    header.content = _json.dumps({'settings': {'sticky': True}, 'rows': [
        # نوار بالایی سرمه‌ای
        {'id': 'h_top', 'settings': {'gap': 0, 'py': 9, 'bg': '#0d1f36'}, 'cols': [[
            {'id': 'h_topbar', 'type': 'topbar', 'data': {
                'right': [
                    {'text': '📞 ۰۲۱-۹۱۰۰۱۲۳۴', 'url': 'tel:02191001234', 'cls': ''},
                    {'text': '✉️ info@academy.ir', 'url': 'mailto:info@academy.ir', 'cls': ''},
                ],
                'left': [
                    {'text': 'سوالی دارید؟ پرسش‌های متداول', 'url': '/faq', 'cls': ''},
                    {'text': 'ورود | ثبت‌نام', 'url': '/auth/login', 'cls': 'dk-top-login'},
                ]}}
        ]]},
        # ردیف اصلی: لوگو + جستجو + آیکون‌ها
        {'id': 'h_main', 'settings': {'gap': 26, 'py': 16, 'bg': '#ffffff', 'widths': 'auto 1fr auto'}, 'cols': [
            [{'id': 'h_logo', 'type': 'logo', 'data': {'text': 'آکادمی آنلاین', 'icon': '🎓', 'sub': 'مرجع تخصصی آموزش آنلاین'}}],
            [{'id': 'h_search', 'type': 'search', 'data': {'placeholder': 'جستجو در تمام دوره‌های آموزشی...', 'show_cat': True}}],
            [
                {'id': 'h_fav', 'type': 'icon_link', 'data': {'icon': '❤️', 'label': 'علاقه‌مندی', 'url': '/dashboard/favorites', 'badge': 'fav'}},
                {'id': 'h_cart', 'type': 'icon_link', 'data': {'icon': '🛒', 'label': 'سبد خرید', 'url': '/cart', 'badge': 'cart'}},
                {'id': 'h_user', 'type': 'user_menu', 'data': {}},
            ],
        ]},
        # ردیف ناوبری: دسته‌بندی + منوی اصلی
        {'id': 'h_nav', 'settings': {'gap': 22, 'py': 10, 'bg': '#ffffff', 'widths': 'auto 1fr'}, 'cols': [
            [{'id': 'h_mega', 'type': 'category_mega', 'data': {'button': 'دسته‌بندی دوره‌ها', 'columns': 3}}],
            [{'id': 'h_navmenu', 'type': 'nav_menu', 'data': {'align': 'right', 'links': [
                {'text': 'دوره‌های آموزشی', 'url': '/courses'},
                {'text': 'مسیر یادگیری', 'url': '/courses?sort=popular'},
                {'text': 'استخدام', 'url': '/about'},
                {'text': 'دانشجویان', 'url': '/blog'},
                {'text': 'وبلاگ', 'url': '/blog'},
                {'text': 'پرسش و پاسخ', 'url': '/faq'},
                {'text': 'مدرس شو', 'url': '/contact'},
            ]}}],
        ]},
    ]}, ensure_ascii=False)
    header.is_published = True
    db.session.add(header)

    # ---------------- فوتر (طراحی جدید از footer_template) ----------------
    from footer_template import FOOTER_ROWS
    footer = Page.query.filter_by(ptype='footer').first()
    if not footer:
        footer = Page(title='فوتر سایت', slug='site-footer', ptype='footer')
    footer.content = _json.dumps({'settings': {}, 'rows': FOOTER_ROWS}, ensure_ascii=False)
    footer.is_published = True
    db.session.add(footer)

    # ---------------- منوی موبایل (اینستاگرامی) ----------------
    mob = Page.query.filter_by(ptype='mobile_menu').first()
    if not mob:
        mob = Page(title='منوی موبایل', slug='mobile-menu', ptype='mobile_menu')
    mob.content = _json.dumps({'settings': {}, 'rows': [
        {'id': 'm_nav', 'settings': {'gap': 0, 'py': 0}, 'cols': [[
            {'id': 'm_home', 'type': 'mobile_item', 'data': {'icon': '🏠', 'label': 'خانه', 'url': '/'}},
            {'id': 'm_courses', 'type': 'mobile_item', 'data': {'icon': '📚', 'label': 'دوره‌ها', 'url': '/courses'}},
            {'id': 'm_theme', 'type': 'mobile_item', 'data': {'icon': '🎨', 'label': 'تم‌ها', 'url': '#theme'}},
            {'id': 'm_fav', 'type': 'mobile_item', 'data': {'icon': '❤️', 'label': 'علاقه‌مندی', 'url': '/dashboard/favorites'}},
            {'id': 'm_profile', 'type': 'mobile_item', 'data': {'icon': '👤', 'label': 'پروفایل', 'url': '/dashboard'}},
        ]]},
    ]}, ensure_ascii=False)
    mob.is_published = True
    db.session.add(mob)

    # ---------------- صفحه اصلی (صفحه‌ساز) ----------------
    home = Page.query.filter_by(ptype='home').first()
    if not home:
        home = Page(title='صفحه اصلی', slug='home', ptype='home')
    home.content = _json.dumps({'settings': {}, 'rows': [
        {'id': 'hm_hero', 'settings': {'gap': 0, 'py': 0, 'radius': 0}, 'cols': [[
            {'id': 'hm_slider', 'type': 'slider', 'data': {
                'height': '430', 'autoplay': True, 'interval': '5', 'dots': True, 'arrows': True,
                'slides': [
                    {'img': 'hero.png', 'title': 'آینده‌ات را با مهارت‌های دیجیتال قدرتمندتر بساز',
                     'sub': 'دوره‌های پروژه‌محور با برترین مدرسان ایران — از برنامه‌نویسی تا مارکتینگ. همین امروز شروع کن!',
                     'btn_text': '🚀 مشاهده همه دوره‌ها', 'btn_url': '/courses', 'align': 'right'},
                    {'img': 'cover-python.png', 'title': 'دوره جامع پایتون با ۵۰٪ تخفیف ویژه',
                     'sub': 'از صفر تا استخدام — با کد تخفیف WELCOME20 تا ۲۰٪ تخفیف بیشتر بگیرید!',
                     'btn_text': 'مشاهده دوره پایتون', 'btn_url': '/course/دوره-جامع-برنامه‌نویسی-پایتون-1', 'align': 'center'},
                    {'img': 'cover-django.png', 'title': 'ساخت فروشگاه اینترنتی با Django',
                     'sub': 'دوره پروژه‌محور — مناسب بازار کار ایران',
                     'btn_text': 'مشاهده دوره', 'btn_url': '/courses', 'align': 'right'},
                ]}}
        ]]},
        {'id': 'hm_features', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
            {'id': 'hm_feat', 'type': 'feature', 'data': {'columns': '3', 'items': [
                {'icon': '🎬', 'title': 'ویدیوهای باکیفیت', 'text': 'تدریس قدم‌به‌قدم Full HD با دسترسی مادام‌العمر'},
                {'icon': '🏅', 'title': 'گواهینامه معتبر', 'text': 'دریافت گواهی پایان دوره با کد رهگیری منحصربه‌فرد'},
                {'icon': '🎓', 'title': 'اساتید حرفه‌ای', 'text': 'همکاری با برترین مدرسان با تجربه واقعی بازار'},
                {'icon': '🧩', 'title': 'پروژه‌محور', 'text': 'یادگیری با ساخت پروژه‌های واقعی، نه فقط تئوری'},
                {'icon': '💬', 'title': 'پشتیبانی فعال', 'text': 'پاسخگویی سریع به سوالات در تیکت و پیام‌رسان‌ها'},
                {'icon': '🛡️', 'title': 'پرداخت امن', 'text': 'درگاه‌های پرداخت معتبر شتاب با ضمانت بازگشت وجه'},
            ]}}
        ]]},
        {'id': 'hm_cats', 'settings': {'gap': 16, 'py': 60, 'bg': '#ffffff', 'radius': 26}, 'cols': [[
            {'id': 'hm_catgrid', 'type': 'categories', 'data': {'title': 'موضوع مورد علاقه‌ات را انتخاب کن', 'limit': '9', 'columns': '4'}}
        ]]},
        {'id': 'hm_featured', 'settings': {'gap': 24, 'py': 60}, 'cols': [[
            {'id': 'hm_courses', 'type': 'courses', 'data': {'title': '⭐ پرفروش‌ترین دوره‌ها', 'subtitle': 'انتخاب بیشتر دانشجویان', 'category': '', 'limit': '8', 'columns': '4', 'sort': 'popular', 'show_price': True}}
        ]]},
        {'id': 'hm_stats', 'settings': {'gap': 0, 'py': 50}, 'cols': [[
            {'id': 'hm_stat', 'type': 'stats', 'data': {'columns': '4', 'items': [
                {'value': '۱۵۰+', 'label': 'دوره آموزشی'},
                {'value': '۵۰,۰۰۰+', 'label': 'دانشجوی فعال'},
                {'value': '۲,۰۰۰+', 'label': 'ساعت آموزش ویدیویی'},
                {'value': '٪۹۸', 'label': 'رضایت دانشجویان'},
            ]}}
        ]]},
        {'id': 'hm_latest', 'settings': {'gap': 24, 'py': 60, 'bg': '#ffffff', 'radius': 26}, 'cols': [[
            {'id': 'hm_lat', 'type': 'courses', 'data': {'title': '🆕 جدیدترین دوره‌ها', 'subtitle': 'تازه‌ترین‌های آکادمی', 'category': '', 'limit': '8', 'columns': '4', 'sort': 'newest', 'show_price': True}}
        ]]},
        {'id': 'hm_teachers', 'settings': {'gap': 22, 'py': 60}, 'cols': [[
            {'id': 'hm_teach', 'type': 'teachers', 'data': {'title': '👨‍🏫 اساتید برتر آکادمی', 'limit': '4', 'columns': '4'}}
        ]]},
        {'id': 'hm_testi', 'settings': {'gap': 22, 'py': 60, 'bg': '#ffffff', 'radius': 26}, 'cols': [[
            {'id': 'hm_test', 'type': 'testimonials', 'data': {'columns': '3', 'items': [
                {'name': 'علی محمدی', 'role': 'دانشجوی دوره پایتون', 'stars': '5', 'color': '#7c3aed',
                 'text': 'دوره پایتون فوق‌العاده بود! بعد از ۴ ماه به عنوان برنامه‌نویس استخدام شدم.'},
                {'name': 'فاطمه احمدی', 'role': 'دانشجوی دوره Django', 'stars': '5', 'color': '#059669',
                 'text': 'کیفیت تدریس و پشتیبانی واقعاً حرفه‌ای بود. پروژه‌های عملی من رو آماده بازار کار کرد.'},
                {'name': 'نگار کریمی', 'role': 'دانشجوی دوره UI/UX', 'stars': '5', 'color': '#db2777',
                 'text': 'دوره UI/UX رو با تخفیف خریدم و الان به عنوان طراح محصول کار می‌کنم.'},
            ]}}
        ]]},
        {'id': 'hm_blog', 'settings': {'gap': 24, 'py': 60}, 'cols': [[
            {'id': 'hm_posts', 'type': 'posts', 'data': {'title': '📝 از وبلاگ آکادمی', 'limit': '3', 'columns': '3'}}
        ]]},
        {'id': 'hm_cta', 'settings': {'gap': 0, 'py': 30}, 'cols': [[
            {'id': 'hm_cta1', 'type': 'cta', 'data': {
                'title': 'آماده شروع یادگیری هستی؟ 🚀', 'text': 'همین حالا ثبت‌نام کن و با کد تخفیف WELCOME20 از ۲۰٪ تخفیف بهره‌مند شو!',
                'btn_text': 'ثبت‌نام رایگان', 'btn_url': '/auth/register', 'style': 'gradient'}}
        ]]},
        {'id': 'hm_news', 'settings': {'gap': 0, 'py': 20}, 'cols': [[
            {'id': 'hm_news1', 'type': 'newsletter', 'data': {'title': 'عضویت در خبرنامه', 'text': 'جدیدترین مطالب و تخفیف‌ها را از دست ندهید!'}}
        ]]},
    ]}, ensure_ascii=False)
    home.is_published = True
    db.session.add(home)

    db.session.commit()
    print('✅ صفحات صفحه‌ساز ساخته شدند: هدر، فوتر، منوی موبایل، صفحه اصلی')


if __name__ == '__main__':
    from app import app
    with app.app_context():
        db.create_all()
        seed()
        _make_sample_files()
        seed_pages()
