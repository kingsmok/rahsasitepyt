# -*- coding: utf-8 -*-
"""رگرسیون بروزرسانی Git و مایگریشن بدون حذف داده."""
import hashlib
import hmac
import json

from sqlalchemy import inspect, text

from models import User, db
from updater import _display_repo, _migrate_db


def test_database_migration_adds_missing_column_without_losing_rows(app):
    """ستون جاافتاده برگردد و کاربر قبلی همچنان باقی بماند."""
    with app.app_context():
        user = User.query.filter_by(email='demo@test.ir').first()
        user_id = user.id
        with db.engine.begin() as conn:
            conn.execute(text('ALTER TABLE users DROP COLUMN education_major'))

        report = _migrate_db()
        columns = {c['name'] for c in inspect(db.engine).get_columns('users')}
        restored = db.session.get(User, user_id)

        assert 'education_major' in columns
        assert restored is not None
        assert restored.id == user_id
        assert 'ستون جدید' in report


def test_private_repo_is_masked():
    """PAT داخل صفحه/تاریخچه قابل مشاهده نباشد."""
    masked = _display_repo('https://very-secret-token@github.com/kingsmok/rahsasitepyt.git')
    assert 'very-secret-token' not in masked
    assert '***@github.com' in masked


def test_github_webhook_signature_is_required(app, client, monkeypatch):
    """Webhook بدون CSRF اما با امضای HMAC معتبر کار می‌کند."""
    secret = 'test-webhook-secret'
    monkeypatch.setenv('GITHUB_WEBHOOK_SECRET', secret)
    app.config['INSTALL_GUARD'] = False
    body = json.dumps({'zen': 'test'}).encode('utf-8')
    signature = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    response = client.post(
        '/admin/update/webhook', data=body, content_type='application/json',
        headers={'X-GitHub-Event': 'ping', 'X-Hub-Signature-256': signature},
    )
    assert response.status_code == 200
    assert response.get_json()['ok'] is True

    bad = client.post(
        '/admin/update/webhook', data=body, content_type='application/json',
        headers={'X-GitHub-Event': 'ping', 'X-Hub-Signature-256': 'sha256=bad'},
    )
    assert bad.status_code == 401
