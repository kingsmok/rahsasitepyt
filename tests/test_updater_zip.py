# -*- coding: utf-8 -*-
"""تست مسیر بروزرسانی نصب‌های ZIP (بدون .git) — overlay امن، مانیفست، بکاپ،
تشخیص نسخه از version.txt، تشخیص «توقف» با liveness قفل و مایگریشن امن."""
import json
import os
import time

import pytest
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, create_engine, text

import updater
from updater import (
    UpdateError, _apply_extracted_archive, _local_version_info, _overlay_skip,
    _overlay_tree, _run_data_migrations, _safe_add_column, check_for_update,
    update_progress,
)


def _mini_release(root, version):
    """ساخت یک «ریلیز» ساختگی با فایل‌های ضروری + چند فایل واقعی."""
    root.mkdir(parents=True, exist_ok=True)
    (root / 'app.py').write_text('app-' + version, encoding='utf-8')
    (root / 'models.py').write_text('models-' + version, encoding='utf-8')
    (root / 'passenger_wsgi.py').write_text('# wsgi', encoding='utf-8')
    (root / 'requirements.txt').write_text('flask\n', encoding='utf-8')
    (root / 'templates').mkdir(exist_ok=True)
    (root / 'templates' / 'base.html').write_text('tpl-' + version, encoding='utf-8')
    (root / 'static').mkdir(exist_ok=True)
    (root / 'static' / 'app.css').write_text('css-' + version, encoding='utf-8')


def _apply_archive(monkeypatch, tmp_path, src_root, repo='https://github.com/o/r.git',
                   commit='abc1234', old_requirements=None):
    """اجرای _apply_extracted_archive با مسیرهای موقت — بدون شبکه."""
    instance = tmp_path / 'site' / 'instance'
    instance.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(updater, 'BASE_DIR', str(tmp_path / 'site'))
    monkeypatch.setattr(updater, 'INSTANCE_DIR', str(instance))
    monkeypatch.setattr(updater, 'MANIFEST_FILE', str(instance / '.update_manifest.json'))
    monkeypatch.setattr(
        updater, '_install_changed_dependencies',
        lambda *args, **kwargs: 'وابستگی‌ها تغییری نکرده‌اند.',
    )
    return _apply_extracted_archive(
        str(src_root), repo=repo, old_commit='', old_requirements=old_requirements,
        commit=commit)


# ═══════════════ نسخهٔ محلی از version.txt (نصب ZIP) ═══════════════

def test_local_version_info_reads_version_txt(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, '_current_commit', lambda revision='HEAD': '')
    monkeypatch.setattr(updater, '_read_applied_commit', lambda: '')
    monkeypatch.setattr(updater, 'VERSION_FILE', str(tmp_path / 'version.txt'))
    (tmp_path / 'version.txt').write_text('1.5.0\n', encoding='utf-8')
    info = _local_version_info()
    assert info['kind'] == 'zip'
    assert info['version_txt'] == '1.5.0'
    assert info['label'] == '1.5.0'


def test_check_for_update_zip_compares_version_txt(monkeypatch):
    monkeypatch.setattr(updater, '_select_branch', lambda repo, branch=None: 'main')
    monkeypatch.setattr(updater, '_remote_refs',
                        lambda repo, heads=False: ({'main': 'c' * 40}, ''))
    monkeypatch.setattr(updater, '_local_version_info', lambda: {
        'kind': 'zip', 'commit': '', 'commit_short': '',
        'version_txt': '1.5.0', 'label': '1.5.0',
    })
    monkeypatch.setattr(updater, '_is_git_worktree', lambda: False)

    monkeypatch.setattr(updater, '_remote_version_txt', lambda repo, branch: '1.5.0')
    result = check_for_update('https://github.com/o/r.git')
    assert result['available'] is False
    assert 'یکسان' in result['msg']
    assert result['local_short'] == '1.5.0'
    assert result['local_version'] == '1.5.0'
    assert result['remote_short'] == '1.5.0'

    monkeypatch.setattr(updater, '_remote_version_txt', lambda repo, branch: '1.6.0')
    result = check_for_update('https://github.com/o/r.git')
    assert result['available'] is True
    assert '1.6.0' in result['msg']

    monkeypatch.setattr(updater, '_remote_version_txt', lambda repo, branch: None)
    result = check_for_update('https://github.com/o/r.git')
    assert result['available'] is True  # نامشخص = هرگز مسدود نمی‌کنیم


# ═══════════════ overlay: حفاظت فایل‌های محلی ═══════════════

def test_overlay_preserves_env_uploads_backups_and_existing_htaccess(tmp_path):
    src = tmp_path / 'src'
    dst = tmp_path / 'dst'
    (src / 'static' / 'uploads').mkdir(parents=True)
    (src / 'backups').mkdir(parents=True)
    (dst / 'static' / 'uploads').mkdir(parents=True)
    (dst / 'backups').mkdir(parents=True)

    (src / 'app.py').write_text('new', encoding='utf-8')
    (src / '.env').write_text('NEW ENV', encoding='utf-8')
    (src / '.htaccess').write_text('NEW HTACCESS', encoding='utf-8')
    (src / 'static' / 'uploads' / '.htaccess').write_text('NEW UPLOADS HTACCESS',
                                                          encoding='utf-8')
    (src / 'static' / 'uploads' / 'img.jpg').write_text('x', encoding='utf-8')
    (src / 'backups' / 'x.zip').write_text('x', encoding='utf-8')

    (dst / '.env').write_text('USER ENV', encoding='utf-8')
    (dst / '.htaccess').write_text('USER HTACCESS', encoding='utf-8')
    (dst / 'static' / 'uploads' / '.htaccess').write_text('USER UPLOADS HTACCESS',
                                                          encoding='utf-8')
    (dst / 'static' / 'uploads' / 'img.jpg').write_text('user', encoding='utf-8')
    (dst / 'backups' / 'user.zip').write_text('user', encoding='utf-8')

    changed = _overlay_tree(str(src), str(dst))

    assert (dst / '.env').read_text(encoding='utf-8') == 'USER ENV'
    assert (dst / '.htaccess').read_text(encoding='utf-8') == 'USER HTACCESS'
    assert (dst / 'static' / 'uploads' / '.htaccess').read_text(
        encoding='utf-8') == 'USER UPLOADS HTACCESS'
    assert (dst / 'static' / 'uploads' / 'img.jpg').read_text(
        encoding='utf-8') == 'user'
    assert (dst / 'backups' / 'user.zip').read_text(encoding='utf-8') == 'user'
    assert (dst / 'app.py').read_text(encoding='utf-8') == 'new'
    assert 'app.py' in changed
    # فایل محافظ جدید آپلودها فقط وقتی سایت آن را ندارد ساخته می‌شود:
    (dst / 'static' / 'uploads' / '.htaccess').unlink()
    _overlay_tree(str(src), str(dst))
    assert (dst / 'static' / 'uploads' / '.htaccess').exists()


def test_overlay_skip_rules():
    assert _overlay_skip('.env')
    assert _overlay_skip('instance/whatever.db')
    assert _overlay_skip('static/uploads/x.jpg')
    assert _overlay_skip('backups/site.zip')
    assert _overlay_skip('.git/config')
    assert not _overlay_skip('app.py')
    assert not _overlay_skip('templates/base.html')


# ═══════════════ اعمال آرشیو: مانیفست + بکاپ + حذف امن ═══════════════

def test_apply_archive_writes_manifest_backup_and_deletes_only_stale(monkeypatch, tmp_path):
    site = tmp_path / 'site'
    instance = site / 'instance'
    instance.mkdir(parents=True)
    # فایل‌های محلی کاربر
    (site / '.env').write_text('USER ENV', encoding='utf-8')
    (site / 'static' / 'uploads').mkdir(parents=True)
    (site / 'static' / 'uploads' / 'user.jpg').write_text('user', encoding='utf-8')
    (site / '.htaccess').write_text('USER HTACCESS', encoding='utf-8')

    release1 = tmp_path / 'rel1'
    _mini_release(release1, '1')
    (release1 / 'old_module.py').write_text('old', encoding='utf-8')
    monkeypatch.setattr(updater, 'BASE_DIR', str(site))
    monkeypatch.setattr(updater, 'INSTANCE_DIR', str(instance))
    monkeypatch.setattr(updater, 'MANIFEST_FILE', str(instance / '.update_manifest.json'))
    monkeypatch.setattr(
        updater, '_install_changed_dependencies',
        lambda *args, **kwargs: 'وابستگی‌ها تغییری نکرده‌اند.',
    )

    result1 = _apply_extracted_archive(
        str(release1), repo='https://github.com/o/r.git',
        old_commit='', old_requirements='flask\n', commit='1111111')
    assert (site / 'app.py').read_text(encoding='utf-8') == 'app-1'
    assert (site / 'old_module.py').exists()
    assert (site / '.env').read_text(encoding='utf-8') == 'USER ENV'
    assert (site / '.htaccess').read_text(encoding='utf-8') == 'USER HTACCESS'
    assert (site / 'static' / 'uploads' / 'user.jpg').exists()
    # مانیفست و بکاپ ساخته شده‌اند:
    manifest = json.loads((instance / '.update_manifest.json').read_text(encoding='utf-8'))
    assert 'app.py' in manifest['files']
    backups = [n for n in os.listdir(instance / 'backups')
               if n.startswith('update-pre-')]
    assert len(backups) == 1

    # ریلیز دوم: old_module حذف شده و app.py تغییر کرده
    release2 = tmp_path / 'rel2'
    _mini_release(release2, '2')
    result2 = _apply_extracted_archive(
        str(release2), repo='https://github.com/o/r.git',
        old_commit='', old_requirements='flask\n', commit='2222222')
    assert (site / 'app.py').read_text(encoding='utf-8') == 'app-2'
    assert not (site / 'old_module.py').exists()  # فقط فایل منسوخِ مدیریت‌شده
    assert 'old_module.py' in result2[3]           # در لیست removed
    assert (site / '.env').read_text(encoding='utf-8') == 'USER ENV'
    assert (site / 'static' / 'uploads' / 'user.jpg').exists()
    manifest2 = json.loads((instance / '.update_manifest.json').read_text(encoding='utf-8'))
    assert 'old_module.py' not in manifest2['files']


def test_apply_archive_failure_restores_previous_files(monkeypatch, tmp_path):
    site = tmp_path / 'site'
    instance = site / 'instance'
    instance.mkdir(parents=True)
    (site / 'app.py').write_text('old-app', encoding='utf-8')

    release = tmp_path / 'rel'
    _mini_release(release, '2')

    monkeypatch.setattr(updater, 'BASE_DIR', str(site))
    monkeypatch.setattr(updater, 'INSTANCE_DIR', str(instance))
    monkeypatch.setattr(updater, 'MANIFEST_FILE', str(instance / '.update_manifest.json'))
    monkeypatch.setattr(
        updater, '_install_changed_dependencies',
        lambda *args, **kwargs: 'وابستگی‌ها تغییری نکرده‌اند.',
    )

    def boom(src_root, dest_root, progress_cb=None):
        raise OSError('disk full')

    monkeypatch.setattr(updater, '_overlay_tree', boom)
    with pytest.raises(UpdateError):
        _apply_extracted_archive(
            str(release), repo='https://github.com/o/r.git',
            old_commit='', old_requirements='flask\n', commit='3333333')
    assert (site / 'app.py').read_text(encoding='utf-8') == 'old-app'


# ═══════════════ تشخیص «توقف» با liveness قفل ═══════════════

def test_update_progress_not_stale_when_lock_pid_alive(monkeypatch, tmp_path):
    state_file = tmp_path / '.update_progress.json'
    lock_file = tmp_path / '.update.lock'
    monkeypatch.setattr(updater, 'STATE_FILE', str(state_file))
    monkeypatch.setattr(updater, 'LOCK_FILE', str(lock_file))
    monkeypatch.setattr(updater, '_load', lambda: None)
    lock_file.write_text(str(os.getpid()), encoding='utf-8')
    old = time.time() - updater.STALE_SECONDS - 3600
    with updater._state_lock:
        updater._state.update({'status': 'running', 'step': 2, 'msg': 'x',
                               'ok': False, '_updated': old})
    progress = update_progress()
    assert progress['status'] == 'running'
    assert progress.get('long_running') is True
    assert 'stale' not in progress or progress['stale'] is False


def test_update_progress_stale_when_no_live_lock(monkeypatch, tmp_path):
    state_file = tmp_path / '.update_progress.json'
    lock_file = tmp_path / '.update.lock'
    monkeypatch.setattr(updater, 'STATE_FILE', str(state_file))
    monkeypatch.setattr(updater, 'LOCK_FILE', str(lock_file))
    monkeypatch.setattr(updater, '_load', lambda: None)
    lock_file.write_text(str(99999999), encoding='utf-8')  # PID مرده
    old = time.time() - updater.STALE_SECONDS - 3600
    with updater._state_lock:
        updater._state.update({'status': 'running', 'step': 2, 'msg': 'x',
                               'ok': False, '_updated': old})
    progress = update_progress()
    assert progress['status'] == 'error'
    assert 'بروزرسانی متوقف شده' in progress['msg']


# ═══════════════ مایگریشن: ستون جدید + SQLite fallback + داده ═══════════════

def test_safe_add_column_sqlite_nonconstant_default_falls_back(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 't.db'))
    metadata = MetaData()
    table = Table('things', metadata,
                  Column('id', Integer, primary_key=True),
                  Column('name', String(50), nullable=False, default='x'))
    table.create(engine)
    with engine.begin() as conn:
        conn.execute(table.insert().values(name='first'))
    from models import utcnow
    column = Column('created_at', DateTime, nullable=False, default=utcnow)
    result = _safe_add_column(engine, table, column)
    assert result in ('added', 'added_nullable')
    # رکورد قبلی حفظ شده و backfill شده است:
    with engine.connect() as conn:
        rows = conn.execute(text('SELECT name FROM things')).fetchall()
    assert len(rows) == 1 and rows[0][0] == 'first'


def test_safe_add_column_tolerates_existing_column(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 't.db'))
    metadata = MetaData()
    table = Table('things2', metadata,
                  Column('id', Integer, primary_key=True),
                  Column('name', String(50)))
    table.create(engine)
    result = _safe_add_column(engine, table, Column('name', String(50)))
    assert result == 'exists'


def test_data_migrations_run_once_per_version(monkeypatch, tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'd.db'))
    migrations_dir = tmp_path / 'migrations'
    migrations_dir.mkdir()
    (migrations_dir / '0001_seed.py').write_text(
        "from sqlalchemy import text\n"
        "def up(conn):\n"
        "    conn.execute(text('CREATE TABLE seeded (v TEXT)'))\n"
        "    conn.execute(text(\"INSERT INTO seeded VALUES ('one')\"))\n",
        encoding='utf-8')
    (migrations_dir / '_notes.py').write_text('ignored', encoding='utf-8')
    (migrations_dir / 'README.txt').write_text('ignored', encoding='utf-8')
    monkeypatch.setattr(updater, 'MIGRATIONS_DIR', str(migrations_dir))

    ran = _run_data_migrations(engine)
    assert ran == ['0001_seed.py']
    with engine.connect() as conn:
        rows = conn.execute(text('SELECT v FROM seeded')).fetchall()
        assert rows == [('one',)]

    # اجرای دوم: هیچ مایگریشنی دوباره اجرا نمی‌شود
    assert _run_data_migrations(engine) == []
    with engine.connect() as conn:
        rows = conn.execute(text('SELECT COUNT(*) FROM seeded')).fetchone()
        assert rows[0] == 1


def test_failed_data_migration_blocks_and_rolls_back(monkeypatch, tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'd2.db'))
    migrations_dir = tmp_path / 'migrations'
    migrations_dir.mkdir()
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE seeded (v TEXT)'))
    (migrations_dir / '0001_bad.py').write_text(
        "from sqlalchemy import text\n"
        "def up(conn):\n"
        "    conn.execute(text(\"INSERT INTO seeded VALUES ('partial')\"))\n"
        "    raise RuntimeError('boom')\n",
        encoding='utf-8')
    monkeypatch.setattr(updater, 'MIGRATIONS_DIR', str(migrations_dir))
    with pytest.raises(UpdateError, match='0001_bad'):
        _run_data_migrations(engine)
    # تراکنش rollback شده: INSERT مایگریشن commit نشده و نسخه ثبت نشده است
    with engine.connect() as conn:
        assert conn.execute(
            text('SELECT COUNT(*) FROM seeded')).fetchone()[0] == 0
        assert conn.execute(
            text('SELECT COUNT(*) FROM schema_migrations')).fetchone()[0] == 0
