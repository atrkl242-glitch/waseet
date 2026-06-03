import os
from flask import Flask, render_template, request, redirect, session
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///waseet.db')
app.secret_key = 'waseet123'
bcrypt = Bcrypt(app)
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game = db.Column(db.String(100))
    description = db.Column(db.String(500))
    price = db.Column(db.Float)
    seller = db.Column(db.String(100))

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer)
    sender = db.Column(db.String(100))
    receiver = db.Column(db.String(100))
    content = db.Column(db.String(500))
    time = db.Column(db.DateTime, default=db.func.now())

# هذا الجزء يقوم بمسح وإعادة إنشاء الجداول لضمان التحديث
with app.app_context():
    db.drop_all()
    db.create_all()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(name=name, email=email, password=hashed)
        db.session.add(user)
        db.session.commit()
        session.permanent = True
        session['user'] = user.name
        return redirect('/')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            session.permanent = True
            session['user'] = user.name
            return redirect('/accounts')
        return render_template('login.html', error='بيانات خاطئة')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

@app.route('/accounts')
def accounts():
    all_accounts = Account.query.all()
    return render_template('accounts.html', accounts=all_accounts)

@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if 'user' not in session:
        return redirect('/login')
    if request.method == 'POST':
        game = request.form['game']
        description = request.form['description']
        price = request.form['price']
        account = Account(game=game, description=description, price=price, seller=session['user'])
        db.session.add(account)
        db.session.commit()
        return redirect('/accounts')
    return render_template('sell.html')

@app.route('/chat/<int:account_id>', methods=['GET', 'POST'])
def chat(account_id):
    if 'user' not in session:
        return redirect('/login')
    account = Account.query.get(account_id)
    if request.method == 'POST':
        content = request.form['content']
        msg = Message(
            account_id=account_id,
            sender=session['user'],
            receiver=account.seller,
            content=content
        )
        db.session.add(msg)
        db.session.commit()
    messages = Message.query.filter_by(account_id=account_id).all()
    return render_template('chat.html', account=account, messages=messages)

if name == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)