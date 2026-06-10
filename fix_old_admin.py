"""
سكربت لمرة واحدة لتحديث حساب الأدمن القديم (admin) إلى البيانات الجديدة.
يشغّل مرة واحدة فقط ثم يحذف.
"""

import sys
import os

# إضافة مسار المشروع
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, bcrypt

def fix_admin():
    with app.app_context():
        # 1. البحث عن المستخدم القديم الذي اسمه 'admin'
        old_admin = User.query.filter_by(name='admin').first()
        
        if not old_admin:
            print("❌ لم يتم العثور على مستخدم باسم 'admin'. ربما تم تحديثه مسبقاً.")
            return False
        
        print(f"✅ تم العثور على المستخدم القديم: id={old_admin.id}, name='{old_admin.name}', email='{old_admin.email}'")
        
        # 2. التحقق من عدم وجود مستخدم آخر بنفس الاسم الجديد أو الإيميل
        conflict_name = User.query.filter_by(name='Turki.admin').first()
        conflict_email = User.query.filter_by(email='atrk1250@gmail.com').first()
        
        if conflict_name and conflict_name.id != old_admin.id:
            print(f"⚠️ يوجد مستخدم آخر باسم 'Turki.admin' (id={conflict_name.id})")
            print("سيتم حذف المستخدم المكرر أولاً...")
            db.session.delete(conflict_name)
            db.session.flush()
        
        if conflict_email and conflict_email.id != old_admin.id:
            print(f"⚠️ يوجد مستخدم آخر بالإيميل 'atrk1250@gmail.com' (id={conflict_email.id})")
            print("سيتم حذف المستخدم المكرر أولاً...")
            db.session.delete(conflict_email)
            db.session.flush()
        
        # 3. تحديث بيانات الأدمن القديم
        old_admin.name = 'Turki.admin'
        old_admin.email = 'atrk1250@gmail.com'
        
        # 4. تشفير كلمة السر الجديدة
        hashed_password = bcrypt.generate_password_hash('Turki@7070').decode('utf-8')
        old_admin.password = hashed_password
        
        # 5. التأكد من صلاحيات الأدمن
        old_admin.is_admin = True
        old_admin.balance = 100000.0
        
        # 6. حفظ التعديلات
        db.session.commit()
        
        print("\n✅ تم تحديث بيانات الأدمن القديم بنجاح!")
        print(f"   - الاسم الجديد: {old_admin.name}")
        print(f"   - الإيميل الجديد: {old_admin.email}")
        print(f"   - كلمة السر: Turki@7070 (مشفرة)")
        print(f"   - الصلاحية: أدمن ✅")
        print(f"   - الرصيد: {old_admin.balance}")
        
        return True

if __name__ == '__main__':
    success = fix_admin()
    if success:
        print("\n🎉 تمت العملية بنجاح! يمكنك الآن حذف هذا الملف (fix_old_admin.py).")
    else:
        print("\n⚠️ لم يتم إجراء أي تعديل.")