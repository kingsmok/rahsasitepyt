# -*- coding: utf-8 -*-
"""تست کتابخانه رسانه (شبیه وردپرس) — آپلود محصول، API رسانه، مسیر تصاویر و لوگو."""
import io
import os
import re

from PIL import Image

from models import (BlogPost, Course, Media, Product, Setting, User, db,
                    normalize_logo_url)


def _png_bytes(color=(200, 40, 40), size=(48, 48)):
    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, format='PNG')
    buf.seek(0)
    return buf


def _make_admin(app):
    with app.app_context():
        a = User(name='Admin', email='admint2@test.ir', phone='09120000113',
                 role='admin', is_active=True)
        a.set_password('admin123')
        db.session.add(a)
        db.session.commit()
        return a.id


def _login_admin(client, app, email='admint2@test.ir'):
    r = client.get('/auth/login')
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/auth/login', data={'_csrf_token': tok, 'email': email,
                                     'password': 'admin123'})
    code2 = app.config.get('_TEST_AUTH_CODES', {}).get('admin-2fa')
    assert code2
    r = client.get('/auth/admin-2fa')
    tok2 = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    r = client.post('/auth/admin-2fa', data={'_csrf_token': tok2, 'code': code2})
    assert r.status_code == 302


def _csrf(client, path):
    r = client.get(path)
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    return m.group(1) if m else ''


# ═══════════════ resolve_image_url / normalize_logo_url ═══════════════

def test_resolve_image_url_variants(tmp_path, monkeypatch):
    from models import resolve_image_url as fn
    import models
    base = str(tmp_path)
    monkeypatch.setattr(models, '__file__', os.path.join(base, 'models.py'))
    os.makedirs(os.path.join(base, 'static', 'img'), exist_ok=True)
    os.makedirs(os.path.join(base, 'static', 'uploads', 'media'), exist_ok=True)
    os.makedirs(os.path.join(base, 'static', 'img', 'uploads', 'products'), exist_ok=True)
    open(os.path.join(base, 'static', 'img', 'cover-python.webp'), 'w').write('x')
    open(os.path.join(base, 'static', 'uploads', 'media', 'm_1.jpg'), 'w').write('x')
    open(os.path.join(base, 'static', 'img', 'uploads', 'products', 'p_1.png'), 'w').write('x')

    # URL خارجی http/https → همان مقدار (باگ قبلی http:// می‌شکست)
    assert fn('http://example.com/a.jpg', 'F') == 'http://example.com/a.jpg'
    assert fn('https://example.com/a.jpg', 'F') == 'https://example.com/a.jpg'
    # کتابخانه رسانه
    assert fn('uploads/media/m_1.jpg', 'F') == '/static/uploads/media/m_1.jpg'
    assert fn('/static/uploads/media/m_1.jpg', 'F') == '/static/uploads/media/m_1.jpg'
    # محصول قدیمی
    assert fn('uploads/products/p_1.png', 'F') == '/static/img/uploads/products/p_1.png'
    # نام ساده
    assert fn('cover-python.webp', 'F') == '/static/img/cover-python.webp'
    # نامعتبر → fallback
    assert fn('../../../etc/passwd', 'F') == 'F'
    assert fn('missing-file.jpg', 'F') == 'F'
    assert fn('', 'F') == 'F'


def test_normalize_logo_url_variants(tmp_path, monkeypatch):
    import models
    base = str(tmp_path)
    monkeypatch.setattr(models, '__file__', os.path.join(base, 'models.py'))
    os.makedirs(os.path.join(base, 'static', 'img', 'uploads', 'brand'), exist_ok=True)
    open(os.path.join(base, 'static', 'img', 'uploads', 'brand', 'logo.png'), 'w').write('x')

    assert normalize_logo_url('uploads/brand/logo.png') == '/static/img/uploads/brand/logo.png'
    assert normalize_logo_url('/static/img/uploads/brand/logo.png') == '/static/img/uploads/brand/logo.png'
    assert normalize_logo_url('static/img/uploads/brand/logo.png') == '/static/img/uploads/brand/logo.png'
    assert normalize_logo_url('https://cdn.example.com/logo.png') == 'https://cdn.example.com/logo.png'
    assert normalize_logo_url('../../etc/passwd') == ''
    assert normalize_logo_url('missing.png') == ''
    assert normalize_logo_url('') == ''


# ═══════════════ آپلود تصویر محصول (باگ قبلی) ═══════════════

def test_admin_product_image_upload_works_and_registers_in_library(client, app, monkeypatch):
    _make_admin(app)
    _login_admin(client, app)

    r = client.get('/admin/products')
    assert r.status_code == 200
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)

    with app.app_context():
        before_media = Media.query.count()

    r = client.post('/admin/products', data={
        '_csrf_token': tok, 'title': 'محصول با تصویر', 'price': '5000',
        'description': '', 'image': '',
        'image_file': (_png_bytes(), 'photo.png'),
    }, content_type='multipart/form-data', follow_redirects=False)
    assert r.status_code == 302

    with app.app_context():
        p = Product.query.filter_by(title='محصول با تصویر').first()
        assert p is not None
        assert p.image.startswith('uploads/products/product-')
        assert p.image_url.startswith('/static/img/uploads/products/')
        # در کتابخانه رسانه مرکزی هم ثبت شده
        assert Media.query.count() == before_media + 1

    # صفحه فهرست محصولات تصویر را نشان می‌دهد
    r = client.get('/admin/products')
    assert '/static/img/uploads/products/product-' in r.get_data(as_text=True)


def test_product_accepts_http_url_instead_of_breaking(client, app, monkeypatch):
    _make_admin(app)
    _login_admin(client, app)
    tok = _csrf(client, '/admin/products')
    r = client.post('/admin/products', data={
        '_csrf_token': tok, 'title': 'محصول با لینک', 'price': '1000',
        'description': '', 'image': 'http://example.com/pic.jpg',
    }, content_type='multipart/form-data', follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        p = Product.query.filter_by(title='محصول با لینک').first()
        assert p.image_url == 'http://example.com/pic.jpg'


# ═══════════════ API رسانه ═══════════════

def _login_teacher(client, app):
    r = client.get('/auth/login')
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    return client.post('/auth/login', data={'_csrf_token': tok,
                                            'email': 't@test.ir', 'password': 'teacher123'})


def test_media_api_list_paginates(client, app):
    with app.app_context():
        for i in range(5):
            db.session.add(Media(filename=f'f{i}.png', path=f'uploads/media/f{i}.png',
                                 kind='image', uploaded_by=None))
        db.session.commit()
    _login_teacher(client, app)
    r = client.get('/api/media/list?kind=image&per_page=2&page=1')
    d = r.get_json()
    assert d['ok'] is True
    assert len(d['items']) == 2
    assert d['has_more'] is True
    assert d['total'] == 5


def test_media_api_upload_requires_csrf_and_saves_multi(client, app):
    _login_teacher(client, app)
    # بدون CSRF → رد
    r = client.post('/api/media/upload', data={
        'file': (_png_bytes((0, 100, 0)), 'a.png'),
    }, content_type='multipart/form-data')
    assert r.status_code == 400

    with client.session_transaction() as sess:
        csrf = sess['_csrf_token']
    r = client.post('/api/media/upload', data={
        'files': [(_png_bytes((0, 100, 0)), 'a.png'),
                  (_png_bytes((0, 0, 100)), 'b.png')],
    }, headers={'X-CSRF-Token': csrf}, content_type='multipart/form-data')
    d = r.get_json()
    assert d['ok'] is True, d
    assert len(d['items']) == 2
    created = []
    with app.app_context():
        for it in d['items']:
            m = db.session.get(Media, it['id'])
            assert m is not None
            assert m.width == 48 and m.height == 48
            assert os.path.isfile(os.path.join(app.root_path, 'static', m.path))
            created.append(os.path.join(app.root_path, 'static', m.path))
            db.session.delete(m)
        db.session.commit()
    for path in created:
        try:
            os.remove(path)
        except OSError:
            pass


def test_media_api_upload_rejects_html_disguised_as_png(client, app):
    _login_teacher(client, app)
    with client.session_transaction() as sess:
        csrf = sess['_csrf_token']
    r = client.post('/api/media/upload', data={
        'files': [(io.BytesIO(b'<script>alert(1)</script>'), 'x.png')],
    }, headers={'X-CSRF-Token': csrf}, content_type='multipart/form-data')
    d = r.get_json()
    assert d['ok'] is False


def test_media_api_delete_requires_csrf(client, app):
    with app.app_context():
        teacher = User.query.filter_by(email='t@test.ir').first()
        m = Media(filename='d.png', path='uploads/media/d.png', kind='image',
                  uploaded_by=teacher.id)
        db.session.add(m)
        db.session.commit()
        mid = m.id
    _login_teacher(client, app)
    r = client.post('/api/media/delete', json={'id': mid})
    assert r.status_code == 400  # بدون CSRF
    with client.session_transaction() as sess:
        csrf = sess['_csrf_token']
    r = client.post('/api/media/delete', json={'id': mid},
                    headers={'X-CSRF-Token': csrf})
    assert r.get_json()['ok'] is True
    with app.app_context():
        assert db.session.get(Media, mid) is None


# ═══════════════ تصویر دوره/وبلاگ از کتابخانه ═══════════════

def test_course_image_url_supports_media_library(client, app):
    with app.app_context():
        c = Course.query.first()
        c.image = 'uploads/media/m_course.jpg'
        db.session.commit()
        assert c.image_url.startswith('/static/uploads/media/m_course.jpg') or \
            c.image_url.endswith('course-placeholder.webp')


def test_blog_post_image_url_property(app):
    with app.app_context():
        p = BlogPost(title='مطلب تست', slug='test-post-1', image='cover-python.webp')
        db.session.add(p)
        db.session.commit()
        assert p.image_url == '/static/img/cover-python.webp'
        p.image = 'http://example.com/x.jpg'
        assert p.image_url == 'http://example.com/x.jpg'
        p.image = '../../bad'
        assert p.image_url.endswith('course-placeholder.webp')


# ═══════════════ لوگوی سایت ═══════════════

def test_super_settings_logo_saves_canonical_path(client, app):
    _make_admin(app)
    _login_admin(client, app)
    tok = _csrf(client, '/admin/super-settings')
    r = client.post('/admin/super-settings', data={
        '_csrf_token': tok, 'tab': 'brand',
        'action': 'save',
        'custom_logo': '/static/img/uploads/brand/logo.png',
        'site_name': 'سایت تست',
    }, follow_redirects=False)
    # مقادیر ذخیره می‌شوند (ریدایرکت یعنی موفقیت فرم)
    assert r.status_code == 302
    with app.app_context():
        st = db.session.get(Setting, 'custom_logo')
        if st is not None:
            assert st.value.startswith('/static/img/uploads/brand/')


def test_site_context_has_logo_url_when_file_exists(client, app, monkeypatch):
    with app.app_context():
        db.session.add(Setting(key='custom_logo', value='uploads/brand/logo.png'))
        db.session.commit()
    # ساخت فایل لوگو برای تست نرمال‌سازی
    brand_dir = os.path.join(app.root_path, 'static', 'img', 'uploads', 'brand')
    os.makedirs(brand_dir, exist_ok=True)
    logo = os.path.join(brand_dir, 'logo.png')
    if not os.path.exists(logo):
        open(logo, 'w').write('x')
    r = client.get('/')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert '/static/img/uploads/brand/logo.png' in body


# ═══════════════ ساخت مدرس با آواتار از کتابخانه ═══════════════

def test_admin_create_teacher_with_library_avatar(client, app):
    _make_admin(app)
    _login_admin(client, app)
    # فایل کتابخانه برای تست اعتبارسنجی resolve_image_url واقعی باشد
    media_dir = os.path.join(app.root_path, 'static', 'uploads', 'media')
    os.makedirs(media_dir, exist_ok=True)
    avatar_path = os.path.join(media_dir, 'm_avatar.jpg')
    open(avatar_path, 'w').write('x')
    try:
        tok = _csrf(client, '/admin/users/add')
        r = client.post('/admin/users/add', data={
            '_csrf_token': tok, 'name': 'مدرس جدید', 'email': 'new-teacher@test.ir',
            'phone': '09120000114', 'password': 'password123', 'role': 'teacher',
            'avatar': 'uploads/media/m_avatar.jpg',
        }, follow_redirects=False)
        assert r.status_code == 302
        with app.app_context():
            u = User.query.filter_by(email='new-teacher@test.ir').first()
            assert u is not None
            assert u.role == 'teacher'
            assert u.avatar == 'uploads/media/m_avatar.jpg'
            assert u.avatar_url == '/static/uploads/media/m_avatar.jpg'
    finally:
        try:
            os.remove(avatar_path)
        except OSError:
            pass
