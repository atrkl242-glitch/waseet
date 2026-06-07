"""
نصوص الهجرة لإضافة جدول الإشعارات (Notifications) وتحديث قاعدة البيانات
"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///waseet.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(300), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

with app.app_context():
    # إنشاء جدول الإشعارات إذا لم يكن موجوداً
    db.create_all()
    print("✓ تم التحقق من وجود جميع الجداول وإنشاء جدول الإشعارات (Notification) بنجاح.")
    
    # التحقق من وجود الأعمدة المطلوبة (للتوافق مع الإصدارات السابقة)
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"✓ الجداول الموجودة في قاعدة البيانات: {tables}")
    
    # إضافة عمود is_banned إذا لم يكن موجوداً (للمستخدمين القدامى)
    if 'user' in tables:
        columns = [c['name'] for c in inspector.get_columns('user')]
        if 'is_banned' not in columns:
            db.session.execute("ALTER TABLE user ADD COLUMN is_banned BOOLEAN DEFAULT 0;")
            db.session.commit()
            print("✓ تم إضافة عمود is_banned إلى جدول المستخدمين.")
        else:
            print("✓ عمود is_banned موجود مسبقاً.")
    
    print("\n✓ جميع عمليات التحديث والهجرة تمت بنجاح!")