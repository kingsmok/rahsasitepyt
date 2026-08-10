# -*- coding: utf-8 -*-
"""مدیریت مرکزی آپلودها — پوشه‌های خصوصی در instance/uploads (خارج از static)"""
import os

_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'uploads')
# پوشه‌های عمومی که در static می‌مانند (عمدی — تصاویر سایت)
PUBLIC_FOLDERS = ('media', 'opt')


def uploads_dir(folder):
    """مسیر دایرکتوری یک پوشه آپلود خصوصی"""
    d = os.path.join(_BASE, folder)
    os.makedirs(d, exist_ok=True)
    return d


def uploads_url(folder, filename):
    """URL عمومی برای فایل آپلودی خصوصی — از route محافظت‌شده /uploads سرو می‌شود"""
    return f'/uploads/{folder}/{filename}'
