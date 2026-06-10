import os
import sqlite3
import sys

"""
نصوص SQL لإضافة الأعمدة المفقودة إلى الجداول الموجودة.
للاستخدام مع PostgreSQL (ريلاوي) أو SQLite (تطوير محلي).
"""

# تعريف الأعمدة التي نحتاج لإضافتها لكل جدول
COLUMNS_TO_ADD = {
    'user': [
        ('is_banned', 'BOOLEAN DEFAULT 0'),
        ('email_verified', 'BOOLEAN DEFAULT 0'),
        ('otp_code', 'VARCHAR(10)'),
        ('otp_expiry', 'TIMESTAMP'),
    ],
    'account': [
        ('platform', 'VARCHAR(50) DEFAULT \'PC\''),
        ('tags', 'VARCHAR(500)'),
    ],
    'order': [
        ('credentials_submitted_at', 'TIMESTAMP'),
        ('buyer_recovery_data', 'TEXT'),
        ('buyer_recovery_submitted_at', 'TIMESTAMP'),
        ('commission_rate', 'FLOAT DEFAULT 5.0'),
        ('commission_amount', 'FLOAT DEFAULT 0.0'),
        ('admin_fee', 'FLOAT DEFAULT 0.0'),
        ('dispute_resolved_by', 'VARCHAR(100)'),
        ('dispute_winner', 'VARCHAR(100)'),
        ('dispute_resolved_at', 'TIMESTAMP'),
    ],
}