# -*- coding: utf-8 -*-
"""تست رگرسیون ویجت‌های صفحه‌ساز — amazing_offer و price_history و مرتب‌سازی."""
from models import db, Course, Category, Product


def test_amazing_offer_fallback_picks_discount_without_500(app):
    """بدون item_id، ویجت پیشنهاد شگفت‌انگیز باید بهترین تخفیف را برگرداند نه 500.

    قبلاً ``Course.query.filter(Course.discount_percent > 0)`` روی یک property
    (نه ستون) اجرا می‌شد و باعث TypeError می‌شد.
    """
    with app.app_context():
        cat = Category.query.first()
        if not cat:
            cat = Category(name='برنامه‌نویسی', slug='programming', sort=1)
            db.session.add(cat)
            db.session.flush()
        db.session.add(Course(title='بدون تخفیف', slug='no-discount', price=100000,
                              discount_price=0, category_id=cat.id, status='published'))
        # بیشترین تخفیف (۷۵٪) — باید از دورهٔ ۵۰٪‌ی conftest جلو بیفتد.
        db.session.add(Course(title='تخفیف‌دار', slug='with-discount', price=200000,
                              discount_price=50000, category_id=cat.id, status='published'))
        db.session.commit()
    from blueprints.builder import builder_amazing_offer
    with app.test_request_context('/'):
        with app.app_context():
            ao = builder_amazing_offer({'item_type': 'course', 'item_id': None})
            assert ao.get('item') is not None
            assert ao['item'].title == 'تخفیف‌دار'
            assert ao.get('discount') == 75
            assert ao.get('url').endswith('/with-discount')


def test_price_history_product_url_uses_slug(app):
    """URL ویجت تاریخچهٔ قیمتِ محصول باید با slug ساخته شود (نه pid که BuildError می‌داد)."""
    with app.app_context():
        p = Product(title='محصول تست', slug='test-product', price=90000,
                    discount_price=70000, is_active=True)
        db.session.add(p)
        db.session.commit()
        pid = p.id
    from blueprints.builder import builder_price_history
    with app.test_request_context('/'):
        with app.app_context():
            ph = builder_price_history({'item_type': 'product', 'item_id': pid})
            assert ph.get('url') == '/product/test-product'
            assert ph.get('current') == 70000
            assert ph.get('item') is not None


def test_builder_courses_cheap_sort_uses_effective_price(app):
    """مرتب‌سازی cheap در ویجت دوره‌ها باید دورهٔ بدون تخفیفِ ارزان‌تر را درست جلو ببرد."""
    with app.app_context():
        cat = Category.query.first()
        if not cat:
            cat = Category(name='برنامه‌نویسی', slug='programming', sort=1)
            db.session.add(cat)
            db.session.flush()
        db.session.add(Course(title='گران تخفیف‌دار', slug='exp-discount', price=100000,
                              discount_price=80000, category_id=cat.id, status='published'))
        db.session.add(Course(title='ارزان بدون تخفیف', slug='cheap-nodiscount', price=30000,
                              discount_price=0, category_id=cat.id, status='published'))
        db.session.commit()
    from blueprints.builder import builder_courses
    with app.test_request_context('/'):
        with app.app_context():
            rows = builder_courses({'sort': 'cheap', 'limit': 5})
            assert rows[0].slug == 'cheap-nodiscount'


# ---------------------------------------------------------------------------
# قرارداد سازگاری عقب‌رو (Backward Compatibility) صفحه‌ساز
# ---------------------------------------------------------------------------
# این تست‌ها یک قرارداد معماری را قفل می‌کنند: داده‌های صفحه در ستون
# Page.content به‌صورت JSON ذخیره می‌شوند و ممکن است سال‌ها قبل با نسخه‌ای
# از برنامه ساخته شده باشند که ویجت‌هایی داشته که امروز دیگر وجود ندارند.
#
# قرارداد: اگر یک نوع ویجت از WIDGETS حذف شود، صفحاتی که قبلاً از آن استفاده
# کرده‌اند باید «تخریب مهارشده» داشته باشند — یعنی همان ویجت بی‌صدا حذف شود
# ولی بقیهٔ صفحه سالم رندر شود و هیچ متن دیباگی به بازدیدکننده نشت نکند.
#
# بدون این تست‌ها، هر تغییری در _sanitize_widget می‌تواند بی‌سروصدا باعث شود
# صفحات قدیمی یا کرش کنند یا متن «ویجت ناشناخته» را به کاربر نهایی نشان دهند.

def _page_with_widgets(widgets):
    """ساخت یک صفحهٔ منتشرشده با فهرست ویجت‌های داده‌شده."""
    import json

    from models import Page
    content = {'settings': {}, 'rows': [
        {'id': 'r1', 'settings': {}, 'cols': [list(widgets)]},
    ]}
    page = Page(title='صفحه سازگاری', slug='compat-page', ptype='page',
                is_published=True, content=json.dumps(content))
    db.session.add(page)
    db.session.commit()
    return page


def test_removed_widget_is_dropped_but_page_survives(app, client):
    """ویجت حذف‌شده باید بی‌صدا کنار گذاشته شود و بقیهٔ صفحه رندر شود."""
    with app.app_context():
        _page_with_widgets([
            {'id': 'w1', 'type': 'widget_that_no_longer_exists',
             'data': {'text': 'محتوای منسوخ'}},
            {'id': 'w2', 'type': 'heading', 'data': {'text': 'عنوان سالم باقیمانده'}},
        ])

    r = client.get('/page/compat-page')
    body = r.get_data(as_text=True)
    assert r.status_code == 200, 'صفحهٔ قدیمی نباید به‌خاطر ویجت حذف‌شده خطا بدهد'
    assert 'عنوان سالم باقیمانده' in body, 'بقیهٔ محتوای صفحه باید سالم بماند'
    assert 'ویجت ناشناخته' not in body, \
        'متن دیباگ ویجت ناشناخته نباید به بازدیدکننده نشان داده شود'
    assert 'widget_that_no_longer_exists' not in body, \
        'نام نوع ویجت داخلی نباید در خروجی عمومی لو برود'


def test_sanitize_widget_drops_unknown_type(app):
    """گارد اصلی: _sanitize_widget باید نوع ناشناخته را None برگرداند."""
    with app.app_context():
        from blueprints.builder import _sanitize_widget
        assert _sanitize_widget({'id': 'x', 'type': 'no_such_widget', 'data': {}}) is None
        assert _sanitize_widget({'id': 'x', 'type': 'heading', 'data': {}}) is not None
        # ورودی خراب (غیر dict) هم نباید استثنا بدهد
        assert _sanitize_widget(None) is None
        assert _sanitize_widget('رشته') is None
        assert _sanitize_widget([]) is None


def test_page_with_only_removed_widgets_does_not_crash(app, client):
    """اگر همهٔ ویجت‌های صفحه حذف شده باشند، نباید ۵۰۰ بدهد."""
    with app.app_context():
        _page_with_widgets([
            {'id': 'w1', 'type': 'gone_a', 'data': {}},
            {'id': 'w2', 'type': 'gone_b', 'data': {}},
        ])
    r = client.get('/page/compat-page')
    # بازدیدکنندهٔ مهمان برای صفحهٔ بی‌محتوا ۴۰۴ می‌گیرد (رفتار عمدی اپ)،
    # اما در هیچ حالتی نباید خطای سرور رخ دهد.
    assert r.status_code < 500, 'صفحهٔ بدون ویجت معتبر نباید خطای سرور بدهد'


def test_corrupted_page_content_does_not_crash(app, client):
    """محتوای JSON خراب نباید صفحه یا مدل را بشکند."""
    import json

    from models import Page
    with app.app_context():
        # ۱) JSON نامعتبر
        p = Page(title='خراب', slug='broken-page', ptype='page',
                 is_published=True, content='{این JSON معتبر نیست')
        db.session.add(p)
        db.session.commit()
        assert p.rows() == [], 'JSON خراب باید به لیست خالی تبدیل شود'

        # ۲) ساختار معتبر ولی با انواع دادهٔ اشتباه
        p.content = json.dumps({'rows': [
            'رشته به‌جای dict',
            {'cols': 'رشته به‌جای لیست'},
            {'cols': [['رشته به‌جای ویجت', None, 42]]},
        ]})
        db.session.commit()
        rows = p.rows()
        assert isinstance(rows, list), 'خروجی همیشه باید لیست باشد'
        for row in rows:
            assert isinstance(row.get('cols'), list)

    r = client.get('/page/broken-page')
    assert r.status_code < 500, 'صفحهٔ با محتوای خراب نباید خطای سرور بدهد'


def test_every_registered_widget_has_a_renderer(app):
    """هیچ ویجت ثبت‌شده‌ای نباید بدون شاخهٔ رندر بماند.

    اگر کسی ویجتی به WIDGETS اضافه کند ولی شاخهٔ متناظر را در
    templates/builder/blocks.html ننویسد، کاربر آن را در پالت می‌بیند،
    به صفحه اضافه می‌کند و در خروجی «ویجت ناشناخته» می‌گیرد.
    """
    import re

    from blueprints.builder import WIDGETS
    with app.app_context():
        tpl_path = 'templates/builder/blocks.html'
        with open(tpl_path, encoding='utf-8') as fh:
            tpl = fh.read()
        rendered = set(re.findall(r"t\s*==\s*'([a-z_0-9]+)'", tpl))
        missing = sorted(set(WIDGETS) - rendered)
        assert not missing, \
            'این ویجت‌ها ثبت شده‌اند ولی رندرر نمی‌شناسدشان: {}'.format(missing)
