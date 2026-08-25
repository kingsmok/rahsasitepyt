# -*- coding: utf-8 -*-
"""تست دستی: رندر عمومی تمام بلوک‌های جدید دیزاین سیستم v2 روی یک صفحه."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('APP_ENV', 'testing')

tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
tmp.close()
os.environ['DATABASE_URL'] = 'sqlite:///' + tmp.name

from app import create_app  # noqa: E402
from models import db, Page, Category, Course, User, Section, Lesson  # noqa: E402

app = create_app()
app.config['TESTING'] = True
app.config['INSTALL_GUARD'] = False

ROWS = [
    {'id': 'r_brand', 'settings': {'gap': 24, 'py': 60},
     'cols': [[{'id': 'w_brand', 'type': 'brand_intro', 'data': {
         'eyebrow': 'چرا ما؟', 'title': 'آکادمی مدرن', 'subtitle': 'زیرتیتر تست',
         'media': 'hero.webp', 'media_badge_value': '+۱۲۰', 'media_badge_label': 'دانشجو',
         'points': 'نکته اول\nنکته دوم', 'btn_text': 'بیشتر', 'btn_url': '/about',
         'btn2_text': 'دوره‌ها', 'btn2_url': '/courses',
         'stats': [{'icon': '🎓', 'value': '{courses}', 'label': 'دوره'}]}}]]},
    {'id': 'r_teacher', 'settings': {'gap': 24, 'py': 40},
     'cols': [[{'id': 'w_teacher', 'type': 'instructor', 'data': {
         'title': 'مدرس', 'name': 'استاد نمونه', 'role': 'مهندس نرم‌افزار',
         'bio': 'بیو تست', 'cv': 'دستاورد ۱\nدستاورد ۲',
         'stats': [{'value': '۱۲', 'label': 'دوره'}, {'value': '۹۸٪', 'label': 'رضایت'}],
         'btn_text': 'دوره‌ها', 'btn_url': '/courses',
         'socials': [{'icon': '✈️', 'url': 'https://t.me/x'}]}}]]},
    {'id': 'r_curric', 'settings': {'gap': 24, 'py': 40},
     'cols': [[{'id': 'w_curr', 'type': 'curriculum', 'data': {
         'title': 'سرفصل', 'subtitle': 'زیرتیتر', 'source': 'manual', 'open_first': True,
         'chapters': [{'title': 'فصل اول', 'lessons': 'معرفی | ۱۰ دقیقه\nنصب ابزار | ۲۰ دقیقه'}],
         'btn_text': 'خرید', 'btn_url': '/courses'}}]]},
    {'id': 'r_path', 'settings': {'gap': 24, 'py': 40},
     'cols': [[{'id': 'w_path', 'type': 'learning_path', 'data': {
         'eyebrow': 'مسیر', 'title': 'گام‌ها', 'subtitle': 'توضیح', 'columns': '4',
         'steps': [{'title': 'گام ۱', 'text': 'توضیح', 'chip': '۲ دوره', 'state': 'done'},
                   {'title': 'گام ۲', 'text': 'توضیح', 'chip': 'پروژه', 'state': 'now'},
                   {'title': 'گام ۳', 'text': 'توضیح'},
                   {'title': 'گام ۴', 'text': 'توضیح'}]}}]]},
    {'id': 'r_tl', 'settings': {'gap': 24, 'py': 40},
     'cols': [[{'id': 'w_tl', 'type': 'timeline', 'data': {
         'eyebrow': 'تاریخچه', 'title': 'مسیر ما', 'align': 'start',
         'items': [{'date': '۱۴۰۰', 'title': 'شروع', 'text': 'توضیح'},
                   {'date': '۱۴۰۲', 'title': 'رشد', 'text': 'توضیح'}]}}]]},
    {'id': 'r_cmp', 'settings': {'gap': 24, 'py': 40},
     'cols': [[{'id': 'w_cmp', 'type': 'plans_compare', 'data': {
         'title': 'مقایسه', 'subtitle': 'زیر',
         'plans': [{'name': 'پایه', 'price': 'رایگان', 'btn_text': 'شروع', 'btn_url': '/auth/register'},
                   {'name': 'حرفه‌ای', 'price': '۴۹۰٬۰۰۰', 'btn_text': 'خرید', 'btn_url': '/courses', 'best': True}],
         'rows': 'دسترسی دوره‌ها | 1 | 1\nپشتیبانی | 0 | 1\nگواهی | no | yes'}}]]},
    {'id': 'r_mem', 'settings': {'gap': 24, 'py': 40},
     'cols': [[{'id': 'w_mem', 'type': 'membership', 'data': {
         'eyebrow': 'اشتراک', 'title': 'عضویت ویژه', 'subtitle': 'توضیح', 'columns': '3',
         'plans': [{'name': 'ماهانه', 'price': '۲۹۰٬۰۰۰', 'period': 'تومان / ماه',
                    'features': 'تمام دوره‌ها\nپشتیبانی', 'btn_text': 'انتخاب', 'btn_url': '/auth/register', 'best': True, 'ribbon': 'پیشنهاد ما'},
                   {'name': 'سالانه', 'price': '۲٬۴۹۰٬۰۰۰', 'period': 'تومان / سال',
                    'old_price': '۳٬۴۸۰٬۰۰۰', 'features': 'تمام دوره‌ها', 'btn_text': 'انتخاب', 'btn_url': '/auth/register'}]}}]]},
    {'id': 'r_offer', 'settings': {'gap': 24, 'py': 40},
     'cols': [[{'id': 'w_offer', 'type': 'discount_banner', 'data': {
         'badge': '٪۴۰ تخفیف', 'title': 'جشنواره آموزش', 'text': 'توضیح کمپین',
         'coupon': 'SALE40', 'btn_text': 'مشاهده تخفیف‌ها', 'btn_url': '/courses',
         'target': '2099-01-01', 'show_countdown': True}}]]},
    {'id': 'r_file', 'settings': {'gap': 24, 'py': 40},
     'cols': [[{'id': 'w_file', 'type': 'file_download', 'data': {
         'title': 'فایل‌های دوره', 'columns': '2',
         'items': [{'icon': '📄', 'title': 'جزوه دوره', 'desc': 'PDF کامل',
                    'ext': 'PDF', 'size': '۲ مگابایت', 'url': '/static/img/hero.webp'}]}}]]},
    {'id': 'r_cert', 'settings': {'gap': 24, 'py': 40},
     'cols': [[{'id': 'w_cert', 'type': 'certificates', 'data': {
         'eyebrow': 'مدرک', 'title': 'گواهی‌ها', 'subtitle': 'توضیح', 'columns': '3',
         'items': [{'icon': '🏅', 'title': 'گواهی', 'text': 'توضیح'}],
         'verify_text': 'استعلام', 'verify_url': '/verify-certificate'}}]]},
    {'id': 'r_trust', 'settings': {'gap': 16, 'py': 40},
     'cols': [[{'id': 'w_trust', 'type': 'trust_box', 'data': {'columns': '4', 'items': [
         {'icon': '↩️', 'title': 'ضمانت', 'text': '۷ روز'},
         {'icon': '💳', 'title': 'پرداخت امن', 'text': 'درگاه رسمی'},
         {'icon': '🎧', 'title': 'پشتیبانی', 'text': '۲۴ ساعته'},
         {'icon': '♾️', 'title': 'دسترسی', 'text': 'دائمی'}]}}]]},
    {'id': 'r_off', 'settings': {'gap': 24, 'py': 40},
     'cols': [[{'id': 'w_off', 'type': 'special_offers', 'data': {
         'title': 'تخفیف‌ها', 'subtitle': 'زیر', 'limit': '4', 'columns': '4',
         'btn_text': 'همه', 'btn_url': '/courses'}}]]},
    {'id': 'r_rel', 'settings': {'gap': 24, 'py': 40},
     'cols': [[{'id': 'w_rel', 'type': 'related_products', 'data': {
         'title': 'محصولات مرتبط', 'subtitle': 'زیر', 'limit': '4', 'columns': '4'}}]]},
]

with app.app_context():
    db.create_all()
    cat = Category(name='برنامه‌نویسی', slug='programming', sort=1)
    db.session.add(cat); db.session.flush()
    t = User(name='مدرس تست', email='t@t.ir', phone='09120000999', role='teacher', is_active=True)
    t.set_password('pass12345'); db.session.add(t); db.session.flush()
    c = Course(title='دوره تخفیف‌دار', slug='disc-course', price=100000, discount_price=50000,
               category_id=cat.id, teacher_id=t.id, status='published')
    db.session.add(c); db.session.flush()
    sec = Section(course_id=c.id, title='فصل اول', sort=1)
    db.session.add(sec); db.session.flush()
    db.session.add(Lesson(section_id=sec.id, title='جلسه اول', duration='00:12:00', is_free=True, sort=1))
    db.session.commit()
    cid = c.id

    page = Page(title='تست بلوک‌ها', slug='ds-test', ptype='page', is_published=True,
                content=json.dumps({'settings': {}, 'rows': ROWS}, ensure_ascii=False))
    db.session.add(page); db.session.commit()

    client = app.test_client()
    r = client.get("/page/ds-test")
    assert r.status_code == 200, r.status_code
    html = r.get_data(as_text=True)
    for marker in ['ds-split', 'ds-teacher', 'ds-curric', 'ds-path', 'ds-timeline',
                   'ds-compare', 'ds-plan', 'ds-offer-banner', 'ds-file',
                   'ds-cert', 'ds-trust-item', 'course-card', '٪۵۰ تخفیف']:
        assert marker in html, 'missing: ' + marker
    assert 'پیشنهاد ما' in html and 'SALE40' in html and 'data-countdown' in html
    assert 'گام ۱' in html and 'دسترسی دوره‌ها' in html and 'استعلام' in html
    assert 'object at 0x' not in html, 'repr leak — some lite object rendered raw'
    assert 'برنامه‌نویسی' in html, 'category name missing on offer card'
    print('✅ render OK — all 13 new blocks render publicly')

    # صفحهٔ دوره با کارت جدید و سرفصل داینامیک (قالب صفحه‌ساز course)
    tp = Page(title='قالب دوره', slug='ds-course-tpl', ptype='course', is_published=True,
              content=json.dumps({'settings': {}, 'rows': [
                  {'id': 'rc', 'settings': {'gap': 24, 'py': 40},
                   'cols': [[{'id': 'wc', 'type': 'curriculum', 'data': {'source': 'current', 'title': 'سرفصل دوره'}}]]}]},
                  ensure_ascii=False))
    db.session.add(tp); db.session.commit()
    from builder_sections import ensure_section
    from blueprints.builder import _clear_app_cache
    _clear_app_cache()
    r2 = client.get('/course/disc-course')
    assert r2.status_code == 200, r2.status_code
    h2 = r2.get_data(as_text=True)
    assert 'دوره تخفیف‌دار' in h2
    assert 'ds-curric' in h2 and 'جلسه اول' in h2, 'dynamic curriculum missing'
    assert 'پیش‌نمایش رایگان' in h2
    print('✅ course template OK — dynamic curriculum + new card render')

os.unlink(tmp.name)
print('DONE')
