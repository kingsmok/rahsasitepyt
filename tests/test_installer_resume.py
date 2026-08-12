# -*- coding: utf-8 -*-
"""رگرسیون نصب روی هاست‌هایی که background thread را متوقف می‌کنند."""
import json

from sqlalchemy import create_engine, inspect, text

import installer


def test_request_install_resumes_without_background_thread(tmp_path, monkeypatch):
    """هر درخواست چند جدول بسازد و درخواست آخر seed/marker را کامل کند."""
    db_path = tmp_path / 'resume.db'
    state_path = tmp_path / '.install_progress.json'
    marked = []

    monkeypatch.setattr(installer, '_INSTALL_STATE_FILE', str(state_path))
    monkeypatch.setattr(installer, 'INSTANCE_DIR', str(tmp_path))
    monkeypatch.setattr(installer, '_install_state', {
        'status': 'idle', 'step': 0, 'steps': 5, 'msg': '', 'ok': False,
    })
    monkeypatch.setattr(installer, 'write_env_file',
                        lambda *_args, **_kwargs: str(tmp_path / '.env'))
    monkeypatch.setattr(installer, 'mark_installed', lambda meta: marked.append(meta))

    admin = {
        'name': 'مدیر تست',
        'email': 'resume@example.com',
        'password': 'TestPass123!',
    }
    site = {
        'name': 'سایت تست', 'desc': '', 'phone': '', 'email': '',
        'base_url': '',
    }
    db_url = 'sqlite:///' + str(db_path)

    statuses = []
    for _ in range(30):
        result, _msg, state = installer.run_install_request(
            db_url, admin, site, tables_per_request=7)
        statuses.append(state['status'])
        if result is not None:
            break

    assert statuses[0] == 'waiting'
    assert result is True
    assert statuses[-1] == 'done'
    assert marked

    # state روی دیسک نباید اطلاعات اتصال یا رمز مدیر را نگه دارد.
    disk_state = json.loads(state_path.read_text(encoding='utf-8'))
    assert disk_state['status'] == 'done'
    assert admin['password'] not in state_path.read_text(encoding='utf-8')

    engine = create_engine(db_url)
    assert len(inspect(engine).get_table_names()) >= 60
    with engine.connect() as conn:
        assert conn.execute(text(
            "SELECT COUNT(*) FROM users WHERE email='resume@example.com'"
        )).scalar() == 1
        assert conn.execute(text(
            "SELECT COUNT(*) FROM settings WHERE key='site_name'"
        )).scalar() == 1
    engine.dispose()


def test_inspect_and_attach_existing_sqlite(tmp_path, monkeypatch):
    """دیتابیس آپلودشده تشخیص داده شود و بدون پاک‌شدن وصل گردد."""
    monkeypatch.setattr(installer, 'INSTANCE_DIR', str(tmp_path))
    monkeypatch.setattr(installer, 'MARKER', str(tmp_path / '.installed'))
    env_path = tmp_path / '.env'
    monkeypatch.setattr(installer, 'write_env_file',
                        lambda *_a, **_k: env_path.write_text('SECRET_KEY=x\n') or str(env_path))

    empty = installer.detect_local_data()
    assert empty['sqlite_exists'] is False
    assert empty['sqlite_has_data'] is False

    db_path = tmp_path / 'academy.db'
    engine = create_engine('sqlite:///' + str(db_path))
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, role TEXT)'))
        conn.execute(text('CREATE TABLE courses (id INTEGER PRIMARY KEY, title TEXT)'))
        conn.execute(text('CREATE TABLE settings (`key` TEXT, value TEXT)'))
        conn.execute(text("INSERT INTO users (email, role) VALUES ('a@b.ir', 'super_admin')"))
        conn.execute(text("INSERT INTO settings (`key`, value) VALUES ('site_name', 'آکادمی من')"))
    engine.dispose()

    local = installer.detect_local_data()
    assert local['sqlite_has_data'] is True
    assert local['sqlite_users'] == 1
    assert local['sqlite_site_name'] == 'آکادمی من'

    report = installer.inspect_database('sqlite:///' + str(db_path))
    assert report['ok'] is True
    assert report['has_data'] is True
    assert report['users'] == 1

    ok, msg = installer.attach_existing_database('sqlite:///' + str(db_path))
    assert ok is True
    assert 'پیدا شد' in msg or 'می‌خواند' in msg
    assert (tmp_path / '.installed').exists()


def test_wizard_template_is_valid_utf8():
    """رگرسیون ارور نصب: codec can't decode byte 0xb1 in wizard.html"""
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'templates' / 'install' / 'wizard.html'
    raw = path.read_bytes()
    text = raw.decode('utf-8')  # نباید UnicodeDecodeError بدهد
    assert text.count('</html>') == 1
    assert text.count('</body>') == 1
    assert 'id="attach-box"' in text
    assert 'function inspectDb' in text
    assert 'function loadLocalDetect' in text
    assert 'checkHealth();' in text
    assert '\x00' not in text


def test_source_text_files_are_valid_utf8():
    """قالب‌ها و سورس‌ها باید UTF-8 خالص باشند تا Jinja/نصب‌کننده کرش نکنند."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'instance', 'logs'}
    exts = {'.html', '.js', '.css', '.py', '.md', '.json', '.txt', '.svg'}
    bad = []
    for path in root.rglob('*'):
        if not path.is_file() or path.suffix.lower() not in exts:
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        try:
            path.read_bytes().decode('utf-8')
        except UnicodeDecodeError as exc:
            bad.append('%s: %s' % (path.relative_to(root), exc))
    assert not bad, 'فایل غیر UTF-8:\n' + '\n'.join(bad)


def test_install_wizard_page_renders(client, monkeypatch):
    """GET /install باید HTML بدهد، نه JSON خطای utf-8 codec."""
    import installer as inst
    monkeypatch.setattr(inst, 'is_installed', lambda: False)
    r = client.get('/install')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'utf-8' not in html.lower() or 'charset' in html.lower()
    assert 'codec can' not in html
    assert 'نصب' in html
    assert 'attach-box' in html
    assert 'btn-install' in html
    assert html.count('</html>') == 1


def test_install_detect_and_inspect_endpoints(client):
    """مسیرهای تشخیص/بررسی نباید به‌خاطر import جاافتاده ۵۰۰ بدهند."""
    r = client.get('/install/detect')
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is True
    assert 'sqlite_exists' in data

    r = client.post('/install/inspect-db', json={'db_type': 'sqlite'})
    assert r.status_code == 200
    data = r.get_json()
    assert 'ok' in data
    assert 'msg' in data


def test_read_text_file_tolerates_windows_bytes(tmp_path):
    """فایل .env ویندوزی نباید نصب را با UnicodeDecodeError بترکاند."""
    p = tmp_path / 'env-win'
    p.write_bytes(b'SECRET_KEY=abc\nNOTE=\xb1plus\n')
    text = installer._read_text_file(str(p))
    assert 'SECRET_KEY=abc' in text
    assert 'NOTE=' in text


def test_mysql_table_options_utf8mb4():
    """بررسی اینکه تمام جدول‌ها مشخصات utf8mb4 و InnoDB مای‌اسکیول را دارند."""
    from models import db
    assert len(db.metadata.tables) > 0
    for name, tbl in db.metadata.tables.items():
        assert tbl.kwargs.get('mysql_charset') == 'utf8mb4', f"جدول {name} فاقد mysql_charset=utf8mb4 است"
        assert tbl.kwargs.get('mysql_collate') == 'utf8mb4_unicode_ci', f"جدول {name} فاقد mysql_collate=utf8mb4_unicode_ci است"
        assert tbl.kwargs.get('mysql_engine') == 'InnoDB', f"جدول {name} فاقد mysql_engine=InnoDB است"

