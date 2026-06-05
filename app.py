import os
from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///waseet.db')
app.secret_key = 'waseet123_secure_key'
bcrypt = Bcrypt(app)
db = SQLAlchemy(app)
with app.app_context():
    db.create_all()

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
    # الحالات: Pending_Payment (انتظار الدفع), Funds_Held (المبلغ معلق), Credentials_Submitted (تم تسليم الحساب), Completed (مكتمل), Disputed (متنازع عليه), Refunded (مسترجع)
    credentials = db.Column(db.String(500), nullable=True) # بيانات الحساب المرسلة من البائع
    created_at = db.Column(db.DateTime, default=db.func.now())
    credentials_submitted_at = db.Column(db.DateTime, nullable=True) # وقت تسليم بيانات الحساب (للتايمر)
    
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

# بناء قاعدة البيانات وإنشاء مستخدم المشرف تلقائياً
with app.app_context():
    db.create_all()
    # إنشاء مستخدم أدمن افتراضي للتجربة
    admin_user = User.query.filter_by(name='admin').first()
    if not admin_user:
        hashed = bcrypt.generate_password_hash('admin123').decode('utf-8')
        admin = User(name='admin', email='admin@waseet.com', password=hashed, balance=100000.0, is_admin=True, is_banned=False)
        db.session.add(admin)
        db.session.commit()

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

def check_auto_release():
    """
    التحقق من الطلبات التي انتهت صلاحية التايمر لها (ساعتين من تسليم بيانات الحساب)
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
            if elapsed >= timedelta(hours=2):
                # تحرير المبلغ تلقائياً للبائع
                seller_user = User.query.filter_by(name=order.seller_name).first()
                if seller_user:
                    seller_user.balance += order.price
                order.status = 'Completed'
                order.account.status = 'Sold'
                auto_released_any = True
                
                # إشعار في الشات
                admin_msg = Message(
                    order_id=order.id,
                    sender='admin',
                    receiver=order.buyer_name,
                    content=f'🔄 تم تحرير المبلغ تلقائياً للبائع {order.seller_name} لانتهاء المهلة (ساعتين) دون تأكيد الاستلام من المشتري.'
                )
                db.session.add(admin_msg)
    
    if auto_released_any:
        db.session.commit()
        flash('تم تحرير مبلغ طلب تلقائياً لانتهاء المهلة المحددة (ساعتين دون تأكيد استلام).', 'info')

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

@app.route('/accounts')
def accounts():
    game_filter = request.args.get('game')
    platform_filter = request.args.get('platform')
    
    query = Account.query.filter_by(status='Available')
    
    all_games = db.session.query(Account.game).filter_by(status='Available').distinct().all()
    all_platforms = db.session.query(Account.platform).filter_by(status='Available').distinct().all()
    
    if game_filter:
        query = query.filter_by(game=game_filter)
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
        image_url = request.form.get('image_url', '').strip()
        
        if not image_url:
            image_url = None
            
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
    
    # التحقق من التايمر التلقائي (ساعتين)
    check_auto_release()
        
    buy_orders = Order.query.filter_by(buyer_name=current_user.name).order_by(Order.id.desc()).all()
    sell_orders = Order.query.filter_by(seller_name=current_user.name).order_by(Order.id.desc()).all()
    
    pending_balance = 0.0
    for o in sell_orders:
        if o.status in ['Funds_Held', 'Credentials_Submitted', 'Disputed']:
            pending_balance += o.price
            
    # استجلاب تاريخ طلبات السحب
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
        # خصم الرصيد من المستخدم يدوياً وحجزه
        current_user.balance -= amount
        
        # إنشاء طلب السحب معلقاً
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
    
    # التحقق من التايمر التلقائي (ساعتين)
    check_auto_release()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        # 1. دفع القيمة للوسيط
        if action == 'pay' and current_user.name == order.buyer_name and order.status == 'Pending_Payment':
            if current_user.balance >= order.price:
                current_user.balance -= order.price
                order.status = 'Funds_Held'
                order.account.status = 'Pending'
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
                order.credentials_submitted_at = datetime.utcnow() # تسجيل وقت التسليم للتايمر
                db.session.commit()
                flash('تم تسليم معلومات الحساب للوسيط والمشتري بنجاح. سيبدأ عداد الساعتين الآن! ⏱️', 'success')
            else:
                flash('يرجى إدخال معلومات صحيحة وغير فارغة.', 'warning')
                
        # 3. تأكيد الاستلام من المشتري
        elif action == 'confirm_receipt' and current_user.name == order.buyer_name and order.status == 'Credentials_Submitted':
            seller_user = User.query.filter_by(name=order.seller_name).first()
            if seller_user:
                seller_user.balance += order.price
            order.status = 'Completed'
            order.account.status = 'Sold'
            db.session.commit()
            flash('شكراً لك! تم تأكيد الاستلام بنجاح، وتحويل المبلغ فوراً إلى البائع.', 'success')
            
        # 4. فتح نزاع مع إرفاق أدلة
        elif action == 'raise_dispute' and order.status in ['Funds_Held', 'Credentials_Submitted']:
            order.status = 'Disputed'
            
            # حفظ أدلة النزاع المرفقة
            text_evidence = request.form.get('dispute_text', '').strip()
            image_evidence = request.form.get('dispute_image', '').strip()
            
            if text_evidence or image_evidence:
                evidence = DisputeEvidence(
                    order_id=order.id,
                    uploaded_by=current_user.name,
                    text_content=text_evidence if text_evidence else None,
                    image_url=image_evidence if image_evidence else None
                )
                db.session.add(evidence)
            
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
                
        # 7. إضافة دليل جديد للنزاع المفتوح
        elif action == 'add_dispute_evidence' and order.status == 'Disputed':
            text_evidence = request.form.get('dispute_text', '').strip()
            image_evidence = request.form.get('dispute_image', '').strip()
            
            if text_evidence or image_evidence:
                evidence = DisputeEvidence(
                    order_id=order.id,
                    uploaded_by=current_user.name,
                    text_content=text_evidence if text_evidence else None,
                    image_url=image_evidence if image_evidence else None
                )
                db.session.add(evidence)
                db.session.commit()
                flash('تم إضافة الدليل الجديد للنزاع بنجاح.', 'success')
            else:
                flash('يرجى إدخال نص أو رابط صورة كدليل.', 'warning')
        
        return redirect(url_for('order_details', order_id=order.id))
        
    messages = Message.query.filter_by(order_id=order.id).order_by(Message.time.asc()).all()
    order_review = Review.query.filter_by(order_id=order.id).first()
    dispute_evidences = DisputeEvidence.query.filter_by(order_id=order.id).order_by(DisputeEvidence.id.desc()).all()
    
    # حساب الوقت المتبقي للتايمر
    remaining_seconds = 0
    if order.status == 'Credentials_Submitted' and order.credentials_submitted_at:
        elapsed = datetime.utcnow() - order.credentials_submitted_at
        total_seconds = 2 * 3600  # ساعتين
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
        
        # 1. حل النزاعات وتحرير/استرجاع المبالغ
        if action in ['release', 'refund']:
            order_id = request.form.get('order_id')
            order = Order.query.get_or_404(order_id)
            
            if order.status == 'Disputed':
                if action == 'release':
                    seller = User.query.filter_by(name=order.seller_name).first()
                    if seller:
                        seller.balance += order.price
                    order.status = 'Completed'
                    order.account.status = 'Sold'
                    db.session.commit()
                    flash(f'تم حل النزاع للطلب #{order.id}: تم تحرير الأموال لصالح البائع.', 'success')
                elif action == 'refund':
                    buyer = User.query.filter_by(name=order.buyer_name).first()
                    if buyer:
                        buyer.balance += order.price
                    order.status = 'Refunded'
                    order.account.status = 'Available'
                    db.session.commit()
                    flash(f'تم حل النزاع للطلب #{order.id}: تم إعادة المبلغ للمشتري وجعل الحساب متاحاً.', 'success')
                    
        # 2. الموافقة على طلبات السحب
        elif action == 'approve_withdrawal':
            req_id = request.form.get('request_id')
            req = WithdrawalRequest.query.get(req_id)
            if req and req.status == 'Pending':
                req.status = 'Approved'
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
    all_orders = Order.query.order_by(Order.id.desc()).all()
    all_users = User.query.order_by(User.id.desc()).all()
    all_withdrawals = WithdrawalRequest.query.order_by(WithdrawalRequest.id.desc()).all()
    
    # حساب الإحصائيات المالية المتقدمة
    funds_held_total = sum(o.price for o in all_orders if o.status in ['Funds_Held', 'Credentials_Submitted', 'Disputed'])
    users_balances_total = sum(u.balance for u in all_users)
    
    return render_template(
        'admin.html', 
        disputed_orders=disputed_orders, 
        all_orders=all_orders, 
        all_users=all_users,
        all_withdrawals=all_withdrawals,
        funds_held_total=funds_held_total,
        users_balances_total=users_balances_total,
        user=current_user
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)