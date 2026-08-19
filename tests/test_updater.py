# -*- coding: utf-8 -*-
"""رگرسیون بروزرسانی Git و مایگریشن بدون حذف داده."""
import hashlib
import hmac
import json

from sqlalchemy import inspect, text

import updater
from models import User, db
from updater import (
    UpdateError, _display_repo, _migrate_db, _overlay_skip, _overlay_tree,
    _parse_github, _read_applied_commit, _remote_default_branch, check_for_update,
)


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


def _post_signed_push(client, secret, payload):
    body = json.dumps(payload).encode('utf-8')
    signature = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        '/admin/update/webhook', data=body, content_type='application/json',
        headers={'X-GitHub-Event': 'push', 'X-Hub-Signature-256': signature},
    )


def test_webhook_uses_default_branch_when_git_branch_is_blank(app, client, monkeypatch):
    secret = 'test-webhook-secret'
    calls = []
    monkeypatch.setenv('GITHUB_WEBHOOK_SECRET', secret)
    monkeypatch.setattr('updater.get_update_branch', lambda: '')
    monkeypatch.setattr(
        'updater.start_update',
        lambda repo=None, branch=None: (calls.append(branch) is None, 'started'),
    )
    app.config['INSTALL_GUARD'] = False

    feature = _post_signed_push(client, secret, {
        'ref': 'refs/heads/feature/dangerous',
        'after': 'a' * 40,
        'repository': {'default_branch': 'main'},
    })
    assert feature.status_code == 200
    assert feature.get_json()['ignored'] is True
    assert calls == []

    main = _post_signed_push(client, secret, {
        'ref': 'refs/heads/main',
        'after': 'b' * 40,
        'repository': {'default_branch': 'main'},
    })
    assert main.status_code == 202
    assert main.get_json()['started'] is True
    assert calls == ['main']


def test_webhook_configured_branch_overrides_payload_default(app, client, monkeypatch):
    secret = 'test-webhook-secret'
    calls = []
    monkeypatch.setenv('GITHUB_WEBHOOK_SECRET', secret)
    monkeypatch.setattr('updater.get_update_branch', lambda: 'release')
    monkeypatch.setattr(
        'updater.start_update',
        lambda repo=None, branch=None: (calls.append(branch) is None, 'started'),
    )
    app.config['INSTALL_GUARD'] = False

    ignored = _post_signed_push(client, secret, {
        'ref': 'refs/heads/main',
        'after': 'a' * 40,
        'repository': {'default_branch': 'main'},
    })
    accepted = _post_signed_push(client, secret, {
        'ref': 'refs/heads/release',
        'after': 'b' * 40,
        'repository': {'default_branch': 'main'},
    })

    assert ignored.get_json()['ignored'] is True
    assert accepted.status_code == 202
    assert calls == ['release']


def test_webhook_ignores_deleted_branch(app, client, monkeypatch):
    secret = 'test-webhook-secret'
    monkeypatch.setenv('GITHUB_WEBHOOK_SECRET', secret)
    monkeypatch.setattr('updater.get_update_branch', lambda: 'main')
    monkeypatch.setattr(
        'updater.start_update',
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('must not start')),
    )
    app.config['INSTALL_GUARD'] = False

    response = _post_signed_push(client, secret, {
        'ref': 'refs/heads/main',
        'after': '0' * 40,
        'deleted': True,
        'repository': {'default_branch': 'main'},
    })

    assert response.status_code == 200
    assert response.get_json()['ignored'] is True


def test_parse_github_urls_and_tokens():
    https = _parse_github('https://github.com/kingsmok/rahsasitepyt.git')
    assert https['owner'] == 'kingsmok'
    assert https['name'] == 'rahsasitepyt'
    assert https['token'] == ''

    private = _parse_github('https://very-secret-token@github.com/kingsmok/rahsasitepyt.git')
    assert private['token'] == 'very-secret-token'
    assert private['name'] == 'rahsasitepyt'

    ssh = _parse_github('git@github.com:kingsmok/rahsasitepyt.git')
    assert ssh['owner'] == 'kingsmok'
    assert ssh['name'] == 'rahsasitepyt'


def test_remote_default_branch_falls_back_when_symref_unsupported(monkeypatch):
    """گیت ۱.۸ سی‌پنل --symref ندارد و usage برمی‌گرداند."""
    usage = 'usage: git ls-remote [--heads] [--tags] [-u <exec> | --upload-pack <exec>]'

    def fake_git(args, timeout=120):
        if args[:2] == ['ls-remote', '--symref']:
            return 129, usage
        if args[:2] == ['ls-remote', '--heads']:
            return 0, 'abc123def\trefs/heads/main\ndef456\trefs/heads/dev\n'
        return 1, 'unexpected ' + ' '.join(args)

    monkeypatch.setattr('updater._git', fake_git)
    monkeypatch.setattr('updater._github_heads', lambda repo: {})
    monkeypatch.setattr('updater._github_default_branch', lambda repo: '')
    assert _remote_default_branch('https://github.com/kingsmok/rahsasitepyt.git') == 'main'


def test_check_for_update_works_without_local_git(monkeypatch):
    monkeypatch.setattr('updater.get_update_branch', lambda: '')
    monkeypatch.setattr('updater._current_branch', lambda: '')
    monkeypatch.setattr('updater._is_git_worktree', lambda: False)
    monkeypatch.setattr('updater._current_commit', lambda revision='HEAD': '')
    monkeypatch.setattr('updater._read_applied_commit', lambda: '')
    monkeypatch.setattr(
        'updater._remote_refs',
        lambda repo, heads=False: ({'main': 'abcdef1234567890'}, ''),
    )
    monkeypatch.setattr('updater._remote_default_branch', lambda repo: 'main')

    info = check_for_update('https://github.com/kingsmok/rahsasitepyt.git')
    assert info['ok'] is True
    assert info['available'] is True
    assert info['branch'] == 'main'
    assert info['remote_short'] == 'abcdef1234'


def test_overlay_preserves_env_and_instance(tmp_path):
    src = tmp_path / 'src'
    dest = tmp_path / 'dest'
    src.mkdir()
    (src / 'app.py').write_text('new-app', encoding='utf-8')
    (src / '.env').write_text('SECRET=from-archive', encoding='utf-8')
    (src / 'instance').mkdir()
    (src / 'instance' / 'hack.txt').write_text('nope', encoding='utf-8')
    dest.mkdir()
    (dest / '.env').write_text('SECRET=local', encoding='utf-8')
    (dest / 'instance').mkdir()
    (dest / 'instance' / 'academy.db').write_text('db', encoding='utf-8')
    (dest / 'app.py').write_text('old-app', encoding='utf-8')

    changed = _overlay_tree(str(src), str(dest))
    assert 'app.py' in changed
    assert (dest / 'app.py').read_text(encoding='utf-8') == 'new-app'
    assert (dest / '.env').read_text(encoding='utf-8') == 'SECRET=local'
    assert (dest / 'instance' / 'academy.db').read_text(encoding='utf-8') == 'db'
    assert not (dest / 'instance' / 'hack.txt').exists()
    assert _overlay_skip('.env')
    assert _overlay_skip('instance/foo')
    assert _overlay_skip('static/uploads/a.jpg')


def test_read_applied_commit_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / '.update_commit'
    monkeypatch.setattr('updater.APPLIED_COMMIT_FILE', str(path))
    monkeypatch.setattr('updater.INSTANCE_DIR', str(tmp_path))
    from updater import _write_applied_commit
    _write_applied_commit('B1026B27F6806E8808CB517CDB32BB60210E6EE8')
    assert _read_applied_commit() == 'b1026b27f6806e8808cb517cdb32bb60210e6ee8'


def test_check_for_update_unknown_branch_is_clear(monkeypatch):
    monkeypatch.setattr(
        'updater._remote_refs',
        lambda repo, heads=False: ({'main': 'abc'}, ''),
    )
    try:
        check_for_update('https://github.com/kingsmok/rahsasitepyt.git', branch='no-such-branch')
    except UpdateError as exc:
        assert 'no-such-branch' in str(exc)
    else:
        raise AssertionError('expected UpdateError')


def _mock_git_update_source(monkeypatch, requirements='same'):
    monkeypatch.setattr(updater, '_current_commit', lambda revision='HEAD': 'old-commit')
    monkeypatch.setattr(updater, '_read_local_requirements', lambda: requirements)
    monkeypatch.setattr(updater, '_preserve_local_files', lambda: {})
    monkeypatch.setattr(updater, '_restore_local_files', lambda saved: None)
    monkeypatch.setattr(updater, '_set_step', lambda *args, **kwargs: None)
    monkeypatch.setattr(updater, '_select_branch', lambda repo, branch=None: 'main')
    monkeypatch.setattr(updater, '_ensure_local_git', lambda: True)
    monkeypatch.setattr(
        updater, '_fetch_target', lambda repo, branch: ('target-ref', 'new-commit')
    )
    monkeypatch.setattr(updater, '_verify_target', lambda ref: set(updater._REQUIRED_FILES))
    monkeypatch.setattr(updater, '_changed_files', lambda old, new: ['app.py'])
    monkeypatch.setattr(updater, '_git_file', lambda ref, path: requirements)


def test_dependency_preflight_failure_does_not_replace_code(monkeypatch):
    _mock_git_update_source(monkeypatch, requirements='old')
    git_calls = []

    def fake_git(args, timeout=120):
        git_calls.append(args)
        return 0, 'ok'

    monkeypatch.setattr(updater, '_git', fake_git)
    monkeypatch.setattr(
        updater, '_git_file',
        lambda ref, path: 'new dependency lock',
    )
    monkeypatch.setattr(
        updater, '_install_changed_dependencies',
        lambda *args, **kwargs: (_ for _ in ()).throw(UpdateError('pip failed clearly')),
    )

    try:
        updater._perform_update('https://github.com/example/project.git', 'main')
    except UpdateError as exc:
        assert 'pip failed clearly' in str(exc)
    else:
        raise AssertionError('expected UpdateError')

    assert not any(call[:2] == ['reset', '--hard'] for call in git_calls)


def test_migration_failure_rolls_code_back_to_old_commit(monkeypatch):
    _mock_git_update_source(monkeypatch)
    reset_targets = []

    def fake_git(args, timeout=120):
        if args[:2] == ['reset', '--hard']:
            reset_targets.append(args[2])
        return 0, 'ok'

    monkeypatch.setattr(updater, '_git', fake_git)
    monkeypatch.setattr(
        updater, '_install_changed_dependencies',
        lambda *args, **kwargs: 'وابستگی‌ها تغییری نکرده‌اند.',
    )
    monkeypatch.setattr(updater, '_backup_sqlite_database', lambda: None)
    monkeypatch.setattr(
        updater, '_run_fresh_migration',
        lambda: (_ for _ in ()).throw(UpdateError('migration failed clearly')),
    )
    monkeypatch.setattr(updater, '_clear_python_cache', lambda: None)

    try:
        updater._perform_update('https://github.com/example/project.git', 'main')
    except UpdateError as exc:
        assert 'migration failed clearly' in str(exc)
        assert 'Rollback' in str(exc)
        assert exc.restart_required is True
    else:
        raise AssertionError('expected UpdateError')

    assert reset_targets == ['target-ref', 'old-commit']


def test_archive_code_snapshot_restores_replaced_and_added_files(tmp_path, monkeypatch):
    instance = tmp_path / 'instance'
    instance.mkdir()
    (tmp_path / 'app.py').write_text('old', encoding='utf-8')
    monkeypatch.setattr(updater, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(updater, 'INSTANCE_DIR', str(instance))

    snapshot = updater._snapshot_code_files({'app.py', 'new_module.py'})
    try:
        (tmp_path / 'app.py').write_text('new', encoding='utf-8')
        (tmp_path / 'new_module.py').write_text('new', encoding='utf-8')
        updater._restore_code_snapshot(snapshot)

        assert (tmp_path / 'app.py').read_text(encoding='utf-8') == 'old'
        assert not (tmp_path / 'new_module.py').exists()
    finally:
        updater._cleanup_code_snapshot(snapshot)


def test_sqlite_backup_can_restore_migration_changes(tmp_path, monkeypatch):
    import sqlite3

    instance = tmp_path / 'instance'
    instance.mkdir()
    database = instance / 'academy.db'
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE sample (value TEXT)')
        connection.execute("INSERT INTO sample VALUES ('before')")

    monkeypatch.setattr(updater, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(updater, 'INSTANCE_DIR', str(instance))
    monkeypatch.delenv('DATABASE_URL', raising=False)
    backup = updater._backup_sqlite_database()
    try:
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE sample SET value='after'")
        updater._restore_sqlite_database(backup)
        with sqlite3.connect(database) as connection:
            value = connection.execute('SELECT value FROM sample').fetchone()[0]
        assert value == 'before'
    finally:
        updater._cleanup_sqlite_backup(backup)
