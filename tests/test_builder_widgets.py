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
