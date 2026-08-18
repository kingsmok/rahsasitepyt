#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ساخت ZIP قابل تحویل مشتری با public key و بدون اسرار/داده runtime.

نمونه:
  python scripts/build_commercial_package.py \
    --public-key license_public_key.pem \
    --output releases/academy-business-1.0.0.zip \
    --version 1.0.0
"""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives import serialization
from licensing import load_public_key

_ALWAYS_EXCLUDE = (
    '.git/', '.github/', '.venv/', 'venv/', 'env/', 'logs/', 'instance/',
    '__pycache__/', '.pytest_cache/', 'releases/',
)
_SECRET_NAMES = (
    'license_private_key.pem', 'vendor_license_private.pem', '.env',
    '.env.local', 'id_rsa', 'id_ed25519',
)
_COMMERCIAL_EXCLUDE_FILES = {
    # فقط داده توسعه seed؛ نصب مشتری هیچ محتوای نمایشی نمی‌سازد.
    'static/video/sample.mp4',
}
_PRIVATE_PEM_RE = re.compile(
    br'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----\r?\n.{40,}?'
    br'-----END [A-Z0-9 ]*PRIVATE KEY-----', re.DOTALL)


def _git(*args):
    result = subprocess.run(['git'] + list(args), cwd=str(ROOT),
                            check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _source_files(include_tests=False, include_untracked=False):
    files = []
    git_args = ['ls-files']
    if include_untracked:
        # --allow-dirty فقط برای build آزمایشی است؛ فایل‌های جدیدِ هنوز commit‌نشده
        # را هم می‌آوریم تا ZIP آزمایشی به‌خاطر حذف ماژول تازه شکسته نباشد.
        git_args.extend(['--cached', '--others', '--exclude-standard'])
    for relative in sorted(set(_git(*git_args).splitlines())):
        relative = relative.strip().replace('\\', '/')
        if (not relative or relative in _COMMERCIAL_EXCLUDE_FILES or
                any(relative.startswith(prefix) for prefix in _ALWAYS_EXCLUDE)):
            continue
        if not include_tests and relative.startswith('tests/'):
            continue
        lower_name = Path(relative).name.lower()
        if lower_name in _SECRET_NAMES or 'private' in lower_name and lower_name.endswith('.pem'):
            raise RuntimeError('فایل حساس در Git شناسایی شد: ' + relative)
        path = ROOT / relative
        if path.is_file():
            files.append((relative, path))
    return files


def _sha256(content):
    return hashlib.sha256(content).hexdigest()


def build_package(public_key_path, output_path, version, include_tests=False,
                  allow_dirty=False):
    if not allow_dirty and _git('status', '--porcelain'):
        raise RuntimeError('مخزن تغییر commit‌نشده دارد؛ ابتدا commit کنید یا --allow-dirty بزنید.')
    public_path = Path(public_key_path).expanduser().resolve()
    public_content = public_path.read_bytes()
    public_key = load_public_key(public_content)
    public_raw = public_key.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    fingerprint = hashlib.sha256(public_raw).hexdigest()

    output = Path(output_path).expanduser().resolve()
    if output.suffix.lower() != '.zip':
        raise RuntimeError('فایل خروجی باید پسوند .zip داشته باشد.')
    try:
        output_relative = output.relative_to(ROOT)
    except ValueError:
        output_relative = None
    if output_relative is not None and (
            not output_relative.parts or output_relative.parts[0] != 'releases'):
        raise RuntimeError('خروجی داخل مخزن فقط باید زیر پوشه releases/ باشد.')
    output.parent.mkdir(parents=True, exist_ok=True)

    sources = _source_files(include_tests=include_tests,
                            include_untracked=allow_dirty)
    manifest_files = {}
    archive_entries = []
    for relative, path in sources:
        content = path.read_bytes()
        if _PRIVATE_PEM_RE.search(content):
            raise RuntimeError('محتوای private key در فایل شناسایی شد: ' + relative)
        archive_entries.append((relative, content))
        manifest_files[relative] = _sha256(content)
    # public key فروشنده، حتی اگر untracked باشد، با نام ثابت داخل بسته قرار می‌گیرد.
    archive_entries = [item for item in archive_entries
                       if item[0] != 'license_public_key.pem']
    archive_entries.append(('license_public_key.pem', public_content))
    manifest_files['license_public_key.pem'] = _sha256(public_content)

    manifest = {
        'product': 'Academy LMS', 'version': version,
        'built_at': datetime.now(timezone.utc).isoformat(),
        'git_commit': _git('rev-parse', 'HEAD'),
        'license_algorithm': 'Ed25519',
        'public_key_fingerprint_sha256': fingerprint,
        'files': dict(sorted(manifest_files.items())),
    }
    archive_entries.append((
        'COMMERCIAL-BUILD.json',
        json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8'),
    ))

    temp_output = output.with_name(output.name + '.tmp.zip')
    try:
        with zipfile.ZipFile(str(temp_output), 'w', zipfile.ZIP_DEFLATED,
                             compresslevel=9) as archive:
            for relative, content in sorted(archive_entries):
                info = zipfile.ZipInfo(relative)
                info.date_time = (2026, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED
                # اسکریپت‌های deployment بعد از unzip باید مستقیم اجراشدنی بمانند.
                mode = 0o755 if relative.endswith('.sh') else 0o644
                info.external_attr = mode << 16
                archive.writestr(info, content)
        # پیش از جایگزینی خروجی نهایی، همان ZIP موقت با verifier مستقل بررسی شود.
        from scripts.verify_commercial_package import verify_package
        verify_package(temp_output)
        os.replace(str(temp_output), str(output))
    finally:
        try:
            temp_output.unlink()
        except OSError:
            pass
    return output, manifest


def main():
    parser = argparse.ArgumentParser(description='ساخت بسته تجاری امن Academy LMS')
    parser.add_argument('--public-key', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--include-tests', action='store_true')
    parser.add_argument('--allow-dirty', action='store_true',
                        help='فقط برای build آزمایشی؛ برای تحویل مشتری استفاده نشود')
    args = parser.parse_args()
    try:
        output, manifest = build_package(
            args.public_key, args.output, args.version,
            include_tests=args.include_tests, allow_dirty=args.allow_dirty)
    except Exception as exc:
        print('ERROR:', exc, file=sys.stderr)
        return 1
    print('بسته تجاری ساخته شد:', output)
    print('commit:', manifest['git_commit'])
    print('public key fingerprint:', manifest['public_key_fingerprint_sha256'])
    print('files:', len(manifest['files']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
