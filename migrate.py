import os
import sqlite3
import sys

# المسار إلى قاعدة البيانات
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'waseet.db')

if not os.path.exists(db_path):
    print(f'❌ قاعدة البيانات غير موجودة في: {db_path}')
    sys.exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('✅ تم الاتصال بقاعدة البيانات.')
print('بدء التحديثات...')

try:
    # 1. إضافة أعمدة التحقق من البريد الإلكتروني إلى جدول User
    cursor.execute("PRAGMA table_info(user)")
    user_columns = [col[1] for col in cursor.fetchall()]
    
    if 'email_verified' not in user_columns:
        cursor.execute("ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 0")
        print('✅ تم إضافة عمود email_verified إلى user')
    else:
        print('ℹ️ عمود email_verified موجود مسبقاً')
    
    if 'otp_code' not in user_columns:
        cursor.execute("ALTER TABLE user ADD COLUMN otp_code VARCHAR(10)")
        print('✅ تم إضافة عمود otp_code إلى user')
    else:
        print('ℹ️ عمود otp_code موجود مسبقاً')
    
    if 'otp_expiry' not in user_columns:
        cursor.execute("ALTER TABLE user ADD COLUMN otp_expiry DATETIME")
        print('✅ تم إضافة عمود otp_expiry إلى user')
    else:
        print('ℹ️ عمود otp_expiry موجود مسبقاً')
    
    # 2. إضافة عمود commission إلى جدول Order
    cursor.execute("PRAGMA table_info('order')")
    order_columns = [col[1] for col in cursor.fetchall()]
    
    if 'commission_amount' not in order_columns:
        cursor.execute("ALTER TABLE 'order' ADD COLUMN commission_amount FLOAT DEFAULT 0")
        print('✅ تم إضافة عمود commission_amount إلى order')
    else:
        print('ℹ️ عمود commission_amount موجود مسبقاً')
    
    if 'commission_rate' not in order_columns:
        cursor.execute("ALTER TABLE 'order' ADD COLUMN commission_rate FLOAT DEFAULT 5.0")
        print('✅ تم إضافة عمود commission_rate إلى order')
    else:
        print('ℹ️ عمود commission_rate موجود مسبقاً')
    
    if 'admin_fee' not in order_columns:
        cursor.execute("ALTER TABLE 'order' ADD COLUMN admin_fee FLOAT DEFAULT 0")
        print('✅ تم إضافة عمود admin_fee إلى order')
    else:
        print('ℹ️ عمود admin_fee موجود مسبقاً')
    
    if 'dispute_resolved_by' not in order_columns:
        cursor.execute("ALTER TABLE 'order' ADD COLUMN dispute_resolved_by VARCHAR(100)")
        print('✅ تم إضافة عمود dispute_resolved_by إلى order')
    else:
        print('ℹ️ عمود dispute_resolved_by موجود مسبقاً')
    
    if 'dispute_winner' not in order_columns:
        cursor.execute("ALTER TABLE 'order' ADD COLUMN dispute_winner VARCHAR(100)")
        print('✅ تم إضافة عمود dispute_winner إلى order')
    else:
        print('ℹ️ عمود dispute_winner موجود مسبقاً')
    
    if 'dispute_resolved_at' not in order_columns:
        cursor.execute("ALTER TABLE 'order' ADD COLUMN dispute_resolved_at DATETIME")
        print('✅ تم إضافة عمود dispute_resolved_at إلى order')
    else:
        print('ℹ️ عمود dispute_resolved_at موجود مسبقاً')
    
    # 3. إضافة عمود tags إلى جدول Account
    cursor.execute("PRAGMA table_info(account)")
    account_columns = [col[1] for col in cursor.fetchall()]
    
    if 'tags' not in account_columns:
        cursor.execute("ALTER TABLE account ADD COLUMN tags VARCHAR(500)")
        print('✅ تم إضافة عمود tags إلى account')
    else:
        print('ℹ️ عمود tags موجود مسبقاً')
    
    if 'game_search_normalized' not in account_columns:
        cursor.execute("ALTER TABLE account ADD COLUMN game_search_normalized VARCHAR(100)")
        print('✅ تم إضافة عمود game_search_normalized إلى account')
    else:
        print('ℹ️ عمود game_search_normalized موجود مسبقاً')

    # 4. تحديث حالات الطلبات القديمة (ترحيل إلى النظام الجديد)
    cursor.execute("SELECT id, status FROM 'order'")
    orders = cursor.fetchall()
    for oid, ostatus in orders:
        new_status = ostatus
        if ostatus == 'Pending_Payment':
            new_status = 'Pending'
        elif ostatus == 'Funds_Held':
            new_status = 'Paid_Hold'
        elif ostatus == 'Disputed':
            new_status = 'In_Dispute'
        elif ostatus == 'Completed':
            new_status = 'Completed'
        elif ostatus == 'Refunded':
            new_status = 'Refunded'
        elif ostatus == 'Credentials_Submitted':
            new_status = 'Paid_Hold'  # تعيين حالة مؤقتة
        elif ostatus == 'Awaiting_Buyer_Recovery':
            new_status = 'In_Dispute'  # تعيين حالة مؤقتة
        
        if new_status != ostatus:
            cursor.execute("UPDATE 'order' SET status = ? WHERE id = ?", (new_status, oid))
            print(f'🔄 تم تحديث حالة الطلب #{oid} من "{ostatus}" إلى "{new_status}"')
    
    conn.commit()
    print('✅ تم حفظ جميع التغييرات في قاعدة البيانات بنجاح!')
    
except Exception as e:
    conn.rollback()
    print(f'❌ حدث خطأ أثناء التحديث: {str(e)}')
finally:
    conn.close()
    print('🔌 تم إغلاق الاتصال بقاعدة البيانات.')