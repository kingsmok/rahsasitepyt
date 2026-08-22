# -*- coding: utf-8 -*-
"""رگرسیون اسکریپت مایگریشن: چاپ فارسی روی cp1252 نباید مایگریشن را بکشد."""
import importlib.util
import io
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_ROOT, 'scripts', 'migrate_database.py')
_SPEC = importlib.util.spec_from_file_location('migrate_database_under_test', _SCRIPT)
migrate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(migrate)


class _Cp1252Stream:
    """شبیه‌ساز کنسول ویندوز که فارسی را encode نمی‌کند."""

    encoding = 'cp1252'

    def __init__(self):
        self.writes = []

    def write(self, text):
        text.encode('cp1252')
        self.writes.append(text)
        return len(text)

    def flush(self):
        pass

    def reconfigure(self, **kwargs):
        raise OSError('reconfigure not supported')


def test_database_kind_detects_mysql_and_sqlite():
    assert migrate.database_kind('mysql+pymysql://u:p@localhost/db') == 'mysql'
    assert migrate.database_kind('sqlite:///instance/academy.db') == 'sqlite'
    assert migrate.database_kind('') == 'sqlite'


def test_safe_print_survives_cp1252_console(monkeypatch):
    broken = _Cp1252Stream()
    captured = io.BytesIO()

    class _BufOut:
        encoding = 'cp1252'
        buffer = captured

        def write(self, text):
            text.encode('cp1252')

        def flush(self):
            pass

        def reconfigure(self, **kwargs):
            raise OSError('no')

    monkeypatch.setattr(sys, 'stdout', broken)
    monkeypatch.setattr(sys, 'stderr', _BufOut())
    ok = migrate.safe_print('بکاپ SQLite ساخته شد — (ساختار به‌روز بود)')
    assert ok is True
    assert 'بکاپ'.encode('utf-8') in captured.getvalue()


def test_configure_stdio_does_not_raise_on_dumb_stream(monkeypatch):
    monkeypatch.setattr(sys, 'stdout', _Cp1252Stream())
    monkeypatch.setattr(sys, 'stderr', _Cp1252Stream())
    migrate.configure_stdio()


def test_safe_print_never_raises(monkeypatch):
    class _Dead:
        encoding = 'ascii'

        def write(self, text):
            raise OSError('closed')

        def flush(self):
            pass

    monkeypatch.setattr(sys, 'stdout', _Dead())
    monkeypatch.setattr(sys, 'stderr', _Dead())
    assert migrate.safe_print('بکاپ') in (True, False)
