import os
from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import re

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///waseet.db')
app.secret_key = 'waseet123_secure_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # حد أقصى 16 ميجابايت للصورة
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}

# التأكد من وجود مجلد رفع الصور
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
bcrypt = Bcrypt(app)
db = SQLAlchemy(app)
with app.app_context():
    db.create_all()

# ==================== دالة تطبيع النص العربي للبحث ====================
def normalize_arabic_text(text):
    """
    تطبيع النص العربي للبحث المرن:
    - إزالة المسافات
    - توحيد أشكال الألف (أ, إ, آ, ا) → ا
    - توحيد التاء المربوطة (ة, ـة) → ه
    - إزالة الحركات (التشكيل)
    - إزالة علامات الترقيم
    """
    if not text:
        return ''
    text = text.lower().strip()
    # إزالة المسافات
    text = re.sub(r'\s+', '', text)
    # توحيد الألف
    text = re.sub(r'[أإآا]', 'ا', text)
    # توحيد التاء المربوطة والهاء
    text = re.sub(r'[ةـة]', 'ه', text)
    # إزالة الحركات والتشكيل
    text = re.sub(r'[ًٌٍَُِّْ]', '', text)
    # إزالة علامات الترقيم والرموز
    text = re.sub(r'[^\w\s]', '', text)
    return text

# ==================== موديل قاعدة البيانات ====================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Float, default=1000.0) # رصيد افتراضي للتجربة
    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False) # حقل الحظر مضاف

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    price = db.Column(db.Float, nullable=False)
    seller = db.Column(db.String(100), nullable=False)
    platform = db.Column(db.String(50), default='PC') # المنصة: PC, Console, Mobile, Switch, VR, Other
    status = db.Column(db.String(50), default='Available') # Available, Pending, Sold
    image_url = db.Column(db.String(500), nullable=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    buyer_name = db.Column(db.String(100), nullable=False)
    seller_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending_Payment') 
    # الحالات: Pending_Payment (انتظار الدفع), Funds_Held (المبلغ معلق), Credentials_Submitted (تم تسليم الحساب), Completed (مكتمل), Disputed (متنازع عليه), Refunded (مسترجع), Awaiting_Buyer_Recovery (انتظار استرداد الحساب من المشتري)
    credentials = db.Column(db.String(500), nullable=True) # بيانات الحساب المرسلة من البائع
    created_at = db.Column(db.DateTime, default=db.func.now())
    credentials_submitted_at = db.Column(db.DateTime, nullable=True) # وقت تسليم بيانات الحساب (للتايمر)
    buyer_recovery_data = db.Column(db.Text, nullable=True) # بيانات الحساب الحالية التي يسلمها المشتري للإدارة (استرداد)
    buyer_recovery_submitted_at = db.Column(db.DateTime, nullable=True) # وقت تسليم بيانات الاسترداد من المشتري
    
    account = db.relationship('Account', backref='orders')

class DisputeEvidence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    uploaded_by = db.Column(db.String(100), nullable=False)
    text_content = db.Column(db.Text, nullable=True) # شرح المشكلة بالتفصيل
    image_url = db.Column(db.String(500), nullable=True) # رابط صورة دليل
    created_at = db.Column(db.DateTime, default=db.func.now())
    
    order = db.relationship('Order', backref=db.backref('dispute_evidences', cascade='all, delete-orphan'))

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=True)
    sender = db.Column(db.String(100), nullable=False)
    receiver = db.Column(db.String(100), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    time = db.Column(db.DateTime, default=db.func.now())

class WithdrawalRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending') # Pending, Approved, Rejected
    created_at = db.Column(db.DateTime, default=db.func.now())

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    buyer_name = db.Column(db.String(100), nullable=False)
    seller_name = db.Column(db.String(100), nullable=False)
    rating = db.Column(db.Integer, nullable=False) # 1 to 5
    comment = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    
    order = db.relationship('Order', backref=db.backref('reviews', cascade='all, delete-orphan'))

# ---- موديل البلاغات (Reports) ----
class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=True)
    reporter_name = db.Column(db.String(100), nullable=False)
    seller_name = db.Column(db.String(100), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='Pending') # Pending, Reviewed, Dismissed
    created_at = db.Column(db.DateTime, default=db.func.now())
    
    account = db.relationship('Account', backref='reports')

# ---- موديل الإشعارات (Notifications) ----
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(100), nullable=False)  # المستلم
    message = db.Column(db.String(500), nullable=False)     # نص الإشعار
    link = db.Column(db.String(300), nullable=True)         # رابط (مثلاً /order/5)
    is_read = db.Column(db.Boolean, default=False)          # مقروء أم لا
    created_at = db.Column(db.DateTime, default=db.func.now())

# بناء قاعدة البيانات وإنشاء مستخدم المشرف تلقائياً
with app.app_context():
    db.create_all()
    # التأكد من وجود جدول الإشعارات (للتحديثات)
    inspector = db.inspect(db.engine)
    if 'notification' not in inspector.get_table_names():
        db.create_all()
    # إنشاء مستخدم أدمن افتراضي للتجربة
    admin_user = User.query.filter_by(name='admin').first()
    if not admin_user:
        hashed = bcrypt.generate_password_hash('admin123').decode('utf-8')
        admin = User(name='admin', email='admin@waseet.com', password=hashed, balance=100000.0, is_admin=True, is_banned=False)
        db.session.add(admin)
        db.session.commit()

# ==================== دالة مساعدة لإنشاء الإشعارات ====================
def create_notification(user_name, message, link=None):
    """إنشاء إشعار جديد لمستخدم معين"""
    notification = Notification(
        user_name=user_name,
        message=message,
        link=link,
        is_read=False
    )
    db.session.add(notification)
    return notification

# ==================== دوال Context Processor ====================

@app.context_processor
def inject_user_balance():
    if 'user' in session:
        user = User.query.filter_by(name=session['user']).first()
        if user:
            return {'current_user_obj': user}
    return {'current_user_obj': None}

@app.context_processor
def inject_seller_rating():
    def get_seller_rating(seller_name):
        reviews = Review.query.filter_by(seller_name=seller_name).all()
        if not reviews:
            return None
        avg_rating = sum(r.rating for r in reviews) / len(reviews)
        return {
            'avg': round(avg_rating, 1),
            'count': len(reviews)
        }
    return {'get_seller_rating': get_seller_rating}

@app.context_processor
def inject_unread_reports():
    """حقن عدد البلاغات غير المقروءة للمشرفين"""
    if 'user' in session:
        user = User.query.filter_by(name=session['user']).first()
        if user and user.is_admin:
            unread_count = Report.query.filter_by(status='Pending').count()
            return {'unread_reports_count': unread_count}
    return {'unread_reports_count': 0}

@app.context_processor
def inject_notifications_count():
    """حقن عدد الإشعارات غير المقروءة لكل المستخدمين"""
    if 'user' in session:
        user = User.query.filter_by(name=session['user']).first()
        if user:
            unread_notifications = Notification.query.filter_by(user_name=user.name, is_read=False).count()
            return {'unread_notifications_count': unread_notifications}
    return {'unread_notifications_count': 0}

# ==================== API Upload ====================

@app.route('/api/upload_image', methods=['POST'])
def upload_image():
    if 'user' not in session:
        return {'error': 'Not logged in'}, 401
    
    if 'image' not in request.files:
        return {'error': 'لم يتم إرسال ملف صورة'}, 400
    
    file = request.files['image']
    if file.filename == '':
        return {'error': 'لم يتم اختيار ملف'}, 400
    
    if file and allowed_file(file.filename):
        import uuid
        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}_{int(datetime.utcnow().timestamp())}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        image_url = url_for('static', filename=f'uploads/{unique_filename}')
        return {'success': True, 'image_url': image_url}, 200
    
    return {'error': 'نوع الملف غير مسموح. الأنواع المسموحة: png, jpg, jpeg, gif, webp, svg'}, 400

# ==================== التحقق من التحرير التلقائي ====================

def check_auto_release():
    """
    التحقق من الطلبات التي انتهت صلاحية التايمر لها (يومين من تسليم بيانات الحساب)
    وإذا لم يؤكد المشتري الاستلام، يتم تحرير المبلغ تلقائياً للبائع.
    """
    if 'user' not in session:
        return
    current_user = User.query.filter_by(name=session['user']).first()
    if not current_user:
        return
    
    orders_to_check = Order.query.filter_by(status='Credentials_Submitted').all()
    now = datetime.utcnow()
    auto_released_any = False
    
    for order in orders_to_check:
        if order.credentials_submitted_at:
            elapsed = now - order.credentials_submitted_at
            if elapsed >= timedelta(days=2):
                seller_user = User.query.filter_by(name=order.seller_name).first()
                if seller_user:
                    seller_user.balance += order.price
                order.status = 'Completed'
                order.account.status = 'Sold'
                auto_released_any = True
                
                # إشعار للبائع
                create_notification(
                    order.seller_name,
                    f'🔄 تم تحرير مبلغ {order.price} ريال تلقائياً لك لانتهاء المهلة دون تأكيد من المشتري.',
                    f'/order/{order.id}'
                )
                
                # إشعار للمشتري
                create_notification(
                    order.buyer_name,
                    f'🔄 تم تحرير المبلغ للبائع {order.seller_name} تلقائياً لانتهاء المهلة (يومين) دون تأكيد الاستلام.',
                    f'/order/{order.id}'
                )
                
                # إشعار في الشات
                admin_msg = Message(
                    order_id=order.id,
                    sender='admin',
                    receiver=order.buyer_name,
                    content=f'🔄 تم تحرير المبلغ تلقائياً للبائع {order.seller_name} لانتهاء المهلة (يومين) دون تأكيد الاستلام من المشتري.'
                )
                db.session.add(admin_msg)
    
    if auto_released_any:
        db.session.commit()
        flash('تم تحرير مبلغ طلب تلقائياً لانتهاء المهلة المحددة (يومين دون تأكيد استلام).', 'info')

# ==================== API: الرسائل ====================

@app.route('/api/send_message', methods=['POST'])
def api_send_message():
    if 'user' not in session:
        return {'error': 'Not logged in'}, 401
    
    data = request.get_json()
    if not data:
        return {'error': 'Invalid request'}, 400
    
    order_id = data.get('order_id')
    content = data.get('content', '').strip()
    
    if not content or not order_id:
        return {'error': 'Missing fields'}, 400
    
    order = Order.query.get(order_id)
    if not order:
        return {'error': 'Order not found'}, 404
    
    current_user = User.query.filter_by(name=session['user']).first()
    if not current_user:
        return {'error': 'User not found'}, 404
    
    if current_user.name != order.buyer_name and current_user.name != order.seller_name and not current_user.is_admin:
        return {'error': 'Unauthorized'}, 403
    
    receiver_name = order.seller_name if current_user.name == order.buyer_name else order.buyer_name
    if current_user.is_admin:
        receiver_name = order.buyer_name
    
    msg = Message(
        order_id=order.id,
        sender=current_user.name,
        receiver=receiver_name,
        content=content
    )
    db.session.add(msg)
    
    # إشعار للمستلم برسالة جديدة
    create_notification(
        receiver_name,
        f'💬 لديك رسالة جديدة من {current_user.name} بخصوص الطلب #{order.id}',
        f'/order/{order.id}'
    )
    
    db.session.commit()
    
    return {
        'success': True,
        'message': {
            'id': msg.id,
            'sender': msg.sender,
            'content': msg.content,
            'time': msg.time.strftime('%H:%M'),
            'time_full': msg.time.isoformat()
        }
    }, 200

@app.route('/api/get_order_status/<int:order_id>', methods=['GET'])
def api_get_order_status(order_id):
    if 'user' not in session:
        return {'error': 'Not logged in'}, 401
    
    current_user = User.query.filter_by(name=session['user']).first()
    if not current_user:
        return {'error': 'User not found'}, 404
    
    order = Order.query.get(order_id)
    if not order:
        return {'error': 'Order not found'}, 404
    
    if current_user.name != order.buyer_name and current_user.name != order.seller_name and not current_user.is_admin:
        return {'error': 'Unauthorized'}, 403
    
    return {
        'success': True,
        'status': order.status,
        'order_id': order.id
    }, 200

@app.route('/api/get_messages/<int:order_id>', methods=['GET'])
def api_get_messages(order_id):
    if 'user' not in session:
        return {'error': 'Not logged in'}, 401
    
    current_user = User.query.filter_by(name=session['user']).first()
    if not current_user:
        return {'error': 'User not found'}, 404
    
    order = Order.query.get(order_id)
    if not order:
        return {'error': 'Order not found'}, 404
    
    if current_user.name != order.buyer_name and current_user.name != order.seller_name and not current_user.is_admin:
        return {'error': 'Unauthorized'}, 403
    
    messages = Message.query.filter_by(order_id=order.id).order_by(Message.time.asc()).all()
    
    return {
        'success': True,
        'order_id': order.id,
        'buyer_name': order.buyer_name,
        'seller_name': order.seller_name,
        'messages': [{
            'id': msg.id,
            'sender': msg.sender,
            'content': msg.content,
            'time': msg.time.strftime('%H:%M'),
            'time_full': msg.time.isoformat()
        } for msg in messages]
    }, 200

# ==================== API: API الإشعارات ====================

@app.route('/api/notifications', methods=['GET'])
def api_get_notifications():
    """جلب آخر 20 إشعار للمستخدم الحالي"""
    if 'user' not in session:
        return {'error': 'Not logged in'}, 401
    
    current_user = User.query.filter_by(name=session['user']).first()
    if not current_user:
        return {'error': 'User not found'}, 404
    
    notifications = Notification.query.filter_by(user_name=current_user.name).order_by(Notification.id.desc()).limit(20).all()
    
    return {
        'success': True,
        'notifications': [{
            'id': n.id,
            'message': n.message,
            'link': n.link,
            'is_read': n.is_read,
            'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
        } for n in notifications]
    }, 200

@app.route('/api/notifications/mark_read', methods=['POST'])
def api_mark_notifications_read():
    """تحديد جميع الإشعارات كمقروءة"""
    if 'user' not in session:
        return {'error': 'Not logged in'}, 401
    
    current_user = User.query.filter_by(name=session['user']).first()
    if not current_user:
        return {'error': 'User not found'}, 404
    
    data = request.get_json() or {}
    notification_id = data.get('notification_id')
    
    if notification_id:
        # تحديد إشعار واحد كمقروء
        notification = Notification.query.get(notification_id)
        if notification and notification.user_name == current_user.name:
            notification.is_read = True
            db.session.commit()
            return {'success': True}, 200
        return {'error': 'Notification not found'}, 404
    else:
        # تحديد جميع الإشعارات كمقروءة
        Notification.query.filter_by(user_name=current_user.name, is_read=False).update({'is_read': True})
        db.session.commit()
        return {'success': True}, 200

@app.route('/api/notifications/count', methods=['GET'])
def api_get_notifications_count():
    """جلب عدد الإشعارات غير المقروءة"""
    if 'user' not in session:
        return {'count': 0}, 200
    
    current_user = User.query.filter_by(name=session['user']).first()
    if not current_user:
        return {'count': 0}, 200
    
    count = Notification.query.filter_by(user_name=current_user.name, is_read=False).count()
    return {'count': count}, 200

# ---- API: الإبلاغ عن بائع ----
@app.route('/api/report_seller', methods=['POST'])
def api_report_seller():
    if 'user' not in session:
        return {'error': 'Not logged in'}, 401
    
    data = request.get_json()
    if not data:
        return {'error': 'Invalid request'}, 400
    
    account_id = data.get('account_id')
    reason = data.get('reason', '').strip()
    
    if not account_id or not reason:
        return {'error': 'جميع الحقول مطلوبة'}, 400
    
    if len(reason) < 5:
        return {'error': 'يرجى كتابة سبب البلاغ بتفصيل أكثر (5 أحرف على الأقل)'}, 400
    
    account = Account.query.get(account_id)
    if not account:
        return {'error': 'الحساب غير موجود'}, 404
    
    current_user = User.query.filter_by(name=session['user']).first()
    if not current_user:
        return {'error': 'User not found'}, 404
    
    # منع الإبلاغ عن نفسك
    if account.seller == current_user.name:
        return {'error': 'لا يمكنك الإبلاغ عن حسابك الخاص'}, 400
    
    # التحقق من عدم وجود بلاغ مكرر لنفس المستخدم على نفس الحساب
    existing_report = Report.query.filter_by(
        account_id=account.id,
        reporter_name=current_user.name
    ).filter(Report.status != 'Dismissed').first()
    
    if existing_report:
        return {'error': 'لقد قمت بالإبلاغ عن هذا الحساب مسبقاً، وهو قيد المراجعة'}, 400
    
    report = Report(
        account_id=account.id,
        reporter_name=current_user.name,
        seller_name=account.seller,
        reason=reason
    )
    db.session.add(report)
    
    # إشعار للإدارة بوجود بلاغ جديد
    create_notification(
        'admin',
        f'🚩 تم استلام بلاغ جديد من {current_user.name} ضد البائع {account.seller} في إعلان "{account.game}". السبب: {reason[:100]}{"..." if len(reason) > 100 else ""}',
        f'/admin/disputes'
    )
    
    db.session.commit()
    
    return {
        'success': True,
        'message': 'تم تقديم البلاغ بنجاح. سيتم مراجعة البلاغ من قبل الإدارة في أقرب وقت.'
    }, 200

# ---- API: جلب البلاغات (للوحة الإدارة) ----
@app.route('/api/reports', methods=['GET'])
def api_get_reports():
    if 'user' not in session:
        return {'error': 'Not logged in'}, 401
    
    current_user = User.query.filter_by(name=session['user']).first()
    if not current_user or not current_user.is_admin:
        return {'error': 'Unauthorized'}, 403
    
    reports = Report.query.order_by(Report.id.desc()).all()
    
    return {
        'success': True,
        'reports': [{
            'id': r.id,
            'account_id': r.account_id,
            'account_game': r.account.game if r.account else 'محذوف',
            'reporter_name': r.reporter_name,
            'seller_name': r.seller_name,
            'reason': r.reason,
            'status': r.status,
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M')
        } for r in reports]
    }, 200

# ---- API: إدارة البلاغات (حذف حساب أو رفض البلاغ) ----
@app.route('/api/report_action', methods=['POST'])
def api_report_action():
    if 'user' not in session:
        return {'error': 'Not logged in'}, 401
    
    current_user = User.query.filter_by(name=session['user']).first()
    if not current_user or not current_user.is_admin:
        return {'error': 'Unauthorized'}, 403
    
    data = request.get_json()
    if not data:
        return {'error': 'Invalid request'}, 400
    
    report_id = data.get('report_id')
    action = data.get('action')  # 'delete_account' or 'dismiss'
    
    report = Report.query.get(report_id)
    if not report:
        return {'error': 'البلاغ غير موجود'}, 404
    
    if action == 'delete_account':
        if report.account:
            db.session.delete(report.account)
        report.status = 'Reviewed'
        db.session.commit()
        return {
            'success': True,
            'message': f'تم حذف الإعلان المخالف للبائع {report.seller_name} وحظر الإعلان بنجاح.'
        }, 200
        
    elif action == 'dismiss':
        report.status = 'Dismissed'
        db.session.commit()
        return {
            'success': True,
            'message': 'تم رفض البلاغ وإغلاقه.'
        }, 200
        
    return {'error': 'Invalid action'}, 400

# ---- API: آخر الإعلانات المضافة (للتحديث التلقائي في الصفحة الرئيسية) ----
@app.route('/api/latest_accounts', methods=['GET'])
def api_latest_accounts():
    accounts = Account.query.filter_by(status='Available').order_by(Account.id.desc()).limit(12).all()
    
    return {
        'success': True,
        'accounts': [{
            'id': a.id,
            'game': a.game,
            'description': a.description,
            'price': a.price,
            'seller': a.seller,
            'platform': a.platform,
            'image_url': a.image_url,
            'created_at': a.id
        } for a in accounts]
    }, 200

# ==================== Routes ====================

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form['name'].strip()
        email_or_phone = request.form['email_or_phone'].strip()
        password = request.form['password']
        
        existing_user = User.query.filter((User.email == email_or_phone) | (User.name == name)).first()
        if existing_user:
            return render_template('register.html', error='اسم المستخدم أو البريد/الجوال مسجل بالفعل')
            
        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(name=name, email=email_or_phone, password=hashed, balance=1000.0, is_banned=False)
        db.session.add(user)
        db.session.commit()
        
        session.permanent = True
        session['user'] = user.name
        flash('تم إنشاء حسابك بنجاح! حصلت على 1000 ريال رصيداً تجريبياً ترحيبياً 🎁', 'success')
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        identifier = request.form['email_or_phone'].strip()
        password = request.form['password']
        
        user = User.query.filter((User.email == identifier) | (User.name == identifier)).first()
        if user and bcrypt.check_password_hash(user.password, password):
            if user.is_banned:
                return render_template('login.html', error='عذراً، هذا الحساب تم حظره من قبل الإدارة لمخالفته شروط الاستخدام 🚫')
            session.permanent = True
            session['user'] = user.name
            flash(f'مرحباً بعودتك، {user.name}!', 'success')
            if user.is_admin:
                return redirect(url_for('admin_disputes'))
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='اسم المستخدم/البريد/الجوال أو كلمة المرور غير صحيحة')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('تم تسجيل الخروج بنجاح.', 'info')
    return redirect(url_for('home'))

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('accounts'))
    
    # تطبيع نص البحث
    normalized_query = normalize_arabic_text(query)
    
    # البحث المرن: جلب جميع الحسابات المتاحة ومقارنتها
    all_available = Account.query.filter_by(status='Available').all()
    search_results = []
    
    for account in all_available:
        # تطبيع جميع الحقول للبحث
        norm_game = normalize_arabic_text(account.game)
        norm_desc = normalize_arabic_text(account.description or '')
        norm_seller = normalize_arabic_text(account.seller)
        norm_platform = normalize_arabic_text(account.platform)
        
        # البحث عن النص المُطبع في أي حقل
        if (normalized_query in norm_game or 
            normalized_query in norm_desc or 
            normalized_query in norm_seller or 
            normalized_query in norm_platform):
            search_results.append(account)
    
    all_games = db.session.query(Account.game).distinct().all()
    all_platforms = db.session.query(Account.platform).distinct().all()
    
    return render_template(
        'accounts.html', 
        accounts=search_results, 
        games=[g[0] for g in all_games], 
        platforms=[p[0] for p in all_platforms],
        selected_game=None,
        selected_platform=None,
        search_query=query
    )

@app.route('/accounts')
def accounts():
    game_filter = request.args.get('game')
    platform_filter = request.args.get('platform')
    
    query = Account.query.filter_by(status='Available')
    
    all_games = db.session.query(Account.game).distinct().all()
    all_platforms = db.session.query(Account.platform).distinct().all()
    
    if game_filter:
        # استخدام البحث المرن للعبة المحددة أيضاً
        normalized_game = normalize_arabic_text(game_filter)
        all_accounts_for_filter = query.order_by(Account.id.desc()).all()
        filtered = []
        for account in all_accounts_for_filter:
            if normalized_game in normalize_arabic_text(account.game):
                filtered.append(account)
        all_accounts = filtered
    else:
        if platform_filter:
            query = query.filter_by(platform=platform_filter)
        all_accounts = query.order_by(Account.id.desc()).all()
    
    return render_template(
        'accounts.html', 
        accounts=all_accounts, 
        games=[g[0] for g in all_games], 
        platforms=[p[0] for p in all_platforms],
        selected_game=game_filter,
        selected_platform=platform_filter
    )

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if 'user' not in session:
        flash('يجب عليك تسجيل الدخول أولاً لنشر حساب.', 'warning')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        game = request.form['game']
        description = request.form['description']
        price = float(request.form['price'])
        platform = request.form.get('platform', 'PC')
        
        image_url = None
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename and allowed_file(file.filename):
                import uuid
                ext = file.filename.rsplit('.', 1)[1].lower()
                unique_filename = f"account_{uuid.uuid4().hex}_{int(datetime.utcnow().timestamp())}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)
                image_url = url_for('static', filename=f'uploads/{unique_filename}')
            
        account = Account(
            game=game,
            description=description,
            price=price,
            seller=session['user'],
            platform=platform,
            image_url=image_url,
            status='Available'
        )
        db.session.add(account)
        db.session.commit()
        
        # إشعار للإدارة بأنه تم إضافة إعلان جديد
        create_notification(
            'admin',
            f'📢 تم نشر حساب جديد للبيع: "{account.game}" بقيمة {account.price} ريال بواسطة {session["user"]}.',
            f'/admin/disputes'
        )
        
        flash('تم نشر حسابك للبيع بنجاح ومتاح الآن في المتجر!', 'success')
        return redirect(url_for('accounts'))
    return render_template('sell.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    current_user = User.query.filter_by(name=session['user']).first()
    if not current_user:
        session.pop('user', None)
        return redirect(url_for('login'))
    
    # التحقق من التايمر التلقائي (يومين)
    check_auto_release()
        
    buy_orders = Order.query.filter_by(buyer_name=current_user.name).order_by(Order.id.desc()).all()
    sell_orders = Order.query.filter_by(seller_name=current_user.name).order_by(Order.id.desc()).all()
    
    pending_balance = 0.0
    for o in sell_orders:
        if o.status in ['Funds_Held', 'Credentials_Submitted', 'Disputed']:
            pending_balance += o.price
            
    withdrawals = WithdrawalRequest.query.filter_by(username=current_user.name).order_by(WithdrawalRequest.id.desc()).all()
            
    return render_template(
        'dashboard.html', 
        user=current_user, 
        buy_orders=buy_orders, 
        sell_orders=sell_orders, 
        pending_balance=pending_balance,
        withdrawals=withdrawals
    )

@app.route('/wallet/deposit', methods=['POST'])
def wallet_deposit():
    if 'user' not in session:
        return redirect(url_for('login'))
    current_user = User.query.filter_by(name=session['user']).first()
    amount = float(request.form.get('amount', 500))
    if amount > 0:
        current_user.balance += amount
        db.session.commit()
        flash(f'تم شحن رصيدك التجريبي بقيمة {amount} ريال بنجاح! 💰', 'success')
    return redirect(url_for('dashboard'))

@app.route('/wallet/withdraw', methods=['POST'])
def wallet_withdraw():
    if 'user' not in session:
        return redirect(url_for('login'))
    current_user = User.query.filter_by(name=session['user']).first()
    amount = float(request.form.get('amount', 100))
    
    if amount <= 0:
        flash('يرجى تحديد قيمة سحب صحيحة.', 'danger')
        return redirect(url_for('dashboard'))
        
    if current_user.balance >= amount:
        current_user.balance -= amount
        req = WithdrawalRequest(username=current_user.name, amount=amount, status='Pending')
        db.session.add(req)
        db.session.commit()
        flash(f'تم تقديم طلب سحب بقيمة {amount} ريال بنجاح! هو الآن بانتظار موافقة المشرف ⏳', 'success')
    else:
        flash('عذراً، رصيدك غير كافٍ لإجراء السحب.', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/order/create/<int:account_id>', methods=['POST'])
def create_order(account_id):
    if 'user' not in session:
        flash('يرجى تسجيل الدخول أولاً لشراء الحساب.', 'warning')
        return redirect(url_for('login'))
        
    current_user = User.query.filter_by(name=session['user']).first()
    account = Account.query.get_or_404(account_id)
    
    if account.seller == current_user.name:
        flash('لا يمكنك شراء حسابك المعروض للبيع!', 'danger')
        return redirect(url_for('accounts'))
        
    if account.status != 'Available':
        flash('عذراً، هذا الحساب تم شراؤه أو محجوز حالياً.', 'warning')
        return redirect(url_for('accounts'))
        
    existing_order = Order.query.filter_by(account_id=account.id, buyer_name=current_user.name).filter(Order.status != 'Refunded').first()
    if existing_order:
        return redirect(url_for('order_details', order_id=existing_order.id))
        
    order = Order(
        account_id=account.id,
        buyer_name=current_user.name,
        seller_name=account.seller,
        price=account.price,
        status='Pending_Payment'
    )
    db.session.add(order)
    
    # إشعار للبائع بأن شخصاً ما يريد شراء منتجه
    create_notification(
        account.seller,
        f'🛒 المشتري {current_user.name} يريد شراء حسابك "{account.game}" بقيمة {account.price} ريال. بانتظار الدفع.',
        f'/order/{order.id}'
    )
    
    db.session.commit()
    
    return redirect(url_for('order_details', order_id=order.id))

@app.route('/order/<int:order_id>', methods=['GET', 'POST'])
def order_details(order_id):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    current_user = User.query.filter_by(name=session['user']).first()
    order = Order.query.get_or_404(order_id)
    
    if current_user.name != order.buyer_name and current_user.name != order.seller_name and not current_user.is_admin:
        flash('ليس لديك صلاحية للوصول إلى هذا الطلب.', 'danger')
        return redirect(url_for('dashboard'))
    
    # التحقق من التايمر التلقائي (يومين)
    check_auto_release()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        # 1. دفع القيمة للوسيط
        if action == 'pay' and current_user.name == order.buyer_name and order.status == 'Pending_Payment':
            if current_user.balance >= order.price:
                current_user.balance -= order.price
                order.status = 'Funds_Held'
                order.account.status = 'Pending'
                
                # إشعار للبائع بأن الدفع تم
                create_notification(
                    order.seller_name,
                    f'💰 تم دفع مبلغ {order.price} ريال لحسابك "{order.account.game}" وهو الآن في أمان الوسيط. يرجى تسليم بيانات الحساب.',
                    f'/order/{order.id}'
                )
                
                db.session.commit()
                flash('تم دفع المبلغ بنجاح! تم حجز الأموال في أمان الوسيط وسيتم إشعار البائع لتسليم الحساب.', 'success')
            else:
                flash('عذراً، رصيدك غير كافٍ. يرجى شحن رصيدك التجريبي أولاً.', 'danger')
                
        # 2. إدخال بيانات الحساب من البائع
        elif action == 'submit_credentials' and current_user.name == order.seller_name and order.status == 'Funds_Held':
            creds = request.form.get('credentials', '').strip()
            if creds:
                order.credentials = creds
                order.status = 'Credentials_Submitted'
                order.credentials_submitted_at = datetime.utcnow()
                
                # إشعار للمشتري بأن البائع سلم البيانات
                create_notification(
                    order.buyer_name,
                    f'🔑 قام البائع {order.seller_name} بتسليم بيانات الحساب "{order.account.game}". يرجى فحص الحساب وتأكيد الاستلام.',
                    f'/order/{order.id}'
                )
                
                db.session.commit()
                flash('تم تسليم معلومات الحساب للوسيط والمشتري بنجاح. سيبدأ عداد اليومين الآن! ⏱️', 'success')
            else:
                flash('يرجى إدخال معلومات صحيحة وغير فارغة.', 'warning')
                
        # 3. تأكيد الاستلام من المشتري
        elif action == 'confirm_receipt' and current_user.name == order.buyer_name and order.status == 'Credentials_Submitted':
            seller_user = User.query.filter_by(name=order.seller_name).first()
            if seller_user:
                seller_user.balance += order.price
            order.status = 'Completed'
            order.account.status = 'Sold'
            
            # إشعار للبائع بأن المشتري أكد الاستلام وتم تحرير المبلغ
            create_notification(
                order.seller_name,
                f'✅ قام المشتري {order.buyer_name} بتأكيد استلام الحساب "{order.account.game}". تم إيداع {order.price} ريال في محفظتك.',
                f'/order/{order.id}'
            )
            
            db.session.commit()
            flash('شكراً لك! تم تأكيد الاستلام بنجاح، وتحويل المبلغ فوراً إلى البائع.', 'success')
            
        # 4. فتح نزاع مع إرفاق أدلة
        elif action == 'raise_dispute' and order.status in ['Funds_Held', 'Credentials_Submitted']:
            order.status = 'Disputed'
            
            text_evidence = request.form.get('dispute_text', '').strip()
            image_evidence = None
            
            if 'dispute_image' in request.files:
                file = request.files['dispute_image']
                if file and file.filename and allowed_file(file.filename):
                    import uuid
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    unique_filename = f"dispute_{order.id}_{uuid.uuid4().hex}_{int(datetime.utcnow().timestamp())}.{ext}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(filepath)
                    image_evidence = url_for('static', filename=f'uploads/{unique_filename}')
                elif file and file.filename:
                    pass
            
            if not image_evidence:
                image_evidence = request.form.get('dispute_image', '').strip() or None
            
            if text_evidence or image_evidence:
                evidence = DisputeEvidence(
                    order_id=order.id,
                    uploaded_by=current_user.name,
                    text_content=text_evidence if text_evidence else None,
                    image_url=image_evidence if image_evidence else None
                )
                db.session.add(evidence)
            
            # إشعار للطرف الآخر بفتح النزاع
            other_party = order.seller_name if current_user.name == order.buyer_name else order.buyer_name
            create_notification(
                other_party,
                f'⚖️ تم فتح نزاع على الطلب #{order.id} من قبل {current_user.name}. يرجى متابعة القضية مع الإدارة.',
                f'/order/{order.id}'
            )
            
            # إشعار للإدارة بوجود نزاع جديد
            create_notification(
                'admin',
                f'⚖️ تم فتح نزاع جديد على الطلب #{order.id} من قبل {current_user.name} ضد {other_party}. يرجى التدخل والمراجعة.',
                f'/admin/disputes'
            )
            
            db.session.commit()
            flash('تم فتح نزاع حول الطلب مع إرفاق الأدلة. تم إرسال تنبيه للمشرف للتدخل والمراجعة.', 'warning')
            
        # 5. إرسال رسالة في الشات
        elif action == 'send_message':
            content = request.form.get('content', '').strip()
            if content:
                receiver_name = order.seller_name if current_user.name == order.buyer_name else order.buyer_name
                if current_user.is_admin:
                    receiver_name = order.buyer_name
                
                msg = Message(
                    order_id=order.id,
                    sender=current_user.name,
                    receiver=receiver_name,
                    content=content
                )
                db.session.add(msg)
                
                # إشعار للمستلم برسالة جديدة
                create_notification(
                    receiver_name,
                    f'💬 لديك رسالة جديدة من {current_user.name} بخصوص الطلب #{order.id}',
                    f'/order/{order.id}'
                )
                
                db.session.commit()
                
        # 6. إرسال تقييم للبائع بعد انتهاء المعاملة
        elif action == 'submit_review' and current_user.name == order.buyer_name and order.status == 'Completed':
            rating = int(request.form.get('rating', 5))
            comment = request.form.get('comment', '').strip()
            
            existing_review = Review.query.filter_by(order_id=order.id).first()
            if not existing_review:
                rev = Review(
                    order_id=order.id,
                    buyer_name=order.buyer_name,
                    seller_name=order.seller_name,
                    rating=rating,
                    comment=comment
                )
                db.session.add(rev)
                db.session.commit()
                flash('تم إرسال تقييمك للبائع بنجاح! شكراً لك.', 'success')
            else:
                flash('لقد قمت بتقييم هذه المعاملة مسبقاً.', 'warning')
                
        # 8. تسليم بيانات استرداد الحساب من المشتري للإدارة
        elif action == 'submit_recovery_data' and current_user.name == order.buyer_name and order.status == 'Awaiting_Buyer_Recovery':
            recovery_data = request.form.get('recovery_data', '').strip()
            if recovery_data:
                order.buyer_recovery_data = recovery_data
                order.buyer_recovery_submitted_at = datetime.utcnow()
                
                # إشعار للإدارة بأن المشتري سلم بيانات الاسترداد
                create_notification(
                    'admin',
                    f'📋 قام المشتري {order.buyer_name} بتسليم بيانات استرداد الحساب للطلب #{order.id}. يرجى مراجعة البيانات وإغلاق النزاع.',
                    f'/admin/disputes'
                )
                
                db.session.commit()
                flash('تم تسليم بيانات الحساب للإدارة بنجاح. بانتظار مراجعة المشرف وإغلاق النزاع واسترجاع أموالك.', 'success')
            else:
                flash('يرجى إدخال بيانات الحساب الحالية بشكل صحيح.', 'warning')
                
        # 9. إضافة دليل جديد للنزاع المفتوح
        elif action == 'add_dispute_evidence' and order.status == 'Disputed':
            text_evidence = request.form.get('dispute_text', '').strip()
            image_evidence = None
            
            if 'dispute_image' in request.files:
                file = request.files['dispute_image']
                if file and file.filename and allowed_file(file.filename):
                    import uuid
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    unique_filename = f"evidence_{order.id}_{uuid.uuid4().hex}_{int(datetime.utcnow().timestamp())}.{ext}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(filepath)
                    image_evidence = url_for('static', filename=f'uploads/{unique_filename}')
                elif file and file.filename:
                    pass
            
            if not image_evidence:
                image_evidence = request.form.get('dispute_image', '').strip() or None
            
            if text_evidence or image_evidence:
                evidence = DisputeEvidence(
                    order_id=order.id,
                    uploaded_by=current_user.name,
                    text_content=text_evidence if text_evidence else None,
                    image_url=image_evidence if image_evidence else None
                )
                db.session.add(evidence)
                
                # إشعار للإدارة بأنه تم إضافة أدلة جديدة للنزاع
                create_notification(
                    'admin',
                    f'📎 قام {current_user.name} بإضافة دليل جديد إلى النزاع على الطلب #{order.id}. يرجى مراجعة الأدلة.',
                    f'/admin/disputes'
                )
                
                db.session.commit()
                flash('تم إضافة الدليل الجديد للنزاع بنجاح.', 'success')
            else:
                flash('يرجى إدخال نص أو صورة كدليل.', 'warning')
        
        return redirect(url_for('order_details', order_id=order.id))
        
    messages = Message.query.filter_by(order_id=order.id).order_by(Message.time.asc()).all()
    order_review = Review.query.filter_by(order_id=order.id).first()
    dispute_evidences = DisputeEvidence.query.filter_by(order_id=order.id).order_by(DisputeEvidence.id.desc()).all()
    
    remaining_seconds = 0
    if order.status == 'Credentials_Submitted' and order.credentials_submitted_at:
        elapsed = datetime.utcnow() - order.credentials_submitted_at
        total_seconds = 2 * 86400
        remaining = total_seconds - int(elapsed.total_seconds())
        remaining_seconds = max(0, remaining)
    
    return render_template(
        'order_details.html', 
        order=order, 
        messages=messages, 
        user=current_user, 
        order_review=order_review,
        dispute_evidences=dispute_evidences,
        remaining_seconds=remaining_seconds
    )

# ==================== لوحة الإدارة (Admin Panel) ====================

@app.route('/admin/disputes', methods=['GET', 'POST'])
def admin_disputes():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    current_user = User.query.filter_by(name=session['user']).first()
    if not current_user or not current_user.is_admin:
        flash('هذه الصفحة خاصة بالإدارة فقط.', 'danger')
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        
        # 1. حل النزاعات بشكل عادل:
        #    - release: تحرير الأموال للبائع (لصالح البائع) -> Completed
        #    - refund: إعادة الأموال للمشتري (لصالح المشتري) -> Refunded (مباشرة)
        if action in ['release', 'refund']:
            order_id = request.form.get('order_id')
            order = Order.query.get_or_404(order_id)
            
            if order.status == 'Disputed':
                if action == 'release':
                    # لصالح البائع: تحويل الأموال المحجوزة مباشرة للبائع
                    seller = User.query.filter_by(name=order.seller_name).first()
                    if seller:
                        seller.balance += order.price
                    order.status = 'Completed'
                    order.account.status = 'Sold'
                    
                    # إشعار للبائع
                    create_notification(
                        order.seller_name,
                        f'⚖️ تم حل النزاع لصالحك! تم إيداع {order.price} ريال في محفظتك للطلب #{order.id}.',
                        f'/order/{order.id}'
                    )
                    
                    # إشعار للمشتري
                    create_notification(
                        order.buyer_name,
                        f'⚖️ تم حل النزاع لصالح البائع للطلب #{order.id}. تم تحرير المبلغ للبائع.',
                        f'/order/{order.id}'
                    )
                    
                    db.session.commit()
                    flash(f'تم حل النزاع للطلب #{order.id}: تم تحرير الأموال لصالح البائع وإغلاق الطلب كمكتمل.', 'success')
                    
                elif action == 'refund':
                    # لصالح المشتري: إعادة الأموال مباشرة للمشتري (بدون تعقيد استرداد الحساب)
                    buyer = User.query.filter_by(name=order.buyer_name).first()
                    if buyer:
                        buyer.balance += order.price
                    order.status = 'Refunded'
                    order.account.status = 'Available'
                    
                    # إشعار للمشتري
                    create_notification(
                        order.buyer_name,
                        f'⚖️ تم حل النزاع لصالحك! تم إعادة {order.price} ريال إلى محفظتك للطلب #{order.id}.',
                        f'/order/{order.id}'
                    )
                    
                    # إشعار للبائع
                    create_notification(
                        order.seller_name,
                        f'⚖️ تم حل النزاع لصالح المشتري للطلب #{order.id}. تم إعادة المبلغ للمشتري وإلغاء الطلب.',
                        f'/order/{order.id}'
                    )
                    
                    db.session.commit()
                    flash(f'تم حل النزاع للطلب #{order.id}: تم إعادة المبلغ للمشتري وإلغاء الطلب.', 'success')
                    
        # 7. تأكيد استلام الحساب من المشتري وإغلاق النزاع نهائياً (للتوافق مع الطلبات القديمة)
        elif action == 'confirm_recovery':
            order_id = request.form.get('order_id')
            order = Order.query.get_or_404(order_id)
            
            if order.status == 'Awaiting_Buyer_Recovery' and order.buyer_recovery_data:
                # إعادة المبلغ إلى محفظة المشتري
                buyer = User.query.filter_by(name=order.buyer_name).first()
                if buyer:
                    buyer.balance += order.price
                
                # إرسال بيانات الحساب المستردة إلى البائع
                seller = User.query.filter_by(name=order.seller_name).first()
                
                recovery_note = f'📋 بيانات الحساب المستردة من المشتري (بعد إغلاق النزاع):\n{order.buyer_recovery_data}'
                
                admin_msg_seller = Message(
                    order_id=order.id,
                    sender='admin',
                    receiver=order.seller_name,
                    content=recovery_note
                )
                db.session.add(admin_msg_seller)
                
                admin_msg_buyer = Message(
                    order_id=order.id,
                    sender='admin',
                    receiver=order.buyer_name,
                    content=f'✅ تم تأكيد استلام بيانات الحساب واسترجاع مبلغ {order.price} ريال إلى محفظتك. تم إغلاق النزاع نهائياً.'
                )
                db.session.add(admin_msg_buyer)
                
                order.status = 'Refunded'
                order.account.status = 'Available'
                
                create_notification(
                    order.buyer_name,
                    f'✅ تم إغلاق النزاع واسترجاع {order.price} ريال إلى محفظتك للطلب #{order.id}.',
                    f'/order/{order.id}'
                )
                
                create_notification(
                    order.seller_name,
                    f'📋 تم إغلاق النزاع للطلب #{order.id}. تم إرسال بيانات الحساب المستردة إليك عبر الشات.',
                    f'/order/{order.id}'
                )
                
                db.session.commit()
                flash(f'تم إغلاق النزاع للطلب #{order.id}: تم استرداد الحساب من المشتري، وإعادة المبلغ للمشتري، وإرسال بيانات الحساب للبائع.', 'success')
            elif order.status == 'Awaiting_Buyer_Recovery' and not order.buyer_recovery_data:
                flash(f'لم يقم المشتري بإدخال بيانات الحساب بعد. يرجى الانتظار.', 'warning')
                    
        # 2. الموافقة على طلبات السحب
        elif action == 'approve_withdrawal':
            req_id = request.form.get('request_id')
            req = WithdrawalRequest.query.get(req_id)
            if req and req.status == 'Pending':
                req.status = 'Approved'
                
                create_notification(
                    req.username,
                    f'✅ تمت الموافقة على طلب السحب بقيمة {req.amount} ريال. سيتم تحويل المبلغ قريباً.',
                    f'/dashboard'
                )
                
                db.session.commit()
                flash(f'تمت الموافقة على طلب السحب بقيمة {req.amount} ريال للمستخدم {req.username} بنجاح.', 'success')
                
        # 3. رفض طلبات السحب وإعادة المبلغ للمحفظة
        elif action == 'reject_withdrawal':
            req_id = request.form.get('request_id')
            req = WithdrawalRequest.query.get(req_id)
            if req and req.status == 'Pending':
                req.status = 'Rejected'
                beneficiary = User.query.filter_by(name=req.username).first()
                if beneficiary:
                    beneficiary.balance += req.amount
                
                create_notification(
                    req.username,
                    f'❌ تم رفض طلب السحب بقيمة {req.amount} ريال وتم إعادة المبلغ إلى محفظتك.',
                    f'/dashboard'
                )
                
                db.session.commit()
                flash(f'تم رفض طلب السحب للمستخدم {req.username} وإعادة قيمة {req.amount} ريال لمحفظته.', 'info')
                
        # 4. حظر أو إلغاء حظر المستخدمين
        elif action == 'toggle_ban':
            user_id = request.form.get('user_id')
            target_user = User.query.get(user_id)
            if target_user:
                if target_user.name == current_user.name:
                    flash('لا يمكنك حظر حسابك الشخصي!', 'danger')
                else:
                    target_user.is_banned = not target_user.is_banned
                    
                    if target_user.is_banned:
                        create_notification(
                            target_user.name,
                            '🚫 تم حظر حسابك من قبل الإدارة لمخالفته شروط الاستخدام.',
                            None
                        )
                    
                    db.session.commit()
                    ban_status = 'حظر' if target_user.is_banned else 'إلغاء حظر'
                    flash(f'تم {ban_status} المستخدم {target_user.name} بنجاح.', 'success')
                    
        # 5. ترقية لمشرف أو سحب الرتبة
        elif action == 'toggle_admin':
            user_id = request.form.get('user_id')
            target_user = User.query.get(user_id)
            if target_user:
                if target_user.name == current_user.name:
                    flash('لا يمكنك سحب صلاحيات الإشراف عن نفسك!', 'danger')
                else:
                    target_user.is_admin = not target_user.is_admin
                    db.session.commit()
                    admin_status = 'مشرف' if target_user.is_admin else 'عضو عادي'
                    flash(f'تم تغيير رتبة المستخدم {target_user.name} إلى {admin_status}.', 'success')
                    
        # 6. تعديل رصيد مستخدم يدوياً
        elif action == 'edit_balance':
            user_id = request.form.get('user_id')
            new_bal = float(request.form.get('balance', 0))
            target_user = User.query.get(user_id)
            if target_user and new_bal >= 0:
                old_bal = target_user.balance
                target_user.balance = new_bal
                db.session.commit()
                flash(f'تم تعديل رصيد المستخدم {target_user.name} بنجاح من {old_bal} إلى {new_bal} ريال.', 'success')
                
        return redirect(url_for('admin_disputes'))
        
    disputed_orders = Order.query.filter_by(status='Disputed').all()
    recovery_orders = Order.query.filter_by(status='Awaiting_Buyer_Recovery').all()
    all_orders = Order.query.order_by(Order.id.desc()).all()
    all_users = User.query.order_by(User.id.desc()).all()
    all_withdrawals = WithdrawalRequest.query.order_by(WithdrawalRequest.id.desc()).all()
    all_reports = Report.query.order_by(Report.id.desc()).all()
    
    funds_held_total = sum(o.price for o in all_orders if o.status in ['Funds_Held', 'Credentials_Submitted', 'Disputed'])
    users_balances_total = sum(u.balance for u in all_users)
    
    return render_template(
        'admin.html', 
        disputed_orders=disputed_orders,
        recovery_orders=recovery_orders,
        all_orders=all_orders, 
        all_users=all_users,
        all_withdrawals=all_withdrawals,
        all_reports=all_reports,
        funds_held_total=funds_held_total,
        users_balances_total=users_balances_total,
        user=current_user
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)