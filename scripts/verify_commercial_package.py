#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اعتبارسنجی آفلاین ZIP تجاری پیش از تحویل یا نصب.

این ابزار امضای لایسنس مشتری را بررسی نمی‌کند؛ ساختار ZIP، نبود اسرار runtime،
hash همه فایل‌ها و fingerprint کلید عمومی فروشنده را کنترل می‌کند.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives import serialization
from licensing import load_public_key

_MANIFEST_NAME = 'COMMERCIAL-BUILD.json'
_MAX_MANIFEST = 2 * 1024 * 1024
_MAX_FILES = 5000
_MAX_FILE_SIZE = 100 * 1024 * 1024
_MAX_TOTAL_SIZE = 512 * 1024 * 1024
_PRIVATE_PEM_RE = re.compile(
    br'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----\r?\n.{40,}?'
    br'-----END [A-Z0-9 ]*PRIVATE KEY-----', re.DOTALL)
_FORBIDDEN_EXACT = {'.env', '.env.local', 'instance/license.json'}
_FORBIDDEN_PREFIXES = ('instance/', 'logs/', '.git/', '.venv/', 'venv/')


def _safe_name(name):
    if not name or '\\' in name or '//' in name or name.startswith('/'):
        return False
    path = PurePosixPath(name)
    return not any(part in ('', '.', '..') for part in path.parts)


def verify_package(package_path):
    package = Path(package_path).expanduser().resolve()
    if not package.is_file() or package.suffix.lower() != '.zip':
        raise ValueError('فایل ZIP تجاری پیدا نشد.')

    with zipfile.ZipFile(str(package)) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError('ZIP دارای نام فایل تکراری است.')
        if not names or len(names) > _MAX_FILES + 1:
            raise ValueError('تعداد فایل‌های ZIP نامعتبر است.')
        if any(not _safe_name(name) for name in names):
            raise ValueError('مسیر ناامن داخل ZIP شناسایی شد.')
        if any(info.flag_bits & 0x1 for info in infos):
            raise ValueError('فایل رمزگذاری‌شده داخل ZIP مجاز نیست.')
        if any(stat.S_ISLNK(info.external_attr >> 16) for info in infos):
            raise ValueError('symlink داخل ZIP تجاری مجاز نیست.')
        if any(info.file_size > _MAX_FILE_SIZE for info in infos) or \
                sum(info.file_size for info in infos) > _MAX_TOTAL_SIZE:
            raise ValueError('حجم بازشده ZIP بیش از سقف مجاز است.')
        if _MANIFEST_NAME not in names:
            raise ValueError('manifest تجاری داخل ZIP وجود ندارد.')
        manifest_info = archive.getinfo(_MANIFEST_NAME)
        if manifest_info.file_size > _MAX_MANIFEST:
            raise ValueError('manifest تجاری بیش از حد بزرگ است.')
        try:
            manifest = json.loads(archive.read(_MANIFEST_NAME).decode('utf-8'))
        except (UnicodeError, ValueError, TypeError) as exc:
            raise ValueError('manifest تجاری JSON معتبر نیست.') from exc
        if not isinstance(manifest, dict) or manifest.get('license_algorithm') != 'Ed25519':
            raise ValueError('الگوریتم manifest تجاری معتبر نیست.')
        files = manifest.get('files')
        if not isinstance(files, dict) or not files or len(files) > _MAX_FILES:
            raise ValueError('فهرست فایل‌های manifest معتبر نیست.')
        expected_names = set(files) | {_MANIFEST_NAME}
        if set(names) != expected_names:
            missing = sorted(expected_names - set(names))
            extra = sorted(set(names) - expected_names)
            raise ValueError('فهرست ZIP با manifest یکسان نیست؛ missing=%s extra=%s' %
                             (missing[:3], extra[:3]))
        if 'license_public_key.pem' not in files:
            raise ValueError('کلید عمومی لایسنس داخل manifest نیست.')

        checked = 0
        for name, expected_hash in files.items():
            if not _safe_name(name) or name in _FORBIDDEN_EXACT or \
                    name.startswith(_FORBIDDEN_PREFIXES):
                raise ValueError('فایل runtime/حساس داخل ZIP شناسایی شد: ' + str(name))
            if not isinstance(expected_hash, str) or not re.match(r'^[0-9a-f]{64}$', expected_hash):
                raise ValueError('SHA-256 نامعتبر برای فایل: ' + str(name))
            content = archive.read(name)
            if _PRIVATE_PEM_RE.search(content):
                raise ValueError('private key داخل ZIP شناسایی شد: ' + str(name))
            actual_hash = hashlib.sha256(content).hexdigest()
            if actual_hash != expected_hash:
                raise ValueError('SHA-256 فایل با manifest تطابق ندارد: ' + str(name))
            checked += 1

        public = load_public_key(archive.read('license_public_key.pem'))
        public_raw = public.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        actual_fingerprint = hashlib.sha256(public_raw).hexdigest()
        expected_fingerprint = str(
            manifest.get('public_key_fingerprint_sha256') or '').lower()
        if actual_fingerprint != expected_fingerprint:
            raise ValueError('fingerprint کلید عمومی با manifest تطابق ندارد.')

    return {
        'ok': True,
        'package': str(package),
        'product': str(manifest.get('product') or ''),
        'version': str(manifest.get('version') or ''),
        'git_commit': str(manifest.get('git_commit') or ''),
        'public_key_fingerprint_sha256': actual_fingerprint,
        'files': checked,
    }


def main():
    parser = argparse.ArgumentParser(description='بررسی یکپارچگی ZIP تجاری Academy LMS')
    parser.add_argument('package', help='مسیر فایل .zip')
    args = parser.parse_args()
    try:
        result = verify_package(args.package)
    except (OSError, ValueError, zipfile.BadZipFile, KeyError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
