import os
import re
import difflib
import random
import string
import smtplib
import uuid
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

app = Flask(__name__)
# Force PostgreSQL connection with new password (Railway internal)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://postgres:fIFMPjCQhDitmOtSoglMisrNxhLdYCib@postgres.railway.internal:5432/railway')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # تحسين الأداء
app.secret_key = 'waseet123_secure_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # حد أقصى 16 ميجابايت للصورة
app.config['COMMISSION_RATE'] = 5.0  # نسبة عمولة المنصة 5%
# إعدادات SMTP للبريد الإلكتروني - تقرأ من متغيرات البيئة فقط (تُضبط في Railway)
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
mail_port_raw = os.environ.get('MAIL_PORT', '587')
app.config['MAIL_PORT'] = int(mail_port_raw) if mail_port_raw and mail_port_raw.strip() else 587
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_FROM'] = os.environ.get('MAIL_FROM', '')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
ITEMS_PER_PAGE = 20  # عدد العناصر في كل صفحة لتحسين السرعة

# تحميل إعدادات SMTP من متغيرات البيئة
def get_smtp_config():
    """إرجاع إعدادات SMTP الحالية من app.config"""
    return {
        'mail_server': app.config.get('MAIL_SERVER', ''),
        'mail_port': app.config.get('MAIL_PORT', 587),
        'mail_username': app.config.get('MAIL_USERNAME', ''),
        'mail_password': app.config.get('MAIL_PASSWORD', ''),
        'mail_from': app.config.get('MAIL_FROM', '')
    }

# Re-trigger: Force Railway to rebuild and rebind DATABASE_URL environment variable
# قائمة نطاقات الإيميلات المؤقتة والوهمية المعروفة
TEMP_EMAIL_DOMAINS = {
    'temp-mail.org', 'temp-mail.cc', 'temp-mail.io', 'guerrillamail.com',
    'guerrillamail.net', 'guerrillamail.org', 'mailinator.com', 'mailinator.net',
    '10minutemail.com', '10minutemail.net', 'yopmail.com', 'yopmail.fr',
    'throwaway.email', 'throwawaymail.com', 'trashmail.com', 'trashmail.net',
    'sharklasers.com', 'spam4.me', 'mailmetrash.com', 'mailnator.com',
    'harakirimail.com', 'filzmail.com', 'getnada.com', 'getairmail.com',
    'airmailbox.com', 'dispostable.com', 'maildrop.cc', 'mailexpire.com',
    'tempail.com', 'tempmail.net', 'emailondeck.com', 'mohmal.com',
    'mohmal.net', 'mohmal.org', 'tempr.email', 'tempemail.net',
    'spambox.us', 'spambox.info', 'mytrashmail.com', 'trash2009.com',
    'maileater.com', 'email-fake.com', 'fakeinbox.com', 'fakeinbox.info',
    'fakemail.net', 'fakemailgenerator.com', 'generator.email',
    'mintemail.com', 'wegwerfmail.de', 'wegwerfmail.net', 'deadaddress.com',
    'emailias.com', 'eyepaste.com', 'haltospam.com', 'kulturbetrieb.info',
    'letterboxes.org', 'mail-metro.com', 'mailexpress.top', 'mailin8r.com',
    'mailita.tk', 'mailline.tk', 'mailtothis.com', 'myinbox.in',
    'netzidiot.de', 'onewaymail.com', 'rcpt.at', 'receiveee.com',
    'sneakemail.com', 'sofort-mail.de', 'spambob.com', 'spambob.net',
    'spambob.org', 'spamcero.com', 'spamcon.org', 'spamday.com',
    'spamex.com', 'spamfree24.org', 'spamfree.eu', 'spamgoes.com',
    'spamherelots.com', 'spamhole.com', 'spamify.com', 'spaminator.de',
    'spamkill.info', 'spaml.com', 'spamoff.de', 'spamsalad.com',
    'spamserver.info', 'spamstack.net', 'spamthis.co.uk', 'spamthis.net',
    'spamtrail.com', 'spamwc.de', 'speed.1s.fr', 'temp-mail.info',
    'tempmail.eu', 'thespammer.net', 'thraml.com', 'trash2009.com',
    'trashymail.com', 'uggsrock.com', 'veryrealemail.com', 'voidmail.net',
    'weg-werf-mail.de', 'wh4f.org', 'whyspam.me', 'willhackforfood.biz',
    'winemaven.info', 'wronghead.com', 'xagloo.com', 'xemaps.com',
    'xents.com', 'xmaily.com', 'xoxy.net', 'yep.it', 'yogamaven.com',
    'yopmail.fr', 'yopmail.net', 'ypmail.webarnak.com.eu.org',
    'zippymail.info', 'zoaxe.com', 'zoemail.net', 'zumpat.com',
    'mail1a.com', 'emailnator.com', 'hmamail.com', 'klzlk.com',
    '24hourmail.com', 'bcaoo.com', 'demail.uk', 'developermail.com',
    'forgetmail.com', 'inboxbear.com', 'moakt.co', 'moakt.ws',
    'nospam.online', 'oncemail.net', 'simplelogin.co', 'tempr.email',
    'zerobounce.net', 'burnermail.io'
}

# التأكد من وجود مجلد رفع الصور
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
bcrypt = Bcrypt(app)
db = SQLAlchemy(app)
with app.app_context():
    db.create_all()

# ==================== دالة تطبيع النص العربي للبحث الذكي ====================
def normalize_arabic_text(text):
    if not text:
        return ''
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'[ىيئ]', 'ي', text)
    text = re.sub(r'[ةۀ]', 'ه', text)
    text = re.sub(r'[ًٌٍَُِْ]', '', text)
    text = re.sub(r'[ـ\x60]', '', text)
    text = re.sub(r'[^\w\s\u0600-\u06FF]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def fuzzy_search_score(query, text):
    if not query or not text:
        return 0.0
    query_norm = normalize_arabic_text(query)
    text_norm = normalize_arabic_text(text)
    if not query_norm or not text_norm:
        return 0.0
    if query_norm == text_norm:
        return 1.0
    if query_norm in text_norm:
        return 0.95
    query_words = query_norm.split()
    text_words = set(text_norm.split())
    if query_words and all(qw in text_words for qw in query_words):
        return 0.90
    if query_words:
        matched_words = sum(1 for qw in query_words if qw in text_words)
        word_ratio = matched_words / len(query_words)
        if word_ratio >= 0.6:
            return 0.75 + (word_ratio * 0.10)
    similarity = difflib.SequenceMatcher(None, query_norm, text_norm).ratio()
    best_partial = 0.0
    for qw in query_words:
        for tw in text_words:
            word_sim = difflib.SequenceMatcher(None, qw, tw).ratio()
            if tw.startswith(qw) or qw.startswith(tw):
                word_sim = max(word_sim, 0.80)
            min_len = min(len(qw), len(tw))
            if min_len >= 2:
                prefix_sim = difflib.SequenceMatcher(None, qw[:min_len], tw[:min_len]).ratio()
                word_sim = max(word_sim, prefix_sim)
            best_partial = max(best_partial, word_sim)
    final_score = max(similarity * 0.6, best_partial * 0.8)
    return min(final_score, 0.89)

# ==================== دوال منع الإيميلات المؤقتة والتحقق ====================

def is_temp_email(email):
    if not email or '@' not in email:
        return False
    domain = email.lower().split('@')[1].strip()
    if domain in TEMP_EMAIL_DOMAINS:
        return True
    parts = domain.split('.')
    if len(parts) >= 2:
        base_domain = '.'.join(parts[-2:])
        if base_domain in TEMP_EMAIL_DOMAINS:
            return True
        if len(parts) >= 3:
            base_domain = '.'.join(parts[-3:])
            if base_domain in TEMP_EMAIL_DOMAINS:
                return True
    return False

def generate_otp():
    return ''.join(random.choices(string.digits, k=4))

def send_otp_email(to_email, otp_code, username):
    subject = '🔐 كود التحقق - منصة وسيط'
    body = f"""
    <div dir="rtl" style="font-family: 'Segoe UI', Tahoma, sans-serif; max-width: 500px; margin: 0 auto; padding: 30px; background: linear-gradient(135deg, #0a0b12, #1a1b2e); border-radius: 20px; border: 1px solid rgba(126, 63, 242, 0.3);">
        <div style="text-align: center; margin-bottom: 25px;">
            <span style="font-size: 32px;">🛡️</span>
            <h1 style="color: #0ff; font-size: 24px; margin: 10px 0;">منصة وسيط</h1>
        </div>
        <div style="background: rgba(7, 8, 10, 0.6); border-radius: 16px; padding: 25px; border: 1px solid rgba(255,255,255,0.05);">
            <p style="color: #e0e0e0; font-size: 16px; line-height: 1.7;">مرحباً <strong style="color: #0ff;">{username}</strong>،</p>
            <p style="color: #a2a8b9; font-size: 14px; line-height: 1.7;">نشكرك على إنشاء حساب في منصة وسيط. يرجى استخدام الكود التالي لتأكيد بريدك الإلكتروني:</p>
            <div style="text-align: center; margin: 25px 0;">
                <span style="display: inline-block; background: linear-gradient(135deg, #00ff9d, #00f0ff); color: #0a0b12; font-size: 36px; font-weight: 900; letter-spacing: 8px; padding: 12px 32px; border-radius: 12px; font-family: monospace;">{otp_code}</span>
            </div>
            <p style="color: #ff6b6b; font-size: 13px; font-weight: 700; text-align: center;">⚠️ هذا الكود صالح لمدة 10 دقائق فقط.</p>
            <p style="color: #a2a8b9; font-size: 13px; line-height: 1.7; margin-top: 20px;">إذا لم تطلب إنشاء حساب في منصة وسيط، يرجى تجاهل هذا البريد.</p>
        </div>
        <div style="text-align: center; margin-top: 20px; color: #5a5f7a; font-size: 12px;">
            <p>© 2026 منصة وسيط - جميع الحقوق محفوظة</p>
            <p style="direction: ltr;">waseet.shop</p>
        </div>
    </div>
    """
    try:
        if app.config['MAIL_USERNAME'] and app.config['MAIL_PASSWORD']:
            msg = MIMEMultipart('alternative')
            msg['From'] = app.config['MAIL_FROM']
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'html'))
            server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
            server.starttls()
            server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            server.sendmail(app.config['MAIL_FROM'], to_email, msg.as_string())
            server.quit()
            print(f'✅ تم إرسال إيميل التحقق بنجاح إلى {to_email}')
        else:
            print(f"""
╔{'═'*50}╗
║  📧 إيميل التحقق (وضع التطوير)                         ║
║  ⚠️ لم يتم ضبط إعدادات SMTP - الإيميل لم يرسل فعلياً     ║
║  إلى: {to_email:<40}║
║  كود التحقق: {otp_code:<36}║
║  صالح لمدة: 10 دقائق                                    ║
║  💡 اذهب إلى لوحة الإدارة ← إعدادات البريد لضبط SMTP    ║
╚{'═'*50}╝
            """)
            return True
        return True
    except Exception as e:
        print(f'❌ فشل إرسال الإيميل إلى {to_email}: {str(e)}')
        return True

# ==================== موديل قاعدة البيانات ====================
class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Float, default=1000.0)
    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    otp_code = db.Column(db.String(10), nullable=True)
    otp_expiry = db.Column(db.DateTime, nullable=True)

class Account(db.Model):
    __tablename__ = 'account'
    id = db.Column(db.Integer, primary_key=True)
    game = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.String(500))
    price = db.Column(db.Float, nullable=False, index=True)
    seller = db.Column(db.String(100), nullable=False, index=True)
    platform = db.Column(db.String(50), default='PC', index=True)
    status = db.Column(db.String(50), default='Available', index=True)
    image_url = db.Column(db.String(500), nullable=True)
    tags = db.Column(db.String(500), nullable=True)

class Order(db.Model):
    __tablename__ = 'order'
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False, index=True)
    buyer_name = db.Column(db.String(100), nullable=False, index=True)
    seller_name = db.Column(db.String(100), nullable=False, index=True)
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending_Payment', index=True)
    credentials = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now(), index=True)
    credentials_submitted_at = db.Column(db.DateTime, nullable=True)
    buyer_recovery_data = db.Column(db.Text, nullable=True)
    buyer_recovery_submitted_at = db.Column(db.DateTime, nullable=True)
    commission_rate = db.Column(db.Float, default=5.0)
    commission_amount = db.Column(db.Float, default=0.0)
    admin_fee = db.Column(db.Float, default=0.0)
    dispute_resolved_by = db.Column(db.String(100), nullable=True)
    dispute_winner = db.Column(db.String(100), nullable=True)
    dispute_resolved_at = db.Column(db.DateTime, nullable=True)
    account = db.relationship('Account', backref='orders')

class DisputeEvidence(db.Model):
    __tablename__ = 'dispute_evidence'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False, index=True)
    uploaded_by = db.Column(db.String(100), nullable=False)
    text_content = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    order = db.relationship('Order', backref=db.backref('dispute_evidences', cascade='all, delete-orphan'))

class Message(db.Model):
    __tablename__ = 'message'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=True, index=True)
    sender = db.Column(db.String(100), nullable=False)
    receiver = db.Column(db.String(100), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    time = db.Column(db.DateTime, default=db.func.now())

class WithdrawalRequest(db.Model):
    __tablename__ = 'withdrawal_request'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending', index=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

class Review(db.Model):
    __tablename__ = 'review'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False, index=True)
    buyer_name = db.Column(db.String(100), nullable=False)
    seller_name = db.Column(db.String(100), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    order = db.relationship('Order', backref=db.backref('reviews', cascade='all, delete-orphan'))

class Report(db.Model):
    __tablename__ = 'report'
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=True, index=True)
    reporter_name = db.Column(db.String(100), nullable=False, index=True)
    seller_name = db.Column(db.String(100), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='Pending', index=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    account = db.relationship('Account', backref='reports')

class Notification(db.Model):
    __tablename__ = 'notification'
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(100), nullable=False, index=True)
    message = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(300), nullable=True)
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

with app.app_context():
    db.create_all()
    admin_email = 'atrkl250@gmail.com'
    admin_name = 'Turki.admin'
    old_admins = User.query.filter(
        (User.name == 'admin') | 
        (User.email == 'atrk1250@gmail.com') |
        (User.name == admin_name) |
        (User.email == admin_email)
    ).all()
    for old in old_admins:
        db.session.delete(old)
    if old_admins:
        db.session.commit()
    admin_user = User.query.filter_by(name=admin_name).first()
    if not admin_user:
        hashed = bcrypt.generate_password_hash('Turki@7070').decode('utf-8')
        admin = User(name=admin_name, email=admin_email, password=hashed, balance=100000.0, is_admin=True, is_banned=False, email_verified=True)
        db.session.add(admin)
        db.session.commit()

# ==================== دالة مساعدة لإنشاء الإشعارات ====================
def create_notification(user_name, message, link=None):
    notification = Notification(user_name=user_name, message=message, link=link, is_read=False)
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
        return {'avg': round(avg_rating, 1), 'count': len(reviews)}
    return {'get_seller_rating': get_seller_rating}

@app.context_processor
def inject_unread_reports():
    if 'user' in session:
        user = User.query.filter_by(name=session['user']).first()
        if user and user.is_admin:
            unread_count = Report.query.filter_by(status='Pending').count()
            return {'unread_reports_count': unread_count}
    return {'unread_reports_count': 0}

@app.context_processor
def inject_notifications_count():
    if 'user' in session:
        user = User.query.filter_by(name=session['user']).first()
        if user:
            unread_notifications = Notification.query.filter_by(user_name=user.name, is_read=False).count()
            return {'unread_notifications_count': unread_notifications}
    return {'unread_notifications_count': 0}

# ==================== دوال حساب العمولة ====================

def calculate_commission(order_price, commission_rate=None):
    if commission_rate is None:
        commission_rate = app.config['COMMISSION_RATE']
    commission = round(order_price * (commission_rate / 100), 2)
    return commission

def apply_commission_and_release(order):
    commission = calculate_commission(order.price)
    seller_net = order.price - commission
    order.commission_amount = commission
    order.commission_rate = app.config['COMMISSION_RATE']
    seller_user = User.query.filter_by(name=order.seller_name).first()
    if seller_user:
        seller_user.balance += seller_net
    order.status = 'Completed'
    order.account.status = 'Sold'
    create_notification(order.seller_name, f'✅ تم إتمام الطلب #{order.id} بنجاح! تم إيداع {seller_net} ريال في محفظتك (بعد خصم عمولة {commission} ريال).', f'/order/{order.id}')
    create_notification(order.buyer_name, f'✅ تم إتمام الطلب #{order.id} بنجاح. شكراً لاستخدامك منصة وسيط!', f'/order/{order.id}')

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
        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}_{int(datetime.utcnow().timestamp())}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        image_url = url_for('static', filename=f'uploads/{unique_filename}')
        return {'success': True, 'image_url': image_url}, 200
    return {'error': 'نوع الملف غير مسموح. الأنواع المسموحة: png, jpg, jpeg, gif, webp, svg'}, 400

# ==================== التحقق من التحرير التلقائي مع العمولة ====================

def check_auto_release():
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
                commission = calculate_commission(order.price)
                seller_net = order.price - commission
                order.commission_amount = commission
                order.commission_rate = app.config['COMMISSION_RATE']
                seller_user = User.query.filter_by(name=order.seller_name).first()
                if seller_user:
                    seller_user.balance += seller_net
                order.status = 'Completed'
                order.account.status = 'Sold'
                auto_released_any = True
                create_notification(order.seller_name, f'🔄 تم تحرير {seller_net} ريال تلقائياً لك (بعد خصم عمولة {commission} ريال) لانتهاء المهلة دون تأكيد من المشتري.', f'/order/{order.id}')
                create_notification(order.buyer_name, f'🔄 تم تحرير المبلغ للبائع {order.seller_name} تلقائياً لانتهاء المهلة (يومين) دون تأكيد الاستلام.', f'/order/{order.id}')
                admin_msg = Message(order_id=order.id, sender='admin', receiver=order.buyer_name, content=f'🔄 تم تحرير المبلغ تلقائياً للبائع {order.seller_name} لانتهاء المهلة (يومين) دون تأكيد الاستلام من المشتري. (عمولة المنصة: {commission} ريال)')
                db.session.add(admin_msg)
    if auto_released_any:
        db.session.commit()
        flash('تم تحرير مبلغ طلب تلقائياً لانتهاء المهلة المحددة.', 'info')

# ==================== دوال مساعدة للنظام الجديد ====================

def get_order_display_status(order_status):
    status_map = {
        'Pending': 'بانتظار الدفع', 'Pending_Payment': 'بانتظار الدفع',
        'Paid_Hold': 'المبلغ معلق ⏳', 'Funds_Held': 'المبلغ معلق ⏳',
        'Credentials_Submitted': 'تم تسليم الحساب - بانتظار التأكيد',
        'In_Dispute': 'تحت النزاع والفحص ⚖️', 'Disputed': 'تحت النزاع والفحص ⚖️',
        'Completed': 'مكتمل ✅', 'Refunded': 'مسترجع ↩️',
        'Awaiting_Buyer_Recovery': 'بانتظار بيانات الاسترداد من المشتري'
    }
    return status_map.get(order_status, order_status)

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
    msg = Message(order_id=order.id, sender=current_user.name, receiver=receiver_name, content=content)
    db.session.add(msg)
    create_notification(receiver_name, f'💬 لديك رسالة جديدة من {current_user.name} بخصوص الطلب #{order.id}', f'/order/{order.id}')
    db.session.commit()
    return {'success': True, 'message': {'id': msg.id, 'sender': msg.sender, 'content': msg.content, 'time': msg.time.strftime('%H:%M'), 'time_full': msg.time.isoformat()}}, 200

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
    return {'success': True, 'status': order.status, 'display_status': get_order_display_status(order.status), 'order_id': order.id}, 200

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
    return {'success': True, 'order_id': order.id, 'buyer_name': order.buyer_name, 'seller_name': order.seller_name, 'messages': [{'id': msg.id, 'sender': msg.sender, 'content': msg.content, 'time': msg.time.strftime('%H:%M'), 'time_full': msg.time.isoformat()} for msg in messages]}, 200

# ==================== API: الإشعارات ====================

@app.route('/api/notifications', methods=['GET'])
def api_get_notifications():
    if 'user' not in session:
        return {'error': 'Not logged in'}, 401
    current_user = User.query.filter_by(name=session['user']).first()
    if not current_user:
        return {'error': 'User not found'}, 404
    notifications = Notification.query.filter_by(user_name=current_user.name).order_by(Notification.id.desc()).limit(20).all()
    return {'success': True, 'notifications': [{'id': n.id, 'message': n.message, 'link': n.link, 'is_read': n.is_read, 'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')} for n in notifications]}, 200

@app.route('/api/notifications/mark_read', methods=['POST'])
def api_mark_notifications_read():
    if 'user' not in session:
        return {'error': 'Not logged in'}, 401
    current_user = User.query.filter_by(name=session['user']).first()
    if not current_user:
        return {'error': 'User not found'}, 404
    data = request.get_json() or {}
    notification_id = data.get('notification_id')
    if notification_id:
        notification = Notification.query.get(notification_id)
        if notification and notification.user_name == current_user.name:
            notification.is_read = True
            db.session.commit()
            return {'success': True}, 200
        return {'error': 'Notification not found'}, 404
    else:
        Notification.query.filter_by(user_name=current_user.name, is_read=False).update({'is_read': True})
        db.session.commit()
        return {'success': True}, 200

@app.route('/api/notifications/count', methods=['GET'])
def api_get_notifications_count():
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
    if account.seller == current_user.name:
        return {'error': 'لا يمكنك الإبلاغ عن حسابك الخاص'}, 400
    existing_report = Report.query.filter_by(account_id=account.id, reporter_name=current_user.name).filter(Report.status != 'Dismissed').first()
    if existing_report:
        return {'error': 'لقد قمت بالإبلاغ عن هذا الحساب مسبقاً، وهو قيد المراجعة'}, 400
    report = Report(account_id=account.id, reporter_name=current_user.name, seller_name=account.seller, reason=reason)
    db.session.add(report)
    create_notification('admin', f'🚩 تم استلام بلاغ جديد من {current_user.name} ضد البائع {account.seller} في إعلان "{account.game}". السبب: {reason[:100]}{"..." if len(reason) > 100 else ""}', f'/admin/disputes')
    db.session.commit()
    return {'success': True, 'message': 'تم تقديم البلاغ بنجاح. سيتم مراجعة البلاغ من قبل الإدارة في أقرب وقت.'}, 200

@app.route('/api/reports', methods=['GET'])
def api_get_reports():
    if 'user' not in session:
        return {'error': 'Not logged in'}, 401
    current_user = User.query.filter_by(name=session['user']).first()
    if not current_user or not current_user.is_admin:
        return {'error': 'Unauthorized'}, 403
    reports = Report.query.order_by(Report.id.desc()).all()
    return {'success': True, 'reports': [{'id': r.id, 'account_id': r.account_id, 'account_game': r.account.game if r.account else 'محذوف', 'reporter_name': r.reporter_name, 'seller_name': r.seller_name, 'reason': r.reason, 'status': r.status, 'created_at': r.created_at.strftime('%Y-%m-%d %H:%M')} for r in reports]}, 200

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
    action = data.get('action')
    report = Report.query.get(report_id)
    if not report:
        return {'error': 'البلاغ غير موجود'}, 404
    if action == 'delete_account':
        if report.account:
            db.session.delete(report.account)
        report.status = 'Reviewed'
        db.session.commit()
        return {'success': True, 'message': f'تم حذف الإعلان المخالف للبائع {report.seller_name} وحظر الإعلان بنجاح.'}, 200
    elif action == 'dismiss':
        report.status = 'Dismissed'
        db.session.commit()
        return {'success': True, 'message': 'تم رفض البلاغ وإغلاقه.'}, 200
    return {'error': 'Invalid action'}, 400

@app.route('/api/latest_accounts', methods=['GET'])
def api_latest_accounts():
    accounts = Account.query.filter_by(status='Available').order_by(Account.id.desc()).limit(12).all()
    return {'success': True, 'accounts': [{'id': a.id, 'game': a.game, 'description': a.description, 'price': a.price, 'seller': a.seller, 'platform': a.platform, 'image_url': a.image_url, 'created_at': a.id} for a in accounts]}, 200

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
        if '@' in email_or_phone:
            if is_temp_email(email_or_phone):
                return render_template('register.html', error='⚠️ لا يمكنك التسجيل باستخدام بريد إلكتروني مؤقت أو وهمي. يرجى استخدام بريد إلكتروني حقيقي للتحقق من حسابك.')
        existing_user = User.query.filter((User.email == email_or_phone) | (User.name == name)).first()
        if existing_user:
            return render_template('register.html', error='اسم المستخدم أو البريد/الجوال مسجل بالفعل')
        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        otp = generate_otp()
        # لا يتم إنشاء الحساب في قاعدة البيانات إلا بعد تأكيد OTP
        session['pending_registration'] = {
            'name': name,
            'email': email_or_phone,
            'password_hash': hashed,
            'otp_code': otp,
            'otp_expiry': (datetime.utcnow() + timedelta(minutes=10)).isoformat()
        }
        session.permanent = True
        send_otp_email(email_or_phone, otp, name)
        flash(f'تم إرسال كود التحقق إلى {email_or_phone} ✅ يرجى إدخال الكود لتفعيل حسابك.', 'success')
        return redirect(url_for('verify_email'))
    return render_template('register.html')

@app.route('/verify_email', methods=['GET', 'POST'])
def verify_email():
    # التحقق من وجود جلسة تسجيل معلقة (النظام الجديد)
    pending = session.get('pending_registration')
    
    if not pending:
        # النظام القديم: المستخدم مسجل بالفعل في قاعدة البيانات ويحتاج تفعيل
        if 'user' not in session:
            return redirect(url_for('login'))
        current_user = User.query.filter_by(name=session['user']).first()
        if not current_user:
            session.pop('user', None)
            return redirect(url_for('login'))
        if current_user.email_verified:
            flash('بريدك الإلكتروني مفعل بالفعل! ✅', 'success')
            return redirect(url_for('dashboard'))
        # عرض صفحة التحقق للمستخدم الموجود في قاعدة البيانات
        user_display = current_user
    else:
        # النظام الجديد: المستخدم لم يُنشأ في قاعدة البيانات بعد
        user_display = type('obj', (object,), {
            'name': pending['name'],
            'email': pending['email'],
            'email_verified': False,
            'balance': 0.0
        })()
    
    if request.method == 'POST':
        otp_input = request.form.get('otp', '').strip()
        action = request.form.get('action', '')
        
        # معالجة حالة المستخدم القديم (موجود في DB)
        if not pending and 'user' in session:
            current_user = User.query.filter_by(name=session['user']).first()
            if not current_user:
                return redirect(url_for('login'))
                
            if action == 'resend':
                new_otp = generate_otp()
                current_user.otp_code = new_otp
                current_user.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
                db.session.commit()
                send_otp_email(current_user.email, new_otp, current_user.name)
                flash(f'✅ تم إرسال كود تحقق جديد إلى {current_user.email}', 'success')
                return redirect(url_for('verify_email'))
            if not otp_input:
                flash('❌ يرجى إدخال كود التحقق.', 'danger')
                return render_template('verify_email.html', user=current_user)
            if not current_user.otp_code or current_user.otp_expiry is None:
                flash('❌ لم يتم طلب كود تحقق. يرجى إعادة إرسال الكود.', 'danger')
                return render_template('verify_email.html', user=current_user)
            if datetime.utcnow() > current_user.otp_expiry:
                flash('❌ انتهت صلاحية كود التحقق. يرجى طلب كود جديد.', 'danger')
                return render_template('verify_email.html', user=current_user)
            if otp_input == current_user.otp_code:
                current_user.email_verified = True
                current_user.otp_code = None
                current_user.otp_expiry = None
                db.session.commit()
                flash('✅ تم تفعيل بريدك الإلكتروني بنجاح! يمكنك الآن الشراء والبيع بأمان.', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('❌ كود التحقق غير صحيح. يرجى المحاولة مرة أخرى.', 'danger')
                return render_template('verify_email.html', user=current_user)
        
        # معالجة حالة المستخدم الجديد (غير موجود في DB بعد - pending)
        if pending:
            if action == 'resend':
                new_otp = generate_otp()
                pending['otp_code'] = new_otp
                pending['otp_expiry'] = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
                session['pending_registration'] = pending
                session.modified = True
                send_otp_email(pending['email'], new_otp, pending['name'])
                flash(f'✅ تم إرسال كود تحقق جديد إلى {pending["email"]}', 'success')
                return redirect(url_for('verify_email'))
            if not otp_input:
                flash('❌ يرجى إدخال كود التحقق.', 'danger')
                return render_template('verify_email.html', user=user_display)
            expiry = datetime.fromisoformat(pending['otp_expiry'])
            if datetime.utcnow() > expiry:
                flash('❌ انتهت صلاحية كود التحقق. يرجى طلب كود جديد.', 'danger')
                return render_template('verify_email.html', user=user_display)
            if otp_input == pending['otp_code']:
                # إنشاء الحساب في قاعدة البيانات بعد تأكيد OTP ✅
                new_user = User(
                    name=pending['name'],
                    email=pending['email'],
                    password=pending['password_hash'],
                    balance=1000.0,
                    is_banned=False,
                    email_verified=True,
                    otp_code=None,
                    otp_expiry=None
                )
                db.session.add(new_user)
                db.session.commit()
                # تسجيل الدخول وإزالة البيانات المؤقتة
                session['user'] = pending['name']
                session.pop('pending_registration', None)
                flash('✅ تم تفعيل بريدك الإلكتروني وإنشاء حسابك بنجاح! يمكنك الآن الشراء والبيع بأمان.', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('❌ كود التحقق غير صحيح. يرجى المحاولة مرة أخرى.', 'danger')
                return render_template('verify_email.html', user=user_display)
    
    return render_template('verify_email.html', user=user_display)

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
    normalized_query = normalize_arabic_text(query)
    MATCH_THRESHOLD = 0.50
    
    # تحسين الأداء: استخدام pagination للبحث
    page = request.args.get('page', 1, type=int)
    per_page = ITEMS_PER_PAGE
    
    # البحث: نستخدم query مع pagination بدلاً من جلب كل شي
    all_available_query = Account.query.filter_by(status='Available')
    
    # أولاً: محاولة البحث المباشر (أسرع)
    direct_results = all_available_query.filter(
        db.or_(
            Account.game.ilike(f'%{query}%'),
            Account.description.ilike(f'%{query}%'),
            Account.seller.ilike(f'%{query}%'),
            Account.tags.ilike(f'%{query}%')
        )
    ).order_by(Account.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    # إذا كانت نتائج البحث المباشر كافية، استخدمها
    if direct_results.total > 0:
        search_results = direct_results.items
        total_pages = direct_results.pages
    else:
        # غير ذلك، استخدم البحث الذكي الضبابي
        all_available = all_available_query.all()
        scored_results = []
        for account in all_available:
            fields_to_check = [account.game, account.description or '', account.seller, account.platform, account.tags or '']
            best_score = 0.0
            for field in fields_to_check:
                score = fuzzy_search_score(query, field)
                if score > best_score:
                    best_score = score
            if best_score >= MATCH_THRESHOLD:
                scored_results.append((account, best_score))
        scored_results.sort(key=lambda x: x[1], reverse=True)
        search_results = [item[0] for item in scored_results]
        total_pages = 1
    
    all_games = db.session.query(Account.game).distinct().all()
    all_platforms = db.session.query(Account.platform).distinct().all()
    
    return render_template('accounts.html', accounts=search_results, games=[g[0] for g in all_games], platforms=[p[0] for p in all_platforms], selected_game=None, selected_platform=None, search_query=query, page=page, total_pages=total_pages)

@app.route('/accounts')
def accounts():
    game_filter = request.args.get('game')
    platform_filter = request.args.get('platform')
    sort_by = request.args.get('sort', 'newest')
    page = request.args.get('page', 1, type=int)
    per_page = ITEMS_PER_PAGE
    
    query = Account.query.filter_by(status='Available')
    all_games = db.session.query(Account.game).distinct().all()
    all_platforms = db.session.query(Account.platform).distinct().all()
    
    if platform_filter:
        query = query.filter_by(platform=platform_filter)
    
    # استخدام pagination بدلاً من جلب كل البيانات
    if game_filter:
        MATCH_THRESHOLD = 0.50
        all_accounts_for_filter = query.order_by(Account.id.desc()).all()
        scored_results = []
        for account in all_accounts_for_filter:
            score = fuzzy_search_score(game_filter, account.game)
            if score >= MATCH_THRESHOLD:
                scored_results.append((account, score))
        scored_results.sort(key=lambda x: x[1], reverse=True)
        all_accounts = [item[0] for item in scored_results]
        total = len(all_accounts)
    else:
        if sort_by == 'price_asc':
            query = query.order_by(Account.price.asc())
        elif sort_by == 'price_desc':
            query = query.order_by(Account.price.desc())
        else:
            query = query.order_by(Account.id.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        all_accounts = pagination.items
        total = pagination.total
    
    total_pages = max(1, (total + per_page - 1) // per_page) if total > 0 else 1
    
    return render_template('accounts.html', accounts=all_accounts, games=[g[0] for g in all_games], platforms=[p[0] for p in all_platforms], selected_game=game_filter, selected_platform=platform_filter, current_sort=sort_by, page=page, total_pages=total_pages)

@app.route('/account/<int:account_id>')
def account_detail(account_id):
    account = Account.query.get_or_404(account_id)
    if account.status != 'Available':
        flash('عذراً، هذا الحساب غير متاح حالياً.', 'warning')
        return redirect(url_for('accounts'))
    similar_accounts = []
    if account.tags:
        tags_list = [t.strip() for t in account.tags.split(',') if t.strip()]
        for tag in tags_list:
            similar = Account.query.filter(Account.id != account.id, Account.status == 'Available', Account.tags.like(f'%{tag}%')).limit(4).all()
            similar_accounts.extend(similar)
    if not similar_accounts:
        similar_accounts = Account.query.filter(Account.id != account.id, Account.status == 'Available', Account.game == account.game).limit(4).all()
    seen_ids = set()
    unique_similar = []
    for a in similar_accounts:
        if a.id not in seen_ids:
            seen_ids.add(a.id)
            unique_similar.append(a)
    return render_template('account_detail.html', account=account, similar_accounts=unique_similar[:4])

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
        tags = request.form.get('tags', '').strip()
        image_url = None
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                unique_filename = f"account_{uuid.uuid4().hex}_{int(datetime.utcnow().timestamp())}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)
                image_url = url_for('static', filename=f'uploads/{unique_filename}')
        account = Account(game=game, description=description, price=price, seller=session['user'], platform=platform, image_url=image_url, tags=tags if tags else None, status='Available')
        db.session.add(account)
        db.session.commit()
        create_notification('admin', f'📢 تم نشر حساب جديد للبيع: "{account.game}" بقيمة {account.price} ريال بواسطة {session["user"]}.', f'/admin/disputes')
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
    check_auto_release()
    buy_orders = Order.query.filter_by(buyer_name=current_user.name).order_by(Order.id.desc()).all()
    sell_orders = Order.query.filter_by(seller_name=current_user.name).order_by(Order.id.desc()).all()
    pending_balance = 0.0
    for o in sell_orders:
        if o.status in ['Funds_Held', 'Credentials_Submitted', 'Disputed', 'Paid_Hold', 'In_Dispute']:
            pending_balance += o.price
    withdrawals = WithdrawalRequest.query.filter_by(username=current_user.name).order_by(WithdrawalRequest.id.desc()).all()
    return render_template('dashboard.html', user=current_user, buy_orders=buy_orders, sell_orders=sell_orders, pending_balance=pending_balance, withdrawals=withdrawals)

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
    order = Order(account_id=account.id, buyer_name=current_user.name, seller_name=account.seller, price=account.price, status='Pending_Payment')
    db.session.add(order)
    create_notification(account.seller, f'🛒 المشتري {current_user.name} يريد شراء حسابك "{account.game}" بقيمة {account.price} ريال. بانتظار الدفع.', f'/order/{order.id}')
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
    check_auto_release()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'pay' and current_user.name == order.buyer_name and order.status in ['Pending_Payment', 'Pending']:
            if not current_user.email_verified:
                flash('❌ يجب تفعيل بريدك الإلكتروني أولاً قبل إتمام عملية الشراء. يرجى التحقق من بريدك.', 'danger')
                return redirect(url_for('verify_email'))
            if current_user.balance >= order.price:
                current_user.balance -= order.price
                order.status = 'Paid_Hold'
                order.account.status = 'Pending'
                create_notification(order.seller_name, f'💰 تم دفع مبلغ {order.price} ريال لحسابك "{order.account.game}" وهو الآن في أمان الوسيط. يرجى تسليم بيانات الحساب.', f'/order/{order.id}')
                db.session.commit()
                flash('تم دفع المبلغ بنجاح! تم حجز الأموال في أمان الوسيط وسيتم إشعار البائع لتسليم الحساب.', 'success')
            else:
                flash('عذراً، رصيدك غير كافٍ. يرجى شحن رصيدك التجريبي أولاً.', 'danger')
        elif action == 'submit_credentials' and current_user.name == order.seller_name and order.status in ['Paid_Hold', 'Funds_Held']:
            creds = request.form.get('credentials', '').strip()
            if creds:
                order.credentials = creds
                order.status = 'Credentials_Submitted'
                order.credentials_submitted_at = datetime.utcnow()
                create_notification(order.buyer_name, f'🔑 قام البائع {order.seller_name} بتسليم بيانات الحساب "{order.account.game}". يرجى فحص الحساب وتأكيد الاستلام.', f'/order/{order.id}')
                db.session.commit()
                flash('تم تسليم معلومات الحساب للوسيط والمشتري بنجاح. سيبدأ عداد اليومين الآن! ⏱️', 'success')
            else:
                flash('يرجى إدخال معلومات صحيحة وغير فارغة.', 'warning')
        elif action == 'confirm_receipt' and current_user.name == order.buyer_name and order.status == 'Credentials_Submitted':
            apply_commission_and_release(order)
            db.session.commit()
            flash(f'شكراً لك! تم تأكيد الاستلام بنجاح. تم خصم عمولة المنصة بنسبة {app.config["COMMISSION_RATE"]}% ({order.commission_amount} ريال) وتحويل الباقي للبائع.', 'success')
        elif action == 'raise_dispute' and order.status in ['Paid_Hold', 'Funds_Held', 'Credentials_Submitted']:
            order.status = 'In_Dispute'
            text_evidence = request.form.get('dispute_text', '').strip()
            image_evidence = None
            if 'dispute_image' in request.files:
                file = request.files['dispute_image']
                if file and file.filename and allowed_file(file.filename):
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
                evidence = DisputeEvidence(order_id=order.id, uploaded_by=current_user.name, text_content=text_evidence if text_evidence else None, image_url=image_evidence if image_evidence else None)
                db.session.add(evidence)
            other_party = order.seller_name if current_user.name == order.buyer_name else order.buyer_name
            create_notification(other_party, f'⚖️ تم فتح نزاع على الطلب #{order.id} من قبل {current_user.name}. يرجى متابعة القضية مع الإدارة.', f'/order/{order.id}')
            create_notification('admin', f'⚖️ تم فتح نزاع جديد على الطلب #{order.id} من قبل {current_user.name} ضد {other_party}. يرجى التدخل والمراجعة.', f'/admin/disputes')
            db.session.commit()
            flash('تم فتح نزاع حول الطلب مع إرفاق الأدلة. تم إرسال تنبيه للمشرف للتدخل والمراجعة.', 'warning')
        elif action == 'send_message':
            content = request.form.get('content', '').strip()
            if content:
                receiver_name = order.seller_name if current_user.name == order.buyer_name else order.buyer_name
                if current_user.is_admin:
                    receiver_name = order.buyer_name
                msg = Message(order_id=order.id, sender=current_user.name, receiver=receiver_name, content=content)
                db.session.add(msg)
                create_notification(receiver_name, f'💬 لديك رسالة جديدة من {current_user.name} بخصوص الطلب #{order.id}', f'/order/{order.id}')
                db.session.commit()
        elif action == 'submit_review' and current_user.name == order.buyer_name and order.status == 'Completed':
            rating = int(request.form.get('rating', 5))
            comment = request.form.get('comment', '').strip()
            existing_review = Review.query.filter_by(order_id=order.id).first()
            if not existing_review:
                rev = Review(order_id=order.id, buyer_name=order.buyer_name, seller_name=order.seller_name, rating=rating, comment=comment)
                db.session.add(rev)
                db.session.commit()
                flash('تم إرسال تقييمك للبائع بنجاح! شكراً لك.', 'success')
            else:
                flash('لقد قمت بتقييم هذه المعاملة مسبقاً.', 'warning')
        elif action == 'submit_recovery_data' and current_user.name == order.buyer_name and order.status in ['Awaiting_Buyer_Recovery', 'In_Dispute']:
            recovery_data = request.form.get('recovery_data', '').strip()
            if recovery_data:
                order.buyer_recovery_data = recovery_data
                order.buyer_recovery_submitted_at = datetime.utcnow()
                order.status = 'Awaiting_Buyer_Recovery'
                create_notification('admin', f'📋 قام المشتري {order.buyer_name} بتسليم بيانات استرداد الحساب للطلب #{order.id}. يرجى مراجعة البيانات وإغلاق النزاع.', f'/admin/disputes')
                db.session.commit()
                flash('تم تسليم بيانات الحساب للإدارة بنجاح. بانتظار مراجعة المشرف وإغلاق النزاع واسترجاع أموالك.', 'success')
            else:
                flash('يرجى إدخال بيانات الحساب الحالية بشكل صحيح.', 'warning')
        elif action == 'add_dispute_evidence' and order.status in ['In_Dispute', 'Disputed']:
            text_evidence = request.form.get('dispute_text', '').strip()
            image_evidence = None
            if 'dispute_image' in request.files:
                file = request.files['dispute_image']
                if file and file.filename and allowed_file(file.filename):
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
                evidence = DisputeEvidence(order_id=order.id, uploaded_by=current_user.name, text_content=text_evidence if text_evidence else None, image_url=image_evidence if image_evidence else None)
                db.session.add(evidence)
                create_notification('admin', f'📎 قام {current_user.name} بإضافة دليل جديد إلى النزاع على الطلب #{order.id}. يرجى مراجعة الأدلة.', f'/admin/disputes')
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
    commission_info = None
    if order.status == 'Completed':
        commission_info = {'commission_amount': order.commission_amount or calculate_commission(order.price), 'commission_rate': order.commission_rate or app.config['COMMISSION_RATE'], 'seller_net': order.price - (order.commission_amount or calculate_commission(order.price)), 'admin_fee': order.admin_fee or 0}
    return render_template('order_details.html', order=order, messages=messages, user=current_user, order_review=order_review, dispute_evidences=dispute_evidences, remaining_seconds=remaining_seconds, commission_info=commission_info, get_order_display_status=get_order_display_status)

# ==================== Decorator حماية لوحة الإدارة ====================

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('❌ يرجى تسجيل الدخول أولاً للوصول إلى لوحة الإدارة.', 'warning')
            return redirect(url_for('login'))
        current_user = User.query.filter_by(name=session['user']).first()
        if not current_user:
            session.pop('user', None)
            flash('❌ المستخدم غير موجود في النظام.', 'warning')
            return redirect(url_for('login'))
        if not current_user.is_admin:
            return render_template('403.html'), 403
        return f(current_user=current_user, *args, **kwargs)
    return decorated_function

# ==================== لوحة الإدارة (Admin Panel) ====================

@app.route('/admin/save_smtp', methods=['POST'])
@admin_required
def admin_save_smtp(current_user):
    """حفظ إعدادات SMTP من لوحة الإدارة"""
    action = request.form.get('action', '')
    mail_server = request.form.get('mail_server', 'smtp.gmail.com')
    mail_port = int(request.form.get('mail_port', 587))
    mail_username = request.form.get('mail_username', '')
    mail_password = request.form.get('mail_password', '')
    
    if action == 'test_email':
        # إرسال إيميل تجريبي
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = mail_username
            msg['To'] = current_user.email
            msg['Subject'] = '📧 إيميل تجريبي - منصة وسيط'
            test_body = f"""
            <div dir="rtl" style="font-family: Arial; padding: 20px;">
                <h2>✅ إعدادات SMTP تعمل بنجاح!</h2>
                <p>مرحباً {current_user.name}،</p>
                <p>تم إرسال هذا الإيميل بنجاح باستخدام إعدادات SMTP الجديدة.</p>
                <p>الخادم: {mail_server}:{mail_port}</p>
                <p>البريد: {mail_username}</p>
            </div>
            """
            msg.attach(MIMEText(test_body, 'html'))
            server = smtplib.SMTP(mail_server, mail_port)
            server.starttls()
            server.login(mail_username, mail_password)
            server.sendmail(mail_username, current_user.email, msg.as_string())
            server.quit()
            smtp_status = {'success': True, 'message': f'✅ تم إرسال إيميل تجريبي بنجاح إلى {current_user.email}'}
            flash(f'✅ تم إرسال إيميل تجريبي بنجاح إلى {current_user.email}', 'success')
        except Exception as e:
            smtp_status = {'success': False, 'message': f'❌ فشل الإرسال: {str(e)}'}
            flash(f'❌ فشل إرسال الإيميل التجريبي: {str(e)}', 'danger')
        
        # إعادة تحميل الصفحة مع الحالة
        return redirect(url_for('admin_disputes'))
    
    # تحديث الإعدادات في الذاكرة مباشرة (لن يتم حفظها في ملف بعد الآن)
    app.config['MAIL_SERVER'] = mail_server
    app.config['MAIL_PORT'] = mail_port
    app.config['MAIL_USERNAME'] = mail_username
    app.config['MAIL_PASSWORD'] = mail_password
    app.config['MAIL_FROM'] = mail_username
    
    flash('✅ تم تحديث إعدادات البريد الإلكتروني في الجلسة الحالية! ⚠️ ملاحظة: لتثبيت الإعدادات بشكل دائم، قم بتعيين متغيرات البيئة MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD في لوحة تحكم Railway.', 'success')
    
    return redirect(url_for('admin_disputes'))

@app.route('/admin/disputes', methods=['GET', 'POST'])
@admin_required
def admin_disputes(current_user):
    # إعادة تحميل إعدادات SMTP لعرضها في الواجهة
    loaded_config = get_smtp_config()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action in ['release', 'refund']:
            order_id = request.form.get('order_id')
            order = Order.query.get_or_404(order_id)
            admin_fee = float(request.form.get('admin_fee', 0))
            
            if order.status in ['In_Dispute', 'Disputed']:
                order.dispute_resolved_by = current_user.name
                order.dispute_resolved_at = datetime.utcnow()
                
                if action == 'release':
                    order.dispute_winner = 'seller'
                    commission = calculate_commission(order.price)
                    order.commission_amount = commission
                    order.commission_rate = app.config['COMMISSION_RATE']
                    seller_net = order.price - commission - admin_fee
                    order.admin_fee = admin_fee
                    seller = User.query.filter_by(name=order.seller_name).first()
                    if seller:
                        seller.balance += seller_net
                    order.status = 'Completed'
                    order.account.status = 'Sold'
                    create_notification(order.seller_name, f'⚖️ تم حل النزاع لصالحك! تم إيداع {seller_net} ريال في محفظتك (بعد خصم عمولة {commission} ريال' + (f' ورسوم إدارية {admin_fee} ريال' if admin_fee > 0 else '') + f') للطلب #{order.id}.', f'/order/{order.id}')
                    create_notification(order.buyer_name, f'⚖️ تم حل النزاع لصالح البائع للطلب #{order.id}. تم تحرير المبلغ للبائع بعد خصم العمولة.', f'/order/{order.id}')
                    db.session.commit()
                    flash(f'تم حل النزاع للطلب #{order.id}: تم تحرير {seller_net} ريال للبائع (بعد خصم عمولة {commission} ريال).', 'success')
                    
                elif action == 'refund':
                    order.dispute_winner = 'buyer'
                    buyer = User.query.filter_by(name=order.buyer_name).first()
                    if buyer:
                        refund_amount = order.price - admin_fee
                        order.admin_fee = admin_fee
                        buyer.balance += refund_amount
                    seller = User.query.filter_by(name=order.seller_name).first()
                    if admin_fee > 0 and seller:
                        seller.is_banned = True
                        create_notification(order.seller_name, f'🚫 تم تجميد حسابك وحظرك من المنصة لتلاعبك بالطلب #{order.id}. تم إعادة المبلغ للمشتري وفرض رسوم إدارية.', None)
                    order.status = 'Refunded'
                    order.account.status = 'Available'
                    create_notification(order.buyer_name, f'⚖️ تم حل النزاع لصالحك! تم إعادة {refund_amount} ريال إلى محفظتك للطلب #{order.id}.' + (f' (تم خصم {admin_fee} ريال كرسوم إدارية)' if admin_fee > 0 else ''), f'/order/{order.id}')
                    create_notification(order.seller_name, f'⚖️ تم حل النزاع لصالح المشتري للطلب #{order.id}. تم إعادة المبلغ للمشتري وإلغاء الطلب.' + (' وتم تجميد حسابك.' if admin_fee > 0 else ''), f'/order/{order.id}')
                    db.session.commit()
                    flash(f'تم حل النزاع للطلب #{order.id}: تم إعادة المبلغ للمشتري' + (f' وخصم {admin_fee} ريال كرسوم إدارية' if admin_fee > 0 else '') + '.', 'success')
                    
        elif action == 'confirm_recovery':
            order_id = request.form.get('order_id')
            order = Order.query.get_or_404(order_id)
            if order.status == 'Awaiting_Buyer_Recovery' and order.buyer_recovery_data:
                buyer = User.query.filter_by(name=order.buyer_name).first()
                if buyer:
                    buyer.balance += order.price
                recovery_note = f'📋 بيانات الحساب المستردة من المشتري (بعد إغلاق النزاع):\n{order.buyer_recovery_data}'
                admin_msg_seller = Message(order_id=order.id, sender='admin', receiver=order.seller_name, content=recovery_note)
                db.session.add(admin_msg_seller)
                admin_msg_buyer = Message(order_id=order.id, sender='admin', receiver=order.buyer_name, content=f'✅ تم تأكيد استلام بيانات الحساب واسترجاع مبلغ {order.price} ريال إلى محفظتك. تم إغلاق النزاع نهائياً.')
                db.session.add(admin_msg_buyer)
                order.dispute_resolved_by = current_user.name
                order.dispute_winner = 'buyer'
                order.dispute_resolved_at = datetime.utcnow()
                order.status = 'Refunded'
                order.account.status = 'Available'
                create_notification(order.buyer_name, f'✅ تم إغلاق النزاع واسترجاع {order.price} ريال إلى محفظتك للطلب #{order.id}.', f'/order/{order.id}')
                create_notification(order.seller_name, f'📋 تم إغلاق النزاع للطلب #{order.id}. تم إرسال بيانات الحساب المستردة إليك عبر الشات.', f'/order/{order.id}')
                db.session.commit()
                flash(f'تم إغلاق النزاع للطلب #{order.id}: تم استرداد الحساب من المشتري، وإعادة المبلغ للمشتري، وإرسال بيانات الحساب للبائع.', 'success')
            elif order.status == 'Awaiting_Buyer_Recovery' and not order.buyer_recovery_data:
                flash('لم يقم المشتري بإدخال بيانات الحساب بعد. يرجى الانتظار.', 'warning')
                    
        elif action == 'approve_withdrawal':
            req_id = request.form.get('request_id')
            req = WithdrawalRequest.query.get(req_id)
            if req and req.status == 'Pending':
                req.status = 'Approved'
                create_notification(req.username, f'✅ تمت الموافقة على طلب السحب بقيمة {req.amount} ريال. سيتم تحويل المبلغ قريباً.', f'/dashboard')
                db.session.commit()
                flash(f'تمت الموافقة على طلب السحب بقيمة {req.amount} ريال للمستخدم {req.username} بنجاح.', 'success')
                
        elif action == 'reject_withdrawal':
            req_id = request.form.get('request_id')
            req = WithdrawalRequest.query.get(req_id)
            if req and req.status == 'Pending':
                req.status = 'Rejected'
                beneficiary = User.query.filter_by(name=req.username).first()
                if beneficiary:
                    beneficiary.balance += req.amount
                create_notification(req.username, f'❌ تم رفض طلب السحب بقيمة {req.amount} ريال وتم إعادة المبلغ إلى محفظتك.', f'/dashboard')
                db.session.commit()
                flash(f'تم رفض طلب السحب للمستخدم {req.username} وإعادة قيمة {req.amount} ريال لمحفظته.', 'info')
                
        elif action == 'toggle_ban':
            user_id = request.form.get('user_id')
            target_user = User.query.get(user_id)
            if target_user:
                if target_user.name == current_user.name:
                    flash('لا يمكنك حظر حسابك الشخصي!', 'danger')
                else:
                    target_user.is_banned = not target_user.is_banned
                    if target_user.is_banned:
                        create_notification(target_user.name, '🚫 تم حظر حسابك من قبل الإدارة لمخالفته شروط الاستخدام.', None)
                    db.session.commit()
                    ban_status = 'حظر' if target_user.is_banned else 'إلغاء حظر'
                    flash(f'تم {ban_status} المستخدم {target_user.name} بنجاح.', 'success')
                    
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
                    
        elif action == 'delete_user':
            user_id = request.form.get('user_id')
            target_user = User.query.get(user_id)
            if not target_user:
                flash('المستخدم غير موجود.', 'danger')
            elif target_user.name == current_user.name:
                flash('لا يمكنك حذف حسابك الشخصي!', 'danger')
            elif target_user.is_admin:
                flash('لا يمكنك حذف حساب مشرف آخر! قم أولاً بإزالة صلاحية الإشراف عنه.', 'danger')
            else:
                # حذف الحسابات التي يبيعها المستخدم
                user_accounts = Account.query.filter_by(seller=target_user.name).all()
                for acc in user_accounts:
                    db.session.delete(acc)
                # حذف المستخدم
                db.session.delete(target_user)
                db.session.commit()
                flash(f'✅ تم حذف المستخدم "{target_user.name}" وجميع حساباته بنجاح.', 'success')
                    
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
        
    disputed_orders = Order.query.filter(Order.status.in_(['In_Dispute', 'Disputed'])).all()
    recovery_orders = Order.query.filter_by(status='Awaiting_Buyer_Recovery').all()
    all_orders = Order.query.order_by(Order.id.desc()).all()
    all_users = User.query.order_by(User.id.desc()).all()
    all_withdrawals = WithdrawalRequest.query.order_by(WithdrawalRequest.id.desc()).all()
    all_reports = Report.query.order_by(Report.id.desc()).all()
    
    funds_held_total = sum(o.price for o in all_orders if o.status in ['Paid_Hold', 'Funds_Held', 'Credentials_Submitted', 'In_Dispute', 'Disputed'])
    users_balances_total = sum(u.balance for u in all_users)
    
    return render_template('admin.html', disputed_orders=disputed_orders, recovery_orders=recovery_orders, all_orders=all_orders, all_users=all_users, all_withdrawals=all_withdrawals, all_reports=all_reports, funds_held_total=funds_held_total, users_balances_total=users_balances_total, user=current_user, smtp_config=loaded_config)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)