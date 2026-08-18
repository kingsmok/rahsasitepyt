#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ابزار آفلاین فروشنده برای ساخت کلید و صدور لایسنس.

کلید خصوصی را روی سیستم فروشنده نگه دارید و هرگز همراه ZIP مشتری نفرستید.

نمونه:
  python scripts/license_tool.py keygen --private ~/academy-vendor-private.pem \
      --public license_public_key.pem
  python scripts/license_tool.py issue --private ~/academy-vendor-private.pem \
      --license-id ACME-2026-001 --customer "مشتری نمونه" \
      --domains academy.example.com,www.academy.example.com \
      --expires 2027-08-17 --plan business
"""
from __future__ import print_function

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from licensing import (LicenseManager, issue_token, load_private_key,
                       load_public_key)


def _write_private(path, content):
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise SystemExit('فایل کلید خصوصی از قبل وجود دارد؛ برای امنیت بازنویسی نشد: %s' % path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(str(path), flags, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(content)
    print('کلید خصوصی ساخته شد:', path)
    print('⚠️ این فایل را در Git، ZIP مشتری یا هاست مشتری قرار ندهید.')


def _password_from_env(name):
    if not name:
        return None
    value = os.environ.get(name, '')
    if len(value) < 12:
        raise SystemExit('رمز کلید خصوصی در متغیر %s باید حداقل ۱۲ کاراکتر باشد.' % name)
    return value.encode('utf-8')


def command_keygen(args):
    private_path = Path(args.private).expanduser().resolve()
    public_path = Path(args.public).expanduser().resolve()
    if private_path == public_path:
        raise SystemExit('مسیر کلید خصوصی و عمومی باید متفاوت باشد.')
    if private_path.exists() or public_path.exists():
        existing = private_path if private_path.exists() else public_path
        raise SystemExit('فایل کلید از قبل وجود دارد؛ برای امنیت بازنویسی نشد: %s' % existing)
    key = Ed25519PrivateKey.generate()
    password = _password_from_env(args.password_env)
    encryption = (serialization.BestAvailableEncryption(password)
                  if password else serialization.NoEncryption())
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    )
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    _write_private(private_path, private_pem)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        public_fd = os.open(str(public_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                            0o644)
        with os.fdopen(public_fd, 'wb') as public_handle:
            public_handle.write(public_pem)
    except Exception:
        # جفت ناقص قابل استفاده نیست؛ فقط همان private key ساخته‌شده در این اجرا
        # پاک می‌شود و هیچ فایل قبلی بازنویسی نمی‌شود.
        try:
            private_path.unlink()
        except OSError:
            pass
        raise
    print('کلید عمومی ساخته شد:', public_path)
    print('فقط فایل عمومی را همراه بسته تجاری توزیع کنید.')


def command_issue(args):
    private_path = Path(args.private).expanduser()
    key = load_private_key(private_path.read_bytes(),
                           password=_password_from_env(args.password_env))
    domains = [item.strip() for item in args.domains.split(',') if item.strip()]
    features = [item.strip() for item in args.features.split(',') if item.strip()]
    payload = {
        'license_id': args.license_id,
        'customer': args.customer,
        'domains': domains,
        'expires_at': args.expires or None,
        'plan': args.plan,
        'features': features or ['*'],
    }
    token = issue_token(key, payload)
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            token_fd = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                               0o600)
        except FileExistsError:
            raise ValueError('فایل خروجی از قبل وجود دارد و بازنویسی نشد: %s' % output)
        with os.fdopen(token_fd, 'w', encoding='utf-8') as token_handle:
            token_handle.write(token + '\n')
        print('لایسنس در فایل ذخیره شد:', output)
    else:
        print(token)


def command_verify(args):
    public = load_public_key(Path(args.public).expanduser().read_bytes())
    manager = LicenseManager(public_key=public, enforcement=True,
                             license_file=os.devnull)
    token = Path(args.token_file).read_text(encoding='utf-8').strip() \
        if args.token_file else args.token.strip()
    state = manager.decode_and_verify(token, args.domain)
    print(json.dumps(state.as_public_dict(), ensure_ascii=False, indent=2))
    return 0 if state.valid else 1


def build_parser():
    parser = argparse.ArgumentParser(description='ابزار صدور لایسنس آکادمی')
    sub = parser.add_subparsers(dest='command', required=True)

    keygen = sub.add_parser('keygen', help='ساخت جفت کلید Ed25519')
    keygen.add_argument('--private', required=True, help='مسیر امن کلید خصوصی فروشنده')
    keygen.add_argument('--public', required=True, help='مسیر کلید عمومی داخل بسته')
    keygen.add_argument('--password-env', default='',
                        help='نام متغیر محیطی رمزگذاری private key (حداقل ۱۲ کاراکتر)')
    keygen.set_defaults(handler=command_keygen)

    issue = sub.add_parser('issue', help='صدور لایسنس امضاشده')
    issue.add_argument('--private', required=True)
    issue.add_argument('--password-env', default='',
                       help='همان متغیر رمز استفاده‌شده هنگام keygen')
    issue.add_argument('--license-id', required=True)
    issue.add_argument('--customer', required=True)
    issue.add_argument('--domains', required=True, help='دامنه‌ها با کاما؛ wildcard مثل *.example.com')
    issue.add_argument('--expires', default='', help='YYYY-MM-DD؛ خالی یعنی بدون انقضا')
    issue.add_argument('--plan', default='standard')
    issue.add_argument('--features', default='*', help='قابلیت‌ها با کاما')
    issue.add_argument('--output', default='')
    issue.set_defaults(handler=command_issue)

    verify = sub.add_parser('verify', help='بررسی توکن و دامنه')
    verify.add_argument('--public', required=True)
    token_group = verify.add_mutually_exclusive_group(required=True)
    token_group.add_argument('--token')
    token_group.add_argument('--token-file')
    verify.add_argument('--domain', required=True)
    verify.set_defaults(handler=command_verify)
    return parser


def main():
    args = build_parser().parse_args()
    try:
        result = args.handler(args)
    except (OSError, ValueError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        return 1
    return int(result or 0)


if __name__ == '__main__':
    raise SystemExit(main())
