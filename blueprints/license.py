# -*- coding: utf-8 -*-
"""صفحه فعال‌سازی و وضعیت لایسنس تجاری."""
from flask import (Blueprint, abort, g, jsonify, redirect, render_template,
                   request, url_for)

from licensing import get_license_manager, normalize_domain
from validators import safe_next

license_bp = Blueprint('license', __name__)


def _response_for_state(state, status=200):
    if request.accept_mimetypes.best == 'application/json' or request.path.startswith('/api/'):
        return jsonify(state.as_public_dict()), status
    return render_template('license/activate.html', license_state=state,
                           current_domain=normalize_domain(request.host),
                           message='', message_type=''), status


@license_bp.route('/license', methods=['GET', 'POST'])
def activate():
    manager = get_license_manager()
    domain = normalize_domain(request.host)
    state = manager.status(domain)
    message = ''
    message_type = ''

    if request.method == 'POST':
        action = request.form.get('action', 'activate')
        if action == 'deactivate':
            if not getattr(g, 'user', None) or g.user.role != 'super_admin':
                abort(403)
            if manager.deactivate():
                state = manager.status(domain)
                message = 'لایسنس از این نصب حذف شد.'
                message_type = 'success'
            else:
                message = 'حذف فایل لایسنس ممکن نشد؛ دسترسی پوشه instance را بررسی کنید.'
                message_type = 'error'
        else:
            token = (request.form.get('license_key') or '').strip()
            if len(token) > 20_000:
                message = 'کلید لایسنس بیش از حد بزرگ است.'
                message_type = 'error'
            elif not manager.configured:
                message = ('کلید عمومی فروشنده روی این بسته تنظیم نشده است؛ '
                           'فایل license_public_key.pem را در ریشه برنامه قرار دهید.')
                message_type = 'error'
            elif state.valid and (not getattr(g, 'user', None) or not g.user.is_admin):
                message = 'برای جایگزینی لایسنس فعال، ابتدا با حساب مدیر وارد شوید.'
                message_type = 'error'
            else:
                state = manager.activate(token, domain)
                message = state.message
                message_type = 'success' if state.valid else 'error'
                if state.valid and request.form.get('continue') == '1':
                    target = safe_next(request.args.get('next')) or url_for('admin.go_live')
                    return redirect(target)

    status = 200
    if manager.enforced and not state.valid and request.accept_mimetypes.best == 'application/json':
        status = 402
    return render_template('license/activate.html', license_state=state,
                           current_domain=domain, message=message,
                           message_type=message_type), status


@license_bp.route('/api/license/status')
def api_status():
    state = get_license_manager().status(request.host)
    status = 200 if state.valid or not state.enforced else 402
    return jsonify(state.as_public_dict()), status
