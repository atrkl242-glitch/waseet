import os
from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///waseet.db'
app.secret_key = os.environ.get('SECRET_KEY', 'waseet123')
db = SQLAlchemy(app)
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

with app.app_context():
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
        user = User(name=name, email=email, password=password)
        db.session.add(user)
        db.session.commit()
        session['user'] = name
        return redirect('/')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['user'] = user.name
            return redirect('/')
        return 'بيانات خاطئة'
    return render_template('login.html')
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')
class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game = db.Column(db.String(100))
    description = db.Column(db.String(500))
    price = db.Column(db.Float)
    seller = db.Column(db.String(100))

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
