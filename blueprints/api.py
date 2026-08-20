# -*- coding: utf-8 -*-
"""API های JSON برای تعاملات جاوااسکریپت"""
import json
from flask import Blueprint, request, jsonify, session, g
from models import db, Course, Favorite, User
from validators import log_exc as _lexc
from jdates import jdate_num

api_bp = Blueprint('api', __name__)


@api_bp.route('/cart/add', methods=['POST'])
def cart_add():
    """افزودن به سبد — اعتبارسنجی ورودی (ضد 500 با داده غیرعددی)"""
    raw = (request.get_json(silent=True) or {}).get('course_id') if request.is_json else request.form.get('course_id')
    try:
        course_id = int(raw or 0)
    except (TypeError, ValueError):
        return jsonify(ok=False, msg='شناسه نامعتبر'), 400
    course = db.session.get(Course, course_id)
    if not course or course.status != 'published':
        return jsonify(ok=False, msg='دوره یافت نشد'), 404
    cart = session.get('cart', [])
    if course.id not in cart:
        cart.append(course.id)
        session['cart'] = cart
    from blueprints.products import _cart_count
    return jsonify(ok=True, count=_cart_count(cart), msg='به سبد خرید اضافه شد')


@api_bp.route('/cart/remove', methods=['POST'])
def cart_remove():
    raw2 = (request.get_json(silent=True) or {}).get('course_id') if request.is_json else request.form.get('course_id')
    try:
        course_id = int(raw2 or 0)
    except (TypeError, ValueError):
        return jsonify(ok=False, msg='شناسه نامعتبر'), 400
    cart = session.get('cart', [])
    if course_id in cart:
        cart.remove(course_id)
        session['cart'] = cart
    from blueprints.products import _cart_count
    return jsonify(ok=True, count=_cart_count(cart))


@api_bp.route('/cart/count')
def cart_count():
    from blueprints.products import _cart_count
    return jsonify(count=_cart_count())


@api_bp.route('/cart/upsell')
def cart_upsell():
    """پیشنهاد لحظه‌ای خرید — دوره‌های مرتبط با دوره اضافه‌شده"""
    course_id = request.args.get('course_id', type=int)
    course = db.session.get(Course, course_id) if course_id else None
    if not course:
        return jsonify(ok=False), 404
    from models import Enrollment
    cart = session.get('cart', [])
    owned = set()
    if g.user:
        owned = {e.course_id for e in Enrollment.query.filter_by(user_id=g.user.id)}
    q = Course.query.filter(Course.status == 'published', Course.id != course.id)
    if course.category_id:
        q = q.filter(Course.category_id == course.category_id)
    candidates = [c for c in q.order_by(Course.views.desc()).limit(6)
                  if c.id not in cart and c.id not in owned]
    pick = None
    if not candidates and course.category_id:
        # هیچ هم‌دسته‌ای نبود → از پرفروش‌ترین‌ها پیشنهاد بده
        candidates = [c for c in Course.query.filter(Course.status == 'published',
                                                     Course.id != course.id)
                      .order_by(Course.views.desc()).limit(6)
                      if c.id not in cart and c.id not in owned]
    if candidates:
        pick = candidates[0]
        return jsonify(ok=True, course={
            'id': pick.id,
            'title': pick.title,
            'slug': pick.slug,
            'image': pick.image,
            'price': pick.price,
            'final_price': pick.final_price,
            'has_discount': pick.has_discount,
            'discount_percent': round((pick.price - pick.final_price) * 100 / pick.price) if pick.has_discount and pick.price else 0,
            'category': pick.category.name if pick.category else '',
        })
    return jsonify(ok=False, msg='پیشنهادی موجود نیست')


@api_bp.route('/favorite/toggle', methods=['POST'])
def favorite_toggle():
    if not g.user:
        return jsonify(ok=False, msg='ابتدا وارد شوید', login=True), 401
    raw = (request.get_json(silent=True) or {}).get('course_id') if request.is_json else request.form.get('course_id')
    try:
        course_id = int(raw or 0)
    except (TypeError, ValueError):
        return jsonify(ok=False, msg='شناسه دوره نامعتبر است'), 400
    course = db.session.get(Course, course_id)
    if not course or course.status != 'published':
        return jsonify(ok=False, msg='دوره یافت نشد'), 404
    fav = Favorite.query.filter_by(user_id=g.user.id, course_id=course_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        return jsonify(ok=True, fav=False, msg='از علاقه‌مندی‌ها حذف شد', count=Favorite.query.filter_by(user_id=g.user.id).count())
    db.session.add(Favorite(user_id=g.user.id, course_id=course_id))
    db.session.commit()
    return jsonify(ok=True, fav=True, msg='به علاقه‌مندی‌ها اضافه شد', count=Favorite.query.filter_by(user_id=g.user.id).count())


@api_bp.route('/form', methods=['POST'])
def submit_form():
    from models import ContactMessage, NewsletterEmail
    data = request.get_json(force=True) if request.is_json else request.form
    fields = data.get('fields') or []
    if isinstance(fields, str):
        try:
            fields = json.loads(fields)
        except Exception:
            fields = []
    name = email = ''
    parts = []
    for f in fields if isinstance(fields, list) else []:
        label = str((f or {}).get('label', '')).strip()
        val = str((f or {}).get('value', '')).strip()
        if not val:
            continue
        parts.append(label + ': ' + val)
        if not name and ('نام' in label or 'name' in label.lower()):
            name = val
        if '@' in val and not email:
            email = val
    to = data.get('to', 'contact')
    if to == 'newsletter' and email:
        if not NewsletterEmail.query.filter_by(email=email).first():
            db.session.add(NewsletterEmail(email=email))
            db.session.commit()
        return jsonify(ok=True, msg='عضویت شما ثبت شد 🎉')
    if name and parts:
        db.session.add(ContactMessage(name=name, email=email or None,
                                      subject='فرم صفحه‌ساز', message='\n'.join(parts)))
        db.session.commit()
        return jsonify(ok=True, msg='پیام شما با موفقیت ارسال شد ✅')
    return jsonify(ok=False, msg='لطفاً فیلدهای الزامی را پر کنید'), 400


@api_bp.route('/contact/read/<int:mid>', methods=['POST'])
def contact_read(mid):
    if not g.user:
        return jsonify(ok=False, msg='ابتدا وارد شوید'), 401
    from permissions import has_any_permission
    if not (g.user.is_admin or has_any_permission(g.user, ('view_consultations', 'manage_settings'))):
        return jsonify(ok=False, msg='دسترسی غیرمجاز'), 403
    from models import ContactMessage
    m = db.session.get(ContactMessage, mid)
    if m:
        m.is_read = True
        db.session.commit()
    return jsonify(ok=True)


@api_bp.route('/media/list')
def media_list():
    """لیست رسانه‌ها برای انتخابگر سراسری فایل (JSON) — با صفحه‌بندی."""
    from models import Media
    kind = request.args.get('kind', '').strip()
    q = request.args.get('q', '').strip()
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = max(1, min(120, int(request.args.get('per_page', 40))))
    except (TypeError, ValueError):
        per_page = 40
    query = Media.query
    if kind in ('image', 'video', 'audio', 'file'):
        query = query.filter_by(kind=kind)
    if q:
        query = query.filter(Media.filename.ilike(f'%{q}%'))
    total = query.count()
    items = query.order_by(Media.id.desc()).offset(
        (page - 1) * per_page).limit(per_page).all()
    return jsonify(ok=True, total=total, page=page, per_page=per_page,
                   has_more=page * per_page < total, items=[{
        'id': m.id, 'name': m.filename, 'url': m.url, 'kind': m.kind,
        'size': m.human_size, 'width': m.width, 'height': m.height,
        'created': jdate_num(m.created_at) if m.created_at else '',
    } for m in items])


def _media_api_csrf_ok():
    """CSRF مخصوص مسیرهای POST رسانه — این مسیرها از گارد سراسری exempt
    هستند (زیر /api)، پس خودمان توکن سشن را چک می‌کنیم."""
    import hmac as _hmac
    token = (request.headers.get('X-CSRF-Token') or
             (request.form or {}).get('_csrf_token') or '')
    expected = session.get('_csrf_token') or ''
    return bool(token) and bool(expected) and _hmac.compare_digest(
        str(token), str(expected))


@api_bp.route('/media/upload', methods=['POST'])
def media_upload():
    """آپلود فایل به کتابخانه مرکزی — فقط ادمین/مدرس (انتخابگر سراسری رسانه)

    نکته امنیتی: قبلاً هر کاربر واردشده (حتی دانشجوی معمولی) می‌توانست از این
    مسیر فایل عمومی (از جمله svg) آپلود کند و لینک آن زیر دامنهٔ خودمان در
    دسترس همه قرار می‌گرفت — دقیقاً همان الگویی که گوگل سیف‌براوزینگ/فایرفاکس
    را به علامت‌گذاری «تلاش برای فریب بازدیدکننده جهت دانلود نرم‌افزار» می‌کشاند.
    """
    if not g.user:
        return jsonify(ok=False, msg='ابتدا وارد شوید', login=True), 401
    if not (g.user.is_admin or g.user.is_teacher):
        return jsonify(ok=False, msg='دسترسی محدود به مدیر/مدرس'), 403
    if not _media_api_csrf_ok():
        return jsonify(ok=False, msg='توکن امنیتی (CSRF) نامعتبر است — صفحه را رفرش کنید.'), 400
    # سهمیه روزانه: حداکثر ۵۰ فایل در ۲۴ ساعت (ضد پر شدن دیسک)
    from models import Media as _M
    from datetime import datetime as _dt, timedelta as _td
    _since = _dt.now() - _td(hours=24)
    _cnt = _M.query.filter(_M.uploaded_by == g.user.id, _M.created_at >= _since).count()
    if _cnt >= 50:
        return jsonify(ok=False, msg='سقف ۵۰ آپلود در روز — فردا دوباره تلاش کنید'), 429
    files = request.files.getlist('files')
    single = request.files.get('file')
    if single and single.filename:
        files = [single] + [f for f in files if f is not single]
    files = [f for f in files if f and f.filename]
    if not files:
        return jsonify(ok=False, msg='فایلی ارسال نشده'), 400
    if len(files) > 20:
        return jsonify(ok=False, msg='حداکثر ۲۰ فایل در هر بار'), 400

    from validators import safe_filename, file_content_is_safe, ALLOWED_MEDIA_EXT
    from models import Media
    import os as _os, uuid as _uuid
    up = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)),
                       'static', 'uploads', 'media')
    _os.makedirs(up, exist_ok=True)
    saved_items = []
    errors = []
    for f in files:
        safe = safe_filename(f.filename or '', ALLOWED_MEDIA_EXT)
        if not safe:
            errors.append('{}: فرمت مجاز نیست'.format(f.filename or 'فایل'))
            continue
        if not file_content_is_safe(f.stream, _os.path.splitext(safe)[1].lower()):
            errors.append('{}: محتوای اجرایی دارد و رد شد'.format(safe))
            continue
        ext = _os.path.splitext(safe)[1].lower()
        fname = 'm_' + _uuid.uuid4().hex[:10] + ext
        fpath = _os.path.join(up, fname)
        f.save(fpath)
        try:
            from uploads_helper import compress_image_file
            compress_image_file(fpath)
        except Exception:
            _lexc('blueprints/api.py')
        size = _os.path.getsize(fpath)
        kind = 'file'
        if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif'):
            kind = 'image'
        elif ext in ('.mp4', '.webm', '.mov'):
            kind = 'video'
        elif ext in ('.mp3', '.wav', '.ogg'):
            kind = 'audio'
        width = height = None
        if kind == 'image':
            try:
                from PIL import Image as _Img
                with _Img.open(fpath) as im:
                    width, height = im.size
            except Exception:
                pass
        m = Media(filename=safe, path='uploads/media/' + fname,
                  mime=f.mimetype or '', size=size, width=width, height=height,
                  kind=kind, uploaded_by=g.user.id)
        db.session.add(m)
        saved_items.append(m)
    db.session.commit()
    if not saved_items and errors:
        return jsonify(ok=False, msg='؛ '.join(errors[:3])), 400
    return jsonify(ok=True, items=[{
        'id': m.id, 'name': m.filename, 'url': m.url, 'kind': m.kind,
        'size': m.human_size, 'width': m.width, 'height': m.height,
    } for m in saved_items], errors=errors[:5])


@api_bp.route('/media/delete', methods=['POST'])
def media_delete():
    """حذف رسانه از طریق API — ادمین یا مالک"""
    from models import Media
    if not _media_api_csrf_ok():
        return jsonify(ok=False, msg='توکن امنیتی (CSRF) نامعتبر است — صفحه را رفرش کنید.'), 400
    raw = (request.get_json(silent=True) or {}).get('id') if request.is_json else request.form.get('id')
    try:
        mid = int(raw or 0)
    except (TypeError, ValueError):
        return jsonify(ok=False, msg='شناسه نامعتبر است'), 400
    m = db.session.get(Media, mid)
    if not m:
        return jsonify(ok=False, msg='یافت نشد'), 404
    if not (g.user and (g.user.is_admin or m.uploaded_by == g.user.id)):
        return jsonify(ok=False, msg='دسترسی ندارید'), 403
    import os as _os
    try:
        p = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'static', m.path)
        if _os.path.exists(p):
            _os.remove(p)
    except Exception:
        _lexc('blueprints/api.py')
    db.session.delete(m)
    db.session.commit()
    return jsonify(ok=True)
