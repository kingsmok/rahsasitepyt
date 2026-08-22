# -*- coding: utf-8 -*-
"""دسته ۳: مسیریابی ضد 404، فعالسازی سایت، اسلاگسازی، دیدگاه وبلاگ، نصب مجدد داده."""
import hashlib
import re
from datetime import datetime, timedelta

from models import (BlogComment, BlogPost, Category, Course, Product, Setting,
                    User, db, make_slug, unique_slug_for)

from conftest import login


def _make_admin(app, email='admcore@test.ir', role='super_admin'):
    with app.app_context():
        a = User(name='Admin Core', email=email, phone='09120000200',
                 role=role, is_active=True)
        a.set_password('admin123')
        db.session.add(a)
        db.session.commit()
        return a.id


def _login_admin(client, app, email='admcore@test.ir'):
    r = client.get('/auth/login')
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/auth/login', data={'_csrf_token': tok, 'email': email,
                                     'password': 'admin123'})
    code2 = app.config.get('_TEST_AUTH_CODES', {}).get('admin-2fa')
    assert code2
    r = client.get('/auth/admin-2fa')
    tok2 = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/auth/admin-2fa', data={'_csrf_token': tok2, 'code': code2})


def _csrf(client, path):
    r = client.get(path)
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    return m.group(1) if m else ''


# ═══════════════ اسلاگسازی ═══════════════

def test_make_slug_persian_and_fallbacks():
    assert make_slug('دوره جامع پایتون') == 'دوره-جامع-پایتون'
    assert make_slug('Python Master Class!') == 'Python-Master-Class'
    assert make_slug('  ') == 'item'
    assert make_slug('!!!') == 'item'
    assert make_slug('الف  الف') == 'الف-الف'


def test_unique_slug_for_appends_counter(app):
    with app.app_context():
        c1 = Course(title='تست', slug='تست', price=0, status='draft')
        db.session.add(c1)
        db.session.commit()
        slug2 = unique_slug_for(Course, 'تست')
        assert slug2 == 'تست-2'
        slug_self = unique_slug_for(Course, 'تست', exclude_id=c1.id)
        assert slug_self == 'تست'


def test_admin_product_creation_uses_unique_persian_slug(client, app):
    _make_admin(app)
    _login_admin(client, app)
    tok = _csrf(client, '/admin/products')
    for title in ('ماگ تستی', 'ماگ تستی'):
        r = client.post('/admin/products', data={
            '_csrf_token': tok, 'title': title, 'price': '1000', 'description': '',
        }, follow_redirects=False)
        assert r.status_code == 302
        tok = _csrf(client, '/admin/products')
    with app.app_context():
        slugs = [p.slug for p in Product.query.filter(Product.title == 'ماگ تستی').all()]
        assert len(slugs) == 2 and len(set(slugs)) == 2
        assert slugs[0] == 'ماگ-تستی'


# ═══════════════ مسیریابی ═══════════════

def test_course_numeric_id_redirects_to_canonical(client, app):
    with app.app_context():
        c = Course.query.filter_by(slug='test-course').first()
        cid = c.id
    r = client.get('/course/{}'.format(cid), follow_redirects=False)
    assert r.status_code == 301
    assert '/course/test-course' in r.headers.get('Location', '')


def test_product_numeric_id_redirects_to_canonical(client, app):
    with app.app_context():
        p = Product.query.first()
        if p is None:
            p = Product(title='محصول', slug='product-x', price=100, is_active=True)
            db.session.add(p)
            db.session.commit()
        pid = p.id
        slug = p.slug
    r = client.get('/product/{}'.format(pid), follow_redirects=False)
    assert r.status_code == 301
    assert '/product/{}'.format(slug) in r.headers.get('Location', '')


def test_course_empty_slug_does_not_crash(client, app):
    r = client.get('/course/')
    assert r.status_code == 404
    r = client.get('/course/%20')
    assert r.status_code == 404


def test_teacher_profile_shows_admin_teachers(client, app):
    """مدرس با نقش admin (که در فرم دوره قابل انتخاب است) نباید 404 بگیرد."""
    tid = _make_admin(app, email='teacheradmin@test.ir')
    with app.app_context():
        u = db.session.get(User, tid)
        u.role = 'admin'
        cat = Category.query.first()
        db.session.add(Course(title='دوره مدرس ادمین', slug='admin-taught',
                              price=0, teacher_id=tid, category_id=cat.id,
                              status='published'))
        db.session.commit()
    r = client.get('/teacher/{}'.format(tid))
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'دوره مدرس ادمین' in body


# ═══════════════ فعالسازی سایت ═══════════════

def test_super_admin_can_force_activate_site(client, app):
    _make_admin(app)
    _login_admin(client, app)
    with app.app_context():
        st = db.session.get(Setting, 'site_active')
        if st:
            st.value = '0'
        else:
            db.session.add(Setting(key='site_active', value='0'))
        db.session.commit()
    tok = _csrf(client, '/admin/go-live')
    r = client.post('/admin/go-live', data={
        '_csrf_token': tok, 'action': 'activate', 'force': '1',
    }, follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        assert db.session.get(Setting, 'site_active').value == '1'
    # سایت واقعاً برای عموم باز شده
    r = client.get('/')
    assert r.status_code == 200
    assert 'maintenance' not in r.headers.get('Location', '')


def test_plain_activation_blocked_without_readiness_and_message(client, app):
    _make_admin(app, email='plainadmin@test.ir', role='admin')
    _login_admin(client, app, email='plainadmin@test.ir')
    with app.app_context():
        st = db.session.get(Setting, 'site_active')
        if st:
            st.value = '0'
        else:
            db.session.add(Setting(key='site_active', value='0'))
        # بدون محتوا و بدون برند
        db.session.commit()
    tok = _csrf(client, '/admin/go-live')
    r = client.post('/admin/go-live', data={
        '_csrf_token': tok, 'action': 'activate', 'force': '1',  # ادمین عادی force ندارد
    }, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert db.session.get(Setting, 'site_active').value == '0'
    body = r.get_data(as_text=True)
    assert 'انتشار انجام نشد' in body or 'ناقص' in body


def test_deactivate_toggle_works(client, app):
    _make_admin(app)
    _login_admin(client, app)
    with app.app_context():
        st = db.session.get(Setting, 'site_active')
        if st:
            st.value = '1'
        else:
            db.session.add(Setting(key='site_active', value='1'))
        db.session.commit()
    tok = _csrf(client, '/admin/go-live')
    r = client.post('/admin/go-live', data={
        '_csrf_token': tok, 'action': 'deactivate',
    }, follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        assert db.session.get(Setting, 'site_active').value == '0'


# ═══════════════ دیدگاههای وبلاگ ═══════════════

def _make_post(app):
    with app.app_context():
        a = User.query.filter(User.role.in_(('admin', 'super_admin'))).first()
        if a is None:
            a = User(name='نویسنده', email='writer@test.ir', phone='09120000201',
                     role='admin', is_active=True)
            a.set_password('writer1234')
            db.session.add(a)
            db.session.flush()
        p = BlogPost(title='پست دیدگاه', slug='comment-post', body='متن پست',
                     author_id=a.id, published=True)
        db.session.add(p)
        db.session.commit()
        return p.id


def test_blog_comment_submit_and_display(client, app):
    _make_post(app)
    r = client.get('/blog/comment-post')
    assert r.status_code == 200
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    r = client.post('/blog/comment-post', data={
        '_csrf_token': tok, 'name': 'نظر دهنده', 'comment': 'متن دیدگاه من',
    }, follow_redirects=False)
    assert r.status_code == 302
    r = client.get('/blog/comment-post')
    body = r.get_data(as_text=True)
    assert 'متن دیدگاه من' in body
    assert 'نظر دهنده' in body


def test_blog_comment_honeypot_rejects_bots(client, app):
    _make_post(app)
    r = client.get('/blog/comment-post')
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/blog/comment-post', data={
        '_csrf_token': tok, 'name': 'ربات', 'comment': 'اسپم', 'website': 'http://spam.ir',
    })
    with app.app_context():
        assert BlogComment.query.filter_by(comment='اسپم').count() == 0


def test_blog_comment_null_approval_is_visible(client, app):
    """دیدگاههای دیتابیس قدیمی با is_approved=NULL نباید از نمایش حذف شوند."""
    _make_post(app)
    with app.app_context():
        p = BlogPost.query.filter_by(slug='comment-post').first()
        c = BlogComment(post_id=p.id, name='قدیمی', comment='دیدگاه قدیمی')
        c.is_approved = None
        db.session.add(c)
        db.session.commit()
    r = client.get('/blog/comment-post')
    body = r.get_data(as_text=True)
    assert 'دیدگاه قدیمی' in body


def test_blog_comment_ip_throttle(client, app):
    _make_post(app)
    r = client.get('/blog/comment-post')
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    for i in range(6):
        client.post('/blog/comment-post', data={
            '_csrf_token': tok, 'name': 'کاربر', 'comment': 'دیدگاه {}'.format(i),
        })
    with app.app_context():
        # حداکثر ۵ دیدگاه در ۱۰ دقیقه از یک IP
        assert BlogComment.query.count() <= 5


# ═══════════════ نصب مجدد داده را پاک نمیکند ═══════════════

def test_run_install_never_overwrites_existing_data(tmp_path, monkeypatch):
    """اجرای نصب روی دیتابیسی که قبلاً کاربر/دسته/تنظیم دارد، داده را دست نمیزند."""
    import installer
    db_path = str(tmp_path / 'reuse.db')
    from sqlalchemy import create_engine
    from app import create_app
    from models import db as _db
    import os as _os
    _os.environ['DATABASE_URL'] = 'sqlite:///' + db_path
    app = create_app()
    app.config['TESTING'] = True
    app.config['INSTALL_GUARD'] = False
    with app.app_context():
        _db.create_all()
        # دادهٔ قبلی سایت
        u = User(name='کاربر قبلی', email='old@site.ir', phone='09120000202',
                 role='student', is_active=True)
        u.set_password('oldpass123')
        _db.session.add(u)
        _db.session.add(Category(name='دسته قبلی', slug='old-cat', sort=1))
        _db.session.add(Setting(key='site_name', value='سایت قبلی'))
        _db.session.add(Course(title='دوره قبلی', slug='old-course', price=5000,
                               status='published'))
        _db.session.commit()

    # هرگز .env واقعی در ریشهٔ مخزن نوشته نشود (آلودگی تست‌های بعدی)
    monkeypatch.setattr(installer, 'write_env_file',
                        lambda *_args, **_kwargs: str(tmp_path / '.env'))
    monkeypatch.setattr(installer, 'mark_installed', lambda meta: None)
    admin = {'name': 'مدیر جدید', 'email': 'new@site.ir', 'password': 'NewPass123!'}
    site = {'name': 'نام جدید', 'desc': '', 'phone': '', 'email': '', 'base_url': ''}
    ok, msg = installer.run_install('sqlite:///' + db_path, admin, site)
    assert ok is True, msg
    with app.app_context():
        # دادهٔ قبلی دست نخورده
        assert User.query.filter_by(email='old@site.ir').first() is not None
        assert Category.query.filter_by(slug='old-cat').first() is not None
        assert Course.query.filter_by(slug='old-course').first() is not None
        # تنظیمات قبلی بازنویسی نشده
        assert _db.session.get(Setting, 'site_name').value == 'سایت قبلی'
        # مدیر جدید هم اضافه شده
        assert User.query.filter_by(email='new@site.ir').first() is not None


# ---------------------------------------------------------------------------
# رگرسیون: تنظیمات JSON خراب نباید صفحه را ۵۰۰ کند
# ---------------------------------------------------------------------------
def test_talent_test_survives_malformed_settings_json(client, app):
    """اگر ادمین JSON نامعتبر در talent_questions ذخیره کند، صفحه باید با
    سوالات پیش‌فرض بالا بیاید — نه خطای ۵۰۰.

    باگ واقعی: بلوک except تابع _get_talent_questions نام _lexc را صدا می‌زد
    که در features.py import نشده بود؛ در نتیجه همان مسیری که قرار بود خطا را
    مهار کند، خودش NameError می‌داد و کل صفحه از کار می‌افتاد.
    """
    with app.app_context():
        db.session.add(Setting(key='talent_questions', value='{not valid json'))
        db.session.commit()
    r = client.get('/talent-test')
    assert r.status_code == 200


def test_talent_test_uses_valid_custom_questions(client, app):
    """JSON معتبر باید واقعاً جایگزین سوالات پیش‌فرض شود."""
    import json as _json
    payload = _json.dumps([
        {'q': 'سوال سفارشی تست', 'o': [['a', 'گزینه یک'], ['b', 'گزینه دو']]},
    ], ensure_ascii=False)
    with app.app_context():
        db.session.add(Setting(key='talent_questions', value=payload))
        db.session.commit()
    r = client.get('/talent-test')
    assert r.status_code == 200
    assert 'سوال سفارشی تست' in r.text
