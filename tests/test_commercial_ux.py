# -*- coding: utf-8 -*-
"""رگرسیون خطاهایی که فقط در تجربه واقعی محصول دیده می‌شوند."""
from io import BytesIO
import os
import re

from PIL import Image

from conftest import login
from models import Assignment, Course, Enrollment, Product, Quiz, db
from test_admin_panel import _login_admin_2fa, _make_admin


def test_locked_coursework_is_not_a_broken_403_link(client, app):
    with app.app_context():
        course = Course.query.filter_by(slug='test-course').first()
        quiz = Quiz(course_id=course.id, title='آزمون قفل‌شده', is_published=True)
        assignment = Assignment(course_id=course.id, title='تمرین قفل‌شده',
                                is_published=True)
        db.session.add_all([quiz, assignment])
        db.session.commit()
        quiz_id, assignment_id = quiz.id, assignment.id

    guest_page = client.get('/course/test-course')
    assert guest_page.status_code == 200
    assert 'ویژه دانشجویان دوره' in guest_page.text
    assert f'/quiz/{quiz_id}' not in guest_page.text
    assert f'/assignment/{assignment_id}' not in guest_page.text

    login(client, 'demo@test.ir', 'demo123')
    with app.app_context():
        from models import User
        user = User.query.filter_by(email='demo@test.ir').first()
        course = Course.query.filter_by(slug='test-course').first()
        db.session.add(Enrollment(user_id=user.id, course_id=course.id))
        db.session.commit()
    enrolled_page = client.get('/course/test-course')
    assert f'/quiz/{quiz_id}' in enrolled_page.text
    assert f'/assignment/{assignment_id}' in enrolled_page.text


def test_referral_link_hidden_when_feature_is_disabled(client):
    login(client, 'demo@test.ir', 'demo123')
    page = client.get('/dashboard')
    assert page.status_code == 200
    assert '/dashboard/referral' not in page.text


def test_builder_sanitizes_links_styles_and_render_limits(app):
    from blueprints.builder import _sanitize_rows
    rows = [{
        'id': 'bad" onclick="alert(1)',
        'settings': {
            'bg': 'red;background:url(https://evil.example/x)',
            'widths': '1fr;position:fixed', 'css_class': 'ok bad<script>',
            'gap': '999999',
        },
        'cols': [[{
            'id': 'button-1', 'type': 'button',
            'data': {
                'text': 'دکمه ناامن', 'url': 'java\nscript:alert(1)',
                'style': {'bg': 'url(https://evil.example/x)',
                          'width': '100%;position:fixed'},
            },
        }, {
            'id': 'slider-1', 'type': 'slider',
            'data': {'slides': [{
                'title': 'اسلاید', 'btn_text': 'کلیک',
                'btn_url': 'javascript:alert(2)',
            }]},
        }]],
    }]
    cleaned = _sanitize_rows(rows)
    assert len(cleaned) == 1
    assert cleaned[0]['id'] != rows[0]['id']
    assert cleaned[0]['settings']['bg'] == ''
    assert cleaned[0]['settings']['widths'] == ''
    assert cleaned[0]['settings']['css_class'] == ''
    assert cleaned[0]['settings']['gap'] == 2000
    button, slider = cleaned[0]['cols'][0]
    assert button['data']['url'] == ''
    assert button['data']['style']['bg'] == ''
    assert button['data']['style']['width'] == ''
    assert slider['data']['slides'][0]['btn_url'] == ''

    with app.test_request_context('/'):
        html = app.jinja_env.get_template('builder/fragment_row.html').render(
            row=cleaned[0], edit=False)
    assert 'javascript:' not in html
    assert 'evil.example' not in html
    assert 'href="#"' not in html
    assert 'دکمه ناامن' not in html


def test_builder_library_rejects_empty_template_and_uses_instance(client, app):
    import json
    _make_admin(app)
    _login_admin_2fa(client, app, 'admint@test.ir', 'admin123')
    invalid = client.post('/builder/api/page-template', json={})
    assert invalid.status_code == 400
    root_file = os.path.join(app.root_path, 'page_library.json')
    assert not os.path.exists(root_file)

    valid = client.post('/builder/api/page-template', json={
        'name': 'قالب تست تجاری',
        'rows': [{'id': 'row-1', 'settings': {}, 'cols': [[]]}],
        'settings': {'seo_title': 'تست'},
    })
    assert valid.status_code == 200 and valid.get_json()['ok'] is True
    library_file = os.path.join(app.instance_path, 'libraries', 'page_library.json')
    assert os.path.isfile(library_file)
    data = json.loads(open(library_file, encoding='utf-8').read())
    assert data[-1]['name'] == 'قالب تست تجاری'


def test_admin_can_upload_product_image_without_typing_server_path(client, app):
    _make_admin(app)
    _login_admin_2fa(client, app, 'admint@test.ir', 'admin123')
    page = client.get('/admin/products')
    token = re.search(r'name="_csrf_token" value="([^"]+)"', page.text).group(1)
    image = Image.new('RGB', (32, 32), '#f2640c')
    stream = BytesIO()
    image.save(stream, format='PNG')
    stream.seek(0)
    response = client.post('/admin/products', data={
        '_csrf_token': token, 'title': 'محصول تصویردار', 'price': '125000',
        'stock': '4', 'image_file': (stream, 'product.png'),
    }, content_type='multipart/form-data', follow_redirects=False)
    assert response.status_code == 302
    with app.app_context():
        product = Product.query.filter_by(title='محصول تصویردار').first()
        assert product and product.image.startswith('uploads/products/product-')
        relative = product.image
        assert product.image_url == '/static/img/' + relative
        path = os.path.join(app.root_path, 'static', 'img', relative)
        assert os.path.isfile(path)
