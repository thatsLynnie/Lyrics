from flask import Flask, send_from_directory, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os
from datetime import timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'lyrics.db')
app = Flask(__name__, static_folder=BASE, static_url_path='')
app.secret_key = os.environ.get('LYRICS_SECRET_KEY', 'cambia-esta-clave-en-produccion')
app.permanent_session_lifetime = timedelta(days=7)

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

@app.get('/')
def home():
    return send_from_directory(BASE, 'index.html')

@app.post('/api/register')
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get('name','')).strip()
    email = str(data.get('email','')).strip().lower()
    password = str(data.get('password',''))
    if len(name) < 2 or '@' not in email or len(password) < 6:
        return jsonify(ok=False, message='Completa los datos correctamente. La contraseña debe tener al menos 6 caracteres.'), 400
    try:
        with get_db() as db:
            cur = db.execute('INSERT INTO users(name,email,password_hash) VALUES(?,?,?)',
                             (name,email,generate_password_hash(password)))
            user_id = cur.lastrowid
        session.permanent = True
        session['user_id'] = user_id
        session['user_name'] = name
        return jsonify(ok=True, message='Cuenta creada correctamente.', user={'id':user_id,'name':name,'email':email})
    except sqlite3.IntegrityError:
        return jsonify(ok=False, message='Ya existe una cuenta con ese correo.'), 409

@app.post('/api/login')
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get('email','')).strip().lower()
    password = str(data.get('password',''))
    with get_db() as db:
        user = db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify(ok=False, message='Correo o contraseña incorrectos.'), 401
    session.permanent = True
    session['user_id'] = user['id']
    session['user_name'] = user['name']
    return jsonify(ok=True, message='Inicio de sesión correcto.', user={'id':user['id'],'name':user['name'],'email':user['email']})

@app.post('/api/logout')
def logout():
    session.clear()
    return jsonify(ok=True)

@app.get('/api/me')
def me():
    if 'user_id' not in session:
        return jsonify(ok=False, user=None)
    return jsonify(ok=True, user={'id':session['user_id'],'name':session.get('user_name','Usuario')})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='127.0.0.1', port=5000)
