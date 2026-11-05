from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3, os, json, csv, io
import mysql.connector
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
LANDING = BASE / 'Lyrics_F'
load_dotenv(BASE / '.env')
from ai_service import (
    AssistantServiceError,
    assistant_name,
    available_providers,
    daily_limit,
    generate_reply_with_fallback,
    is_configured,
    provider_settings,
)

DB_BACKEND = os.environ.get('LYRICS_DB_BACKEND', 'mysql').strip().lower()
DB = Path(os.environ.get('LYRICS_DATABASE', BASE / 'lyrics.db')).expanduser().resolve()
MYSQL_CONFIG = {
    'host': os.environ.get('LYRICS_MYSQL_HOST', '127.0.0.1'),
    'port': int(os.environ.get('LYRICS_MYSQL_PORT', '3306')),
    'user': os.environ.get('LYRICS_MYSQL_USER', 'root'),
    'password': os.environ.get('LYRICS_MYSQL_PASSWORD', ''),
    'database': os.environ.get('LYRICS_MYSQL_DATABASE', 'lyrics'),
    'charset': 'utf8mb4',
}
UPLOADS = Path(os.environ.get('LYRICS_UPLOADS', BASE / 'uploads')).expanduser().resolve()
UPLOADS.mkdir(exist_ok=True)
ASSETS = BASE / 'img'
ALLOWED_UPLOADS = {'mp3','wav','ogg','m4a','mid','midi','pdf','musicxml','xml','png','jpg','jpeg','txt','json'}

app = Flask(__name__, template_folder=str(BASE), static_folder=None)
app.config['SECRET_KEY'] = os.environ.get('LYRICS_SECRET_KEY') or os.urandom(32)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.permanent_session_lifetime = timedelta(days=7)

SCHEMA = '''
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS roles (
  id_rol INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL UNIQUE,
  descripcion TEXT
);
CREATE TABLE IF NOT EXISTS users (
  id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  correo TEXT NOT NULL UNIQUE,
  contrasena_hash TEXT NOT NULL,
  fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  estado TEXT NOT NULL DEFAULT 'activo',
  biografia TEXT NOT NULL DEFAULT '',
  pais TEXT NOT NULL DEFAULT '',
  id_rol INTEGER NOT NULL,
  FOREIGN KEY (id_rol) REFERENCES roles(id_rol)
);
CREATE TABLE IF NOT EXISTS projects (
  id_proyecto INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  descripcion TEXT DEFAULT '',
  fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  estado TEXT NOT NULL DEFAULT 'activo',
  id_usuario_creador INTEGER NOT NULL,
  FOREIGN KEY (id_usuario_creador) REFERENCES users(id_usuario) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS project_users (
  id_proyecto INTEGER NOT NULL,
  id_usuario INTEGER NOT NULL,
  permiso TEXT NOT NULL DEFAULT 'editor',
  fecha_asignacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_proyecto,id_usuario),
  FOREIGN KEY (id_proyecto) REFERENCES projects(id_proyecto) ON DELETE CASCADE,
  FOREIGN KEY (id_usuario) REFERENCES users(id_usuario) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS resources (
  id_recurso INTEGER PRIMARY KEY AUTOINCREMENT,
  tipo TEXT NOT NULL,
  nombre TEXT NOT NULL,
  url_archivo TEXT,
  descripcion TEXT DEFAULT '',
  fecha_subida TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_proyecto INTEGER NOT NULL,
  FOREIGN KEY (id_proyecto) REFERENCES projects(id_proyecto) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS compositions (
  id_composicion INTEGER PRIMARY KEY AUTOINCREMENT,
  titulo TEXT NOT NULL,
  descripcion TEXT DEFAULT '',
  instrumento TEXT NOT NULL DEFAULT 'Piano',
  dificultad TEXT NOT NULL DEFAULT '',
  genero TEXT NOT NULL DEFAULT '',
  fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_proyecto INTEGER NOT NULL,
  FOREIGN KEY (id_proyecto) REFERENCES projects(id_proyecto) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS score_favorites (
  id_usuario INTEGER NOT NULL,
  id_composicion INTEGER NOT NULL,
  fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_usuario,id_composicion),
  FOREIGN KEY (id_usuario) REFERENCES users(id_usuario) ON DELETE CASCADE,
  FOREIGN KEY (id_composicion) REFERENCES compositions(id_composicion) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS scores (
  id_partitura INTEGER PRIMARY KEY AUTOINCREMENT,
  formato TEXT NOT NULL DEFAULT 'lyrics-score',
  url_archivo TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_composicion INTEGER NOT NULL,
  contenido_json TEXT DEFAULT '{}',
  FOREIGN KEY (id_composicion) REFERENCES compositions(id_composicion) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS recordings (
  id_grabacion INTEGER PRIMARY KEY AUTOINCREMENT,
  archivo_audio TEXT NOT NULL,
  duracion REAL DEFAULT 0,
  formato TEXT DEFAULT 'webm',
  fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_composicion INTEGER NOT NULL,
  id_usuario INTEGER NOT NULL,
  FOREIGN KEY (id_composicion) REFERENCES compositions(id_composicion) ON DELETE CASCADE,
  FOREIGN KEY (id_usuario) REFERENCES users(id_usuario) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS analyses (
  id_analisis INTEGER PRIMARY KEY AUTOINCREMENT,
  tipo TEXT NOT NULL,
  resultado TEXT NOT NULL,
  observaciones TEXT DEFAULT '',
  fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_grabacion INTEGER,
  id_proyecto INTEGER NOT NULL,
  FOREIGN KEY (id_grabacion) REFERENCES recordings(id_grabacion) ON DELETE SET NULL,
  FOREIGN KEY (id_proyecto) REFERENCES projects(id_proyecto) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS activities (
  id_actividad INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  descripcion TEXT DEFAULT '',
  fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_docente INTEGER NOT NULL,
  id_proyecto INTEGER,
  FOREIGN KEY (id_docente) REFERENCES users(id_usuario) ON DELETE CASCADE,
  FOREIGN KEY (id_proyecto) REFERENCES projects(id_proyecto) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS evaluations (
  id_evaluacion INTEGER PRIMARY KEY AUTOINCREMENT,
  titulo TEXT NOT NULL,
  tipo TEXT NOT NULL DEFAULT 'formativa',
  fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_actividad INTEGER NOT NULL,
  FOREIGN KEY (id_actividad) REFERENCES activities(id_actividad) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS evaluation_results (
  id_resultado INTEGER PRIMARY KEY AUTOINCREMENT,
  calificacion REAL,
  observaciones TEXT DEFAULT '',
  fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_evaluacion INTEGER NOT NULL,
  id_usuario INTEGER NOT NULL,
  UNIQUE(id_evaluacion,id_usuario),
  FOREIGN KEY (id_evaluacion) REFERENCES evaluations(id_evaluacion) ON DELETE CASCADE,
  FOREIGN KEY (id_usuario) REFERENCES users(id_usuario) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS tracking (
  id_seguimiento INTEGER PRIMARY KEY AUTOINCREMENT,
  progreso INTEGER NOT NULL DEFAULT 0,
  comentarios TEXT DEFAULT '',
  fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_proyecto INTEGER NOT NULL,
  id_usuario INTEGER NOT NULL,
  FOREIGN KEY (id_proyecto) REFERENCES projects(id_proyecto) ON DELETE CASCADE,
  FOREIGN KEY (id_usuario) REFERENCES users(id_usuario) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS ai_conversations (
  id_conversacion INTEGER PRIMARY KEY AUTOINCREMENT,
  titulo TEXT NOT NULL DEFAULT 'Nueva conversación',
  fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_usuario INTEGER NOT NULL,
  FOREIGN KEY (id_usuario) REFERENCES users(id_usuario) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS ai_messages (
  id_mensaje INTEGER PRIMARY KEY AUTOINCREMENT,
  rol TEXT NOT NULL,
  contenido TEXT NOT NULL,
  fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_conversacion INTEGER NOT NULL,
  FOREIGN KEY (id_conversacion) REFERENCES ai_conversations(id_conversacion) ON DELETE CASCADE
);
'''

ROLE_DATA = [
 ('administrador','Control y manejo de la plataforma en general.'),
 ('docente','Creación de actividades, evaluaciones y seguimiento académico.'),
 ('compositor','Composición, grabación, organización y análisis musical.'),
 ('mixto','Funciones de docente y compositor.')
]

ADMIN_TABLES = {
    'roles': 'Roles',
    'users': 'Usuarios',
    'projects': 'Proyectos',
    'project_users': 'Acceso a proyectos',
    'resources': 'Recursos',
    'compositions': 'Composiciones',
    'score_favorites': 'Partituras favoritas',
    'scores': 'Partituras',
    'recordings': 'Grabaciones',
    'analyses': 'Análisis',
    'activities': 'Actividades',
    'evaluations': 'Evaluaciones',
    'evaluation_results': 'Resultados de evaluaciones',
    'tracking': 'Seguimiento',
}
ADMIN_READ_ONLY_TABLES = {'roles', 'users'}

@contextmanager
def db():
    sqlite_backend = DB_BACKEND == 'sqlite'
    if sqlite_backend:
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
    else:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
    adapter = DatabaseConnection(conn, sqlite_backend)
    try:
        yield adapter
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

class DatabaseRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)

class DatabaseCursor:
    def __init__(self, cursor, sqlite_backend):
        self.cursor = cursor
        self.sqlite_backend = sqlite_backend

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    @property
    def rowcount(self):
        return self.cursor.rowcount

    def _row(self, row):
        return row if row is None or self.sqlite_backend else DatabaseRow(row)

    def fetchone(self):
        return self._row(self.cursor.fetchone())

    def fetchall(self):
        return [self._row(row) for row in self.cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())

class DatabaseConnection:
    def __init__(self, connection, sqlite_backend):
        self.connection = connection
        self.sqlite_backend = sqlite_backend

    def execute(self, sql, args=()):
        if self.sqlite_backend:
            cursor = self.connection.execute(sql, args)
        else:
            sql = sql.replace('INSERT OR IGNORE INTO', 'INSERT IGNORE INTO').replace('?', '%s')
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(sql, args)
        return DatabaseCursor(cursor, self.sqlite_backend)

    def executescript(self, script):
        return self.connection.executescript(script)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()

DB_INITIALIZED = False

def init_db():
    global DB_INITIALIZED
    with db() as con:
        if DB_BACKEND == 'sqlite':
            con.executescript(SCHEMA)
            columns = {row['name'] for row in con.execute('PRAGMA table_info(users)')}
            if 'biografia' not in columns:
                con.execute("ALTER TABLE users ADD COLUMN biografia TEXT NOT NULL DEFAULT ''")
            if 'pais' not in columns:
                con.execute("ALTER TABLE users ADD COLUMN pais TEXT NOT NULL DEFAULT ''")
            composition_columns = {row['name'] for row in con.execute('PRAGMA table_info(compositions)')}
            for column in ('instrumento', 'dificultad', 'genero'):
                if column not in composition_columns:
                    con.execute(f"ALTER TABLE compositions ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
        else:
            for statement in (BASE / 'schema.sql').read_text(encoding='utf-8').split(';'):
                if statement.strip():
                    con.execute(statement)
            migrations = {
                'users': {'biografia': "VARCHAR(2000) NOT NULL DEFAULT ''", 'pais': "VARCHAR(100) NOT NULL DEFAULT ''"},
                'compositions': {
                    'instrumento': "VARCHAR(80) NOT NULL DEFAULT 'Piano'",
                    'dificultad': "VARCHAR(40) NOT NULL DEFAULT ''",
                    'genero': "VARCHAR(80) NOT NULL DEFAULT ''",
                },
            }
            for table, columns in migrations.items():
                existing = {row['COLUMN_NAME'] for row in con.execute(
                    'SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=?',
                    (table,),
                )}
                for column, definition in columns.items():
                    if column not in existing:
                        con.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
        for name, desc in ROLE_DATA:
            con.execute('INSERT OR IGNORE INTO roles(nombre,descripcion) VALUES (?,?)',(name,desc))
    DB_INITIALIZED = True

@app.before_request
def initialize_database():
    if not DB_INITIALIZED:
        init_db()

def row_dict(row):
    return dict(row) if row else None

def current_user():
    uid = session.get('user_id')
    if not uid: return None
    with db() as con:
        return row_dict(con.execute('''SELECT u.id_usuario,u.nombre,u.correo,u.fecha_creacion,u.estado,u.biografia,u.pais,r.nombre rol,r.id_rol FROM users u JOIN roles r ON r.id_rol=u.id_rol WHERE u.id_usuario=?''',(uid,)).fetchone())

def login_required(fn):
    @wraps(fn)
    def wrapped(*a,**kw):
        if not current_user(): return jsonify(ok=False,message='Debes iniciar sesión.'),401
        return fn(*a,**kw)
    return wrapped

def roles_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapped(*a,**kw):
            user=current_user()
            if not user: return jsonify(ok=False,message='Debes iniciar sesión.'),401
            if user['rol'] not in roles: return jsonify(ok=False,message='No tienes permisos para esta acción.'),403
            return fn(*a,**kw)
        return wrapped
    return deco

def admin_table_columns(con, table):
    if table not in ADMIN_TABLES:
        return None
    if DB_BACKEND == 'sqlite':
        schema_row = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        auto_increment = 'autoincrement' in str(schema_row['sql'] or '').lower() if schema_row else False
        rows = con.execute(f'PRAGMA table_info(`{table}`)').fetchall()
        columns = [{
            'name': row['name'],
            'type': str(row['type'] or '').lower(),
            'primary': bool(row['pk']),
            'auto': auto_increment and bool(row['pk']),
            'nullable': not bool(row['notnull']),
            'default': row['dflt_value'],
        } for row in rows]
    else:
        rows = con.execute(
            '''SELECT COLUMN_NAME, DATA_TYPE, COLUMN_KEY, EXTRA, IS_NULLABLE, COLUMN_DEFAULT
               FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=?
               ORDER BY ORDINAL_POSITION''',
            (table,),
        ).fetchall()
        columns = [{
            'name': row['COLUMN_NAME'],
            'type': str(row['DATA_TYPE']).lower(),
            'primary': row['COLUMN_KEY'] == 'PRI',
            'auto': 'auto_increment' in str(row['EXTRA']).lower(),
            'nullable': row['IS_NULLABLE'] == 'YES',
            'default': row['COLUMN_DEFAULT'],
        } for row in rows]
    if table == 'users':
        columns = [column for column in columns if column['name'] != 'contrasena_hash']
    return [{
        **column,
        'editable': not column['primary'] and column['name'] != 'contrasena_hash',
        'searchable': column['type'] in {
            'text', 'tinytext', 'mediumtext', 'longtext', 'varchar', 'char',
        },
    } for column in columns]

def admin_record_filter(columns, key_values):
    primary = [column['name'] for column in columns if column['primary']]
    if not primary or not isinstance(key_values, dict) or set(key_values) != set(primary):
        return None, None
    where = ' AND '.join(f'`{name}`=?' for name in primary)
    return where, tuple(key_values[name] for name in primary)

def project_access(con, project_id, user, write=False):
    if user['rol']=='administrador': return True
    row=con.execute('''SELECT p.id_usuario_creador, pu.permiso FROM projects p LEFT JOIN project_users pu ON pu.id_proyecto=p.id_proyecto AND pu.id_usuario=? WHERE p.id_proyecto=?''',(user['id_usuario'],project_id)).fetchone()
    if not row: return False
    if row['id_usuario_creador']==user['id_usuario']: return True
    return bool(row['permiso']) and (not write or row['permiso'] in ('editor','owner'))

def payload(): return request.get_json(silent=True) or {}

def touch_project(con,pid):
    con.execute('UPDATE projects SET fecha_actualizacion=CURRENT_TIMESTAMP WHERE id_proyecto=?',(pid,))

@app.get('/')
def home(): return send_from_directory(LANDING, 'index.html')

@app.get('/dashboard')
def dashboard():
    return send_from_directory(BASE, 'dashboard.html')

@app.get('/dashboard.css')
def dashboard_styles():
    return send_from_directory(BASE, 'dashboard.css')

@app.get('/dashboard.js')
def dashboard_script():
    return send_from_directory(BASE, 'dashboard.js')

@app.get('/ai.css')
def ai_styles():
    return send_from_directory(BASE, 'ai.css')

@app.get('/ai.js')
def ai_script():
    return send_from_directory(BASE, 'ai.js')

@app.get('/landing.js')
def landing_script():
    return send_from_directory(BASE, 'landing.js')

@app.get('/estilos.css')
@app.get('/estilo.css')
def landing_styles():
    return send_from_directory(LANDING, 'estilos.css')

@app.get('/img/<path:filename>')
def image_asset(filename):
    return send_from_directory(LANDING / 'img', filename)

@app.get('/api/me')
def me():
    u=current_user()
    return jsonify(ok=bool(u), user=u)

@app.post('/api/register')
def register():
    d=payload(); name=str(d.get('name','')).strip(); email=str(d.get('email','')).strip().lower(); password=str(d.get('password',''))
    if len(name)<2 or '@' not in email or len(password)<6: return jsonify(ok=False,message='Completa los datos. La contraseña debe tener mínimo 6 caracteres.'),400
    with db() as con:
        role=con.execute("SELECT id_rol FROM roles WHERE nombre='compositor'").fetchone()
        try:
            cur=con.execute('INSERT INTO users(nombre,correo,contrasena_hash,id_rol) VALUES(?,?,?,?)',(name,email,generate_password_hash(password),role['id_rol']))
        except (sqlite3.IntegrityError, mysql.connector.IntegrityError): return jsonify(ok=False,message='Ya existe una cuenta con ese correo.'),409
        uid=cur.lastrowid
    session.permanent=True; session['user_id']=uid
    return jsonify(ok=True,message='Cuenta creada correctamente.',user=current_user())

@app.post('/api/login')
def login():
    d=payload(); email=str(d.get('email','')).strip().lower(); password=str(d.get('password',''))
    with db() as con: u=con.execute('SELECT * FROM users WHERE correo=?',(email,)).fetchone()
    if not u or not check_password_hash(u['contrasena_hash'],password): return jsonify(ok=False,message='Correo o contraseña incorrectos.'),401
    if u['estado']!='activo': return jsonify(ok=False,message='La cuenta está inactiva.'),403
    session.permanent=True; session['user_id']=u['id_usuario']
    return jsonify(ok=True,message='Inicio de sesión correcto.',user=current_user())

@app.post('/api/logout')
def logout(): session.clear(); return jsonify(ok=True)

@app.get('/api/profile')
@login_required
def profile(): return jsonify(ok=True,user=current_user())

@app.get('/api/ai/config')
@login_required
def ai_config():
    providers=available_providers()
    default_provider=providers[0]['id'] if providers else 'openai'
    return jsonify(
        ok=True,
        assistant_name=assistant_name(),
        configured=bool(providers),
        providers=providers,
        default_provider=default_provider,
        model=provider_settings(default_provider)['model'],
    )

@app.get('/api/ai/conversations')
@login_required
def ai_conversations():
    user=current_user()
    with db() as con:
        rows=con.execute(
            '''SELECT id_conversacion,titulo,fecha_creacion,fecha_actualizacion
               FROM ai_conversations WHERE id_usuario=?
               ORDER BY fecha_actualizacion DESC,id_conversacion DESC''',
            (user['id_usuario'],),
        ).fetchall()
    return jsonify(ok=True,conversations=[dict(row) for row in rows])

@app.post('/api/ai/conversations')
@login_required
def create_ai_conversation():
    user=current_user(); data=payload()
    title=str(data.get('titulo','Nueva conversación')).strip()[:100] or 'Nueva conversación'
    with db() as con:
        cur=con.execute(
            'INSERT INTO ai_conversations(titulo,id_usuario) VALUES(?,?)',
            (title,user['id_usuario']),
        )
    return jsonify(ok=True,id_conversacion=cur.lastrowid,titulo=title)

@app.get('/api/ai/conversations/<int:conversation_id>')
@login_required
def ai_conversation(conversation_id):
    user=current_user()
    with db() as con:
        conversation=con.execute(
            'SELECT id_conversacion,titulo,fecha_creacion,fecha_actualizacion FROM ai_conversations WHERE id_conversacion=? AND id_usuario=?',
            (conversation_id,user['id_usuario']),
        ).fetchone()
        if not conversation:
            return jsonify(ok=False,message='Conversación no encontrada.'),404
        messages=con.execute(
            'SELECT id_mensaje,rol,contenido,fecha_creacion FROM ai_messages WHERE id_conversacion=? ORDER BY id_mensaje',
            (conversation_id,),
        ).fetchall()
    return jsonify(ok=True,conversation=dict(conversation),messages=[dict(row) for row in messages])

@app.post('/api/ai/conversations/<int:conversation_id>/messages')
@login_required
def send_ai_message(conversation_id):
    user=current_user(); data=payload(); content=data.get('contenido')
    provider=data.get('provider','openai')
    if not isinstance(provider,str):
        return jsonify(ok=False,message='El proveedor de IA seleccionado no es válido.'),400
    try:
        selected_provider=provider_settings(provider)
    except AssistantServiceError as error:
        return jsonify(ok=False,message=str(error)),error.status_code
    if not isinstance(content,str) or not content.strip():
        return jsonify(ok=False,message='Escribe un mensaje para el asistente.'),400
    content=content.strip()
    if len(content)>4000:
        return jsonify(ok=False,message='El mensaje no puede superar los 4.000 caracteres.'),400
    with db() as con:
        conversation=con.execute(
            'SELECT id_conversacion FROM ai_conversations WHERE id_conversacion=? AND id_usuario=?',
            (conversation_id,user['id_usuario']),
        ).fetchone()
        if not conversation:
            return jsonify(ok=False,message='Conversación no encontrada.'),404
        if not is_configured(provider):
            return jsonify(ok=False,message=f"{selected_provider['name']} no está configurado. Añade la clave correspondiente al archivo .env del servidor."),503
        try:
            response_limit=daily_limit()
        except AssistantServiceError as error:
            return jsonify(ok=False,message=str(error)),error.status_code
        cutoff="datetime('now','-1 day')" if DB_BACKEND=='sqlite' else 'DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 1 DAY)'
        responses=con.execute(
            f'''SELECT COUNT(*) FROM ai_messages m
               JOIN ai_conversations c ON c.id_conversacion=m.id_conversacion
               WHERE c.id_usuario=? AND m.rol='assistant' AND m.fecha_creacion>={cutoff}''',
            (user['id_usuario'],),
        ).fetchone()[0]
        if responses>=response_limit:
            return jsonify(ok=False,message=f'Has alcanzado el límite de {response_limit} respuestas cada 24 horas.'),429
        prior=con.execute(
            'SELECT rol,contenido FROM ai_messages WHERE id_conversacion=? ORDER BY id_mensaje DESC LIMIT 20',
            (conversation_id,),
        ).fetchall()
    history=[{'role':row['rol'],'content':row['contenido']} for row in reversed(prior)]
    history.append({'role':'user','content':content})

    try:
        answer,provider_used,fallback_notice=generate_reply_with_fallback(history,provider=provider)
    except AssistantServiceError as error:
        return jsonify(ok=False,message=str(error)),error.status_code

    title=content[:97].rstrip()
    if len(content)>97:
        title+='...'
    with db() as con:
        conversation=con.execute(
            'SELECT titulo FROM ai_conversations WHERE id_conversacion=? AND id_usuario=?',
            (conversation_id,user['id_usuario']),
        ).fetchone()
        if not conversation:
            return jsonify(ok=False,message='La conversación ya no está disponible.'),404
        con.execute(
            'INSERT INTO ai_messages(rol,contenido,id_conversacion) VALUES(?,?,?)',
            ('user',content,conversation_id),
        )
        con.execute(
            'INSERT INTO ai_messages(rol,contenido,id_conversacion) VALUES(?,?,?)',
            ('assistant',answer,conversation_id),
        )
        if conversation['titulo']=='Nueva conversación':
            con.execute(
                'UPDATE ai_conversations SET titulo=?,fecha_actualizacion=CURRENT_TIMESTAMP WHERE id_conversacion=? AND id_usuario=?',
                (title,conversation_id,user['id_usuario']),
            )
        else:
            con.execute(
                'UPDATE ai_conversations SET fecha_actualizacion=CURRENT_TIMESTAMP WHERE id_conversacion=? AND id_usuario=?',
                (conversation_id,user['id_usuario']),
            )
    return jsonify(
        ok=True,
        reply=answer,
        provider_used=provider_used,
        fallback_notice=fallback_notice,
    )

@app.delete('/api/ai/conversations/<int:conversation_id>')
@login_required
def delete_ai_conversation(conversation_id):
    user=current_user()
    with db() as con:
        cursor=con.execute(
            'DELETE FROM ai_conversations WHERE id_conversacion=? AND id_usuario=?',
            (conversation_id,user['id_usuario']),
        )
        if cursor.rowcount==0:
            return jsonify(ok=False,message='Conversación no encontrada.'),404
    return jsonify(ok=True)

@app.put('/api/profile')
@login_required
def update_profile():
    u=current_user(); d=payload(); name=str(d.get('nombre',u['nombre'])).strip();
    bio=str(d.get('biografia',u['biografia'])).strip(); country=str(d.get('pais',u['pais'])).strip()
    if len(name)<2: return jsonify(ok=False,message='El nombre no es válido.'),400
    if len(bio)>1000 or len(country)>100: return jsonify(ok=False,message='La biografía o el país exceden el límite permitido.'),400
    with db() as con: con.execute('UPDATE users SET nombre=?,biografia=?,pais=? WHERE id_usuario=?',(name,bio,country,u['id_usuario']))
    return jsonify(ok=True,user=current_user())

@app.get('/api/roles')
@login_required
def roles():
    with db() as con: rows=[dict(x) for x in con.execute('SELECT * FROM roles ORDER BY id_rol')]
    return jsonify(ok=True,roles=rows)

def active_admin_count(con):
    return con.execute(
        "SELECT COUNT(*) FROM users u JOIN roles r ON r.id_rol=u.id_rol WHERE r.nombre='administrador' AND u.estado='activo'"
    ).fetchone()[0]

def admin_user_values(con, data, columns, creating=False):
    if not isinstance(data, dict):
        return None, 'Los datos enviados no son válidos.'
    by_name = {column['name']: column for column in columns}
    writable = {
        name: column for name, column in by_name.items()
        if (
            (not column['auto'] and name != 'contrasena_hash')
            if creating else column['editable'] and not column['primary']
        )
    }
    if set(data) - set(writable):
        return None, 'El registro contiene campos no permitidos.'
    values = {}
    for name, value in data.items():
        column = writable[name]
        if value is None or value == '':
            if not column['nullable'] and column['default'] is None:
                return None, f'El campo {name} es obligatorio.'
            values[name] = None if value is None else ''
            continue
        try:
            if column['type'] in {'int', 'integer', 'tinyint', 'smallint', 'mediumint', 'bigint'}:
                values[name] = int(value)
            elif column['type'] in {'float', 'double', 'real', 'decimal', 'numeric'}:
                values[name] = float(value)
            elif column['type'] in {'json'}:
                json.loads(value) if isinstance(value, str) else None
                values[name] = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            else:
                values[name] = value
        except (ValueError, TypeError, json.JSONDecodeError):
            return None, f'El valor del campo {name} no tiene un formato válido.'
    return values, None

@app.get('/api/admin/tables')
@roles_required('administrador')
def admin_tables():
    with db() as con:
        tables = []
        for name, label in ADMIN_TABLES.items():
            count = con.execute(f'SELECT COUNT(*) FROM `{name}`').fetchone()[0]
            tables.append({'name': name, 'label': label, 'count': count})
    return jsonify(ok=True, tables=tables)

@app.get('/api/admin/tables/<table>')
@roles_required('administrador')
def admin_table_records(table):
    if table not in ADMIN_TABLES:
        return jsonify(ok=False, message='Tabla no disponible.'), 404
    try:
        limit = min(100, max(1, int(request.args.get('limit', 50))))
        offset = min(100000, max(0, int(request.args.get('offset', 0))))
    except ValueError:
        return jsonify(ok=False, message='La paginación no es válida.'), 400
    search = request.args.get('q', '').strip()[:100]
    with db() as con:
        columns = admin_table_columns(con, table)
        if not columns:
            return jsonify(ok=False, message='La tabla no está disponible.'), 404
        primary = [column['name'] for column in columns if column['primary']]
        if not primary:
            return jsonify(ok=False, message='La tabla no tiene una clave primaria segura para administrarla.'), 400
        searchable = [column['name'] for column in columns if column['searchable']]
        where = ''
        args = []
        if search and searchable:
            cast_type = 'CHAR' if DB_BACKEND != 'sqlite' else 'TEXT'
            where = ' WHERE ' + ' OR '.join(f'CAST(`{name}` AS {cast_type}) LIKE ?' for name in searchable)
            args.extend([f'%{search}%'] * len(searchable))
        total = con.execute(f'SELECT COUNT(*) FROM `{table}`{where}', tuple(args)).fetchone()[0]
        order = ', '.join(f'`{name}`' for name in primary)
        safe_columns = ', '.join(f'`{column["name"]}`' for column in columns)
        rows = con.execute(
            f'SELECT {safe_columns} FROM `{table}`{where} ORDER BY {order} LIMIT ? OFFSET ?',
            tuple(args + [limit, offset]),
        ).fetchall()
    safe_rows = []
    for row in rows:
        safe_rows.append({column['name']: row[column['name']] for column in columns})
    return jsonify(
        ok=True, table=table, label=ADMIN_TABLES[table], columns=columns,
        rows=safe_rows, total=total, limit=limit, offset=offset,
        read_only=table in ADMIN_READ_ONLY_TABLES,
    )

@app.post('/api/admin/tables/<table>')
@roles_required('administrador')
def admin_create_record(table):
    if table not in ADMIN_TABLES or table in ADMIN_READ_ONLY_TABLES:
        return jsonify(ok=False, message='No se permite crear registros en esta tabla.'), 403
    with db() as con:
        columns = admin_table_columns(con, table)
        values, error = admin_user_values(con, payload(), columns, creating=True)
        if error:
            return jsonify(ok=False, message=error), 400
        if not values:
            return jsonify(ok=False, message='Indica los campos requeridos para crear el registro.'), 400
        names = list(values)
        placeholders = ','.join('?' for _ in names)
        sql = f'INSERT INTO `{table}` ({",".join(f"`{name}`" for name in names)}) VALUES ({placeholders})'
        try:
            cursor = con.execute(sql, tuple(values[name] for name in names))
        except (sqlite3.IntegrityError, mysql.connector.IntegrityError) as error:
            return jsonify(ok=False, message=f'No se pudo crear el registro por una restricción de datos: {error.msg if hasattr(error, "msg") else error}'), 400
        record_id = cursor.lastrowid
    return jsonify(ok=True, id=record_id)

@app.put('/api/admin/tables/<table>')
@roles_required('administrador')
def admin_update_record(table):
    if table not in ADMIN_TABLES or table in ADMIN_READ_ONLY_TABLES:
        return jsonify(ok=False, message='No se permite editar esta tabla directamente.'), 403
    data = payload()
    with db() as con:
        columns = admin_table_columns(con, table)
        where, keys = admin_record_filter(columns, data.get('key'))
        if where is None:
            return jsonify(ok=False, message='La clave del registro no es válida.'), 400
        values, error = admin_user_values(con, data.get('values'), columns)
        if error:
            return jsonify(ok=False, message=error), 400
        if not values:
            return jsonify(ok=False, message='No hay cambios para guardar.'), 400
        assignments = ', '.join(f'`{name}`=?' for name in values)
        try:
            cursor = con.execute(
                f'UPDATE `{table}` SET {assignments} WHERE {where}',
                tuple(values.values()) + keys,
            )
        except (sqlite3.IntegrityError, mysql.connector.IntegrityError) as error:
            return jsonify(ok=False, message=f'No se pudo guardar por una restricción de datos: {error.msg if hasattr(error, "msg") else error}'), 400
        if cursor.cursor.rowcount == 0:
            exists = con.execute(f'SELECT 1 FROM `{table}` WHERE {where}', keys).fetchone()
            if not exists:
                return jsonify(ok=False, message='El registro ya no existe.'), 404
    return jsonify(ok=True)

@app.delete('/api/admin/tables/<table>')
@roles_required('administrador')
def admin_delete_record(table):
    if table not in ADMIN_TABLES or table in ADMIN_READ_ONLY_TABLES:
        return jsonify(ok=False, message='No se permite borrar registros de esta tabla.'), 403
    data = payload()
    with db() as con:
        columns = admin_table_columns(con, table)
        where, keys = admin_record_filter(columns, data.get('key'))
        if where is None:
            return jsonify(ok=False, message='La clave del registro no es válida.'), 400
        try:
            cursor = con.execute(f'DELETE FROM `{table}` WHERE {where}', keys)
        except (sqlite3.IntegrityError, mysql.connector.IntegrityError) as error:
            return jsonify(ok=False, message=f'No se pudo borrar por relaciones con otros registros: {error.msg if hasattr(error, "msg") else error}'), 409
        if cursor.cursor.rowcount == 0:
            return jsonify(ok=False, message='El registro ya no existe.'), 404
    return jsonify(ok=True)

@app.get('/api/admin/users')
@roles_required('administrador')
def admin_user_list():
    search = request.args.get('q', '').strip()[:100]
    pattern = f'%{search}%'
    with db() as con:
        users = con.execute(
            '''SELECT u.id_usuario,u.nombre,u.correo,u.estado,u.fecha_creacion,
                      r.nombre rol,r.id_rol
               FROM users u JOIN roles r ON r.id_rol=u.id_rol
               WHERE ?='' OR u.nombre LIKE ? OR u.correo LIKE ? OR r.nombre LIKE ?
               ORDER BY u.id_usuario DESC LIMIT 100''',
            (search, pattern, pattern, pattern),
        ).fetchall()
        roles = con.execute('SELECT id_rol,nombre,descripcion FROM roles ORDER BY id_rol').fetchall()
    return jsonify(ok=True, users=[dict(row) for row in users], roles=[dict(row) for row in roles])

@app.post('/api/admin/users')
@roles_required('administrador')
def admin_create_user():
    data = payload()
    name = str(data.get('nombre', '')).strip()
    email = str(data.get('correo', '')).strip().lower()
    password = str(data.get('password', ''))
    try:
        role_id = int(data.get('id_rol', 0))
    except (TypeError, ValueError):
        return jsonify(ok=False, message='El rol indicado no es válido.'), 400
    if len(name) < 2 or len(name) > 160 or '@' not in email or len(email) > 255 or len(password) < 8:
        return jsonify(ok=False, message='Revisa el nombre, correo y contraseña (mínimo 8 caracteres).'), 400
    with db() as con:
        if not con.execute('SELECT 1 FROM roles WHERE id_rol=?', (role_id,)).fetchone():
            return jsonify(ok=False, message='El rol indicado no existe.'), 400
        try:
            cursor = con.execute(
                'INSERT INTO users(nombre,correo,contrasena_hash,id_rol) VALUES(?,?,?,?)',
                (name, email, generate_password_hash(password), role_id),
            )
        except (sqlite3.IntegrityError, mysql.connector.IntegrityError):
            return jsonify(ok=False, message='Ya existe una cuenta con ese correo.'), 409
    return jsonify(ok=True, id_usuario=cursor.lastrowid)

@app.get('/api/users')
@roles_required('administrador')
def users():
    with db() as con: rows=[dict(x) for x in con.execute('''SELECT u.id_usuario,u.nombre,u.correo,u.estado,u.fecha_creacion,r.nombre rol,r.id_rol FROM users u JOIN roles r ON r.id_rol=u.id_rol ORDER BY u.id_usuario DESC''')]
    return jsonify(ok=True,users=rows)

@app.put('/api/users/<int:uid>/role')
@roles_required('administrador')
def change_role(uid):
    d=payload()
    try:
        rid=int(d.get('id_rol',0))
    except (TypeError,ValueError):
        return jsonify(ok=False,message='Rol inválido.'),400
    with db() as con:
        if not con.execute('SELECT 1 FROM roles WHERE id_rol=?',(rid,)).fetchone(): return jsonify(ok=False,message='Rol inexistente.'),400
        target=con.execute('SELECT id_rol,estado FROM users WHERE id_usuario=?',(uid,)).fetchone()
        if not target: return jsonify(ok=False,message='Usuario inexistente.'),404
        target_role=con.execute('SELECT nombre FROM roles WHERE id_rol=?',(target['id_rol'],)).fetchone()
        next_role=con.execute('SELECT nombre FROM roles WHERE id_rol=?',(rid,)).fetchone()
        if target_role['nombre']=='administrador' and next_role['nombre']!='administrador' and target['estado']=='activo' and active_admin_count(con)<=1:
            return jsonify(ok=False,message='No puedes quitar el último administrador activo.'),409
        con.execute('UPDATE users SET id_rol=? WHERE id_usuario=?',(rid,uid))
    return jsonify(ok=True)

@app.delete('/api/users/<int:uid>')
@roles_required('administrador')
def delete_user(uid):
    administrator=current_user()
    if administrator['id_usuario']==uid:
        return jsonify(ok=False,message='No puedes eliminar tu propia cuenta administradora desde aquí.'),409
    with db() as con:
        target=con.execute(
            '''SELECT u.id_usuario,u.estado,r.nombre rol FROM users u
               JOIN roles r ON r.id_rol=u.id_rol WHERE u.id_usuario=?''',
            (uid,),
        ).fetchone()
        if not target:
            return jsonify(ok=False,message='Usuario inexistente.'),404
        if target['rol']=='administrador' and target['estado']=='activo' and active_admin_count(con)<=1:
            return jsonify(ok=False,message='No puedes eliminar el último administrador activo.'),409
        con.execute('DELETE FROM users WHERE id_usuario=?',(uid,))
    return jsonify(ok=True)

@app.get('/api/projects')
@login_required
def projects():
    u=current_user()
    with db() as con:
        rows=con.execute('''SELECT DISTINCT p.*, u.nombre creador, (SELECT COUNT(*) FROM compositions c WHERE c.id_proyecto=p.id_proyecto) composiciones, (SELECT COUNT(*) FROM resources r WHERE r.id_proyecto=p.id_proyecto) recursos FROM projects p JOIN users u ON u.id_usuario=p.id_usuario_creador LEFT JOIN project_users pu ON pu.id_proyecto=p.id_proyecto AND pu.id_usuario=? WHERE p.id_usuario_creador=? OR pu.id_usuario=? ORDER BY p.fecha_actualizacion DESC''',(u['id_usuario'],u['id_usuario'],u['id_usuario'])).fetchall()
    return jsonify(ok=True,projects=[dict(r) for r in rows])

@app.post('/api/projects')
@login_required
def create_project():
    u=current_user(); d=payload(); name=str(d.get('nombre','')).strip()
    if not name or len(name)>120: return jsonify(ok=False,message='El nombre del proyecto debe tener entre 1 y 120 caracteres.'),400
    with db() as con:
        cur=con.execute('INSERT INTO projects(nombre,descripcion,id_usuario_creador) VALUES(?,?,?)',(name,str(d.get('descripcion','')).strip(),u['id_usuario']))
        pid=cur.lastrowid; con.execute('INSERT INTO project_users(id_proyecto,id_usuario,permiso) VALUES(?,?,?)',(pid,u['id_usuario'],'owner'))
    return jsonify(ok=True,project={'id_proyecto':pid})

@app.put('/api/projects/<int:pid>')
@login_required
def update_project(pid):
    u=current_user(); d=payload()
    name=str(d.get('nombre','')).strip()
    if not name or len(name)>120: return jsonify(ok=False,message='El nombre del proyecto debe tener entre 1 y 120 caracteres.'),400
    with db() as con:
        if not project_access(con,pid,u,True): return jsonify(ok=False,message='Sin permiso.'),403
        con.execute('UPDATE projects SET nombre=?,descripcion=?,estado=?,fecha_actualizacion=CURRENT_TIMESTAMP WHERE id_proyecto=?',(name,str(d.get('descripcion','')),str(d.get('estado','activo')),pid))
    return jsonify(ok=True)

@app.delete('/api/projects/<int:pid>')
@login_required
def delete_project(pid):
    u=current_user()
    with db() as con:
        row=con.execute('SELECT id_usuario_creador FROM projects WHERE id_proyecto=?',(pid,)).fetchone()
        if not row or (row['id_usuario_creador']!=u['id_usuario'] and u['rol']!='administrador'): return jsonify(ok=False,message='Solo el creador o administrador puede eliminarlo.'),403
        con.execute('DELETE FROM projects WHERE id_proyecto=?',(pid,))
    return jsonify(ok=True)

@app.post('/api/projects/<int:pid>/share')
@login_required
def share_project(pid):
    u=current_user(); d=payload(); email=str(d.get('correo','')).strip().lower(); perm=str(d.get('permiso','editor'))
    with db() as con:
        if not project_access(con,pid,u,True): return jsonify(ok=False,message='Sin permiso.'),403
        target=con.execute('SELECT id_usuario FROM users WHERE correo=?',(email,)).fetchone()
        if not target: return jsonify(ok=False,message='No existe un usuario con ese correo.'),404
        membership_sql = 'INSERT OR REPLACE INTO project_users(id_proyecto,id_usuario,permiso) VALUES(?,?,?)'
        if DB_BACKEND != 'sqlite':
            membership_sql = 'INSERT INTO project_users(id_proyecto,id_usuario,permiso) VALUES(?,?,?) ON DUPLICATE KEY UPDATE permiso=VALUES(permiso)'
        con.execute(membership_sql,(pid,target['id_usuario'],perm))
    return jsonify(ok=True)

@app.get('/api/projects/<int:pid>/detail')
@login_required
def project_detail(pid):
    u=current_user()
    with db() as con:
        if not project_access(con,pid,u): return jsonify(ok=False,message='Sin acceso.'),403
        p=con.execute('SELECT * FROM projects WHERE id_proyecto=?',(pid,)).fetchone()
        data={'project':dict(p),
              'resources':[dict(x) for x in con.execute('SELECT * FROM resources WHERE id_proyecto=? ORDER BY fecha_subida DESC',(pid,))],
              'compositions':[dict(x) for x in con.execute('SELECT * FROM compositions WHERE id_proyecto=? ORDER BY fecha_creacion DESC',(pid,))],
              'analyses':[dict(x) for x in con.execute('SELECT * FROM analyses WHERE id_proyecto=? ORDER BY fecha DESC',(pid,))],
              'tracking':[dict(x) for x in con.execute('SELECT * FROM tracking WHERE id_proyecto=? ORDER BY fecha DESC',(pid,))]}
    return jsonify(ok=True,**data)

@app.post('/api/projects/<int:pid>/resources')
@login_required
def add_resource(pid):
    u=current_user()
    with db() as con:
        if not project_access(con,pid,u,True): return jsonify(ok=False,message='Sin permiso.'),403
        name=str(request.form.get('nombre','')).strip(); desc=str(request.form.get('descripcion','')); typ=str(request.form.get('tipo','archivo'))
        f=request.files.get('archivo'); url=''
        if f and f.filename:
            ext=f.filename.rsplit('.',1)[-1].lower() if '.' in f.filename else ''
            if ext not in ALLOWED_UPLOADS: return jsonify(ok=False,message='Tipo de archivo no permitido.'),400
            safe=f'{datetime.utcnow().strftime("%Y%m%d%H%M%S")}_{secure_filename(f.filename)}'; f.save(UPLOADS/safe); url='/uploads/'+safe
        if not name: name=f.filename if f and f.filename else 'Recurso'
        cur=con.execute('INSERT INTO resources(tipo,nombre,url_archivo,descripcion,id_proyecto) VALUES(?,?,?,?,?)',(typ,name,url,desc,pid))
        touch_project(con,pid)
    return jsonify(ok=True,id_recurso=cur.lastrowid)

@app.delete('/api/resources/<int:rid>')
@login_required
def delete_resource(rid):
    u=current_user()
    with db() as con:
        r=con.execute('SELECT * FROM resources WHERE id_recurso=?',(rid,)).fetchone()
        if not r or not project_access(con,r['id_proyecto'],u,True): return jsonify(ok=False,message='Sin permiso.'),403
        con.execute('DELETE FROM resources WHERE id_recurso=?',(rid,))
    return jsonify(ok=True)

@app.post('/api/projects/<int:pid>/compositions')
@login_required
def add_composition(pid):
    u=current_user(); d=payload(); title=str(d.get('titulo','')).strip()
    with db() as con:
        if not project_access(con,pid,u,True): return jsonify(ok=False,message='Sin permiso.'),403
        if not title: return jsonify(ok=False,message='Título requerido.'),400
        cur=con.execute('INSERT INTO compositions(titulo,descripcion,instrumento,dificultad,genero,id_proyecto) VALUES(?,?,?,?,?,?)',(title,str(d.get('descripcion','')).strip(),str(d.get('instrumento','Piano')).strip() or 'Piano',str(d.get('dificultad','')).strip(),str(d.get('genero','')).strip(),pid)); touch_project(con,pid)
    return jsonify(ok=True,id_composicion=cur.lastrowid)

@app.put('/api/compositions/<int:cid>')
@login_required
def update_composition(cid):
    u=current_user(); d=payload()
    with db() as con:
        c=con.execute('SELECT * FROM compositions WHERE id_composicion=?',(cid,)).fetchone()
        if not c or not project_access(con,c['id_proyecto'],u,True): return jsonify(ok=False,message='Sin permiso.'),403
        title=str(d.get('titulo',c['titulo'])).strip()
        if not title: return jsonify(ok=False,message='Título requerido.'),400
        con.execute('UPDATE compositions SET titulo=?,descripcion=?,instrumento=?,dificultad=?,genero=? WHERE id_composicion=?',(title,str(d.get('descripcion',c['descripcion'])).strip(),str(d.get('instrumento',c['instrumento'])).strip(),str(d.get('dificultad',c['dificultad'])).strip(),str(d.get('genero',c['genero'])).strip(),cid)); touch_project(con,c['id_proyecto'])
    return jsonify(ok=True)

@app.get('/api/library')
@login_required
def library():
    u=current_user()
    with db() as con:
        rows=con.execute('''SELECT c.id_composicion,c.titulo,c.descripcion,c.instrumento,c.dificultad,c.genero,c.fecha_creacion,p.id_proyecto,p.nombre proyecto,p.id_usuario_creador creador_id,u.nombre compositor,
            (SELECT s.contenido_json FROM scores s WHERE s.id_composicion=c.id_composicion ORDER BY s.version DESC LIMIT 1) contenido_json,
            EXISTS(SELECT 1 FROM score_favorites f WHERE f.id_composicion=c.id_composicion AND f.id_usuario=?) favorita
            FROM compositions c JOIN projects p ON p.id_proyecto=c.id_proyecto JOIN users u ON u.id_usuario=p.id_usuario_creador
            LEFT JOIN project_users pu ON pu.id_proyecto=p.id_proyecto AND pu.id_usuario=?
            WHERE p.id_usuario_creador=? OR pu.id_usuario=? ORDER BY c.fecha_creacion DESC''',(u['id_usuario'],u['id_usuario'],u['id_usuario'],u['id_usuario'])).fetchall()
    return jsonify(ok=True,compositions=[dict(row) for row in rows])

@app.put('/api/compositions/<int:cid>/favorite')
@login_required
def set_score_favorite(cid):
    u=current_user(); d=payload()
    with db() as con:
        c=con.execute('SELECT id_proyecto FROM compositions WHERE id_composicion=?',(cid,)).fetchone()
        if not c or not project_access(con,c['id_proyecto'],u): return jsonify(ok=False,message='Sin acceso a esta composición.'),404
        if d.get('favorita'):
            con.execute('INSERT OR IGNORE INTO score_favorites(id_usuario,id_composicion) VALUES(?,?)',(u['id_usuario'],cid))
        else:
            con.execute('DELETE FROM score_favorites WHERE id_usuario=? AND id_composicion=?',(u['id_usuario'],cid))
    return jsonify(ok=True,favorita=bool(d.get('favorita')))

@app.delete('/api/compositions/<int:cid>')
@login_required
def delete_composition(cid):
    u=current_user()
    with db() as con:
        c=con.execute('SELECT * FROM compositions WHERE id_composicion=?',(cid,)).fetchone()
        if not c or not project_access(con,c['id_proyecto'],u,True): return jsonify(ok=False,message='Sin permiso.'),403
        con.execute('DELETE FROM compositions WHERE id_composicion=?',(cid,))
    return jsonify(ok=True)

@app.get('/api/compositions/<int:cid>/score')
@login_required
def get_score(cid):
    u=current_user()
    with db() as con:
        c=con.execute('SELECT * FROM compositions WHERE id_composicion=?',(cid,)).fetchone()
        if not c or not project_access(con,c['id_proyecto'],u): return jsonify(ok=False,message='Sin acceso.'),403
        s=con.execute('SELECT * FROM scores WHERE id_composicion=? ORDER BY version DESC LIMIT 1',(cid,)).fetchone()
    return jsonify(ok=True,score=dict(s) if s else None)

@app.post('/api/compositions/<int:cid>/score')
@login_required
def save_score(cid):
    u=current_user(); d=payload(); content=d.get('contenido',{})
    if not isinstance(content,dict) or not isinstance(content.get('notes',[]),list) or len(content.get('notes',[]))>2000:
        return jsonify(ok=False,message='La estructura de la partitura no es válida.'),400
    notes=content.get('notes',[])
    valid_pitches={f'{step}{acc}' for step in 'CDEFGAB' for acc in ('','#','b')}
    if any(not isinstance(n,dict) or n.get('name') not in valid_pitches or not isinstance(n.get('octave'),int) or not -1<=n['octave']<=9 or n.get('duration','q') not in {'w','h','q','8','16'} for n in notes):
        return jsonify(ok=False,message='La partitura contiene una nota o duración no válida.'),400
    try: tempo=int(content.get('tempo',80))
    except (TypeError,ValueError): return jsonify(ok=False,message='El tempo debe ser un número entre 30 y 300 BPM.'),400
    if not 30<=tempo<=300: return jsonify(ok=False,message='El tempo debe ser un número entre 30 y 300 BPM.'),400
    content['tempo']=tempo
    with db() as con:
        c=con.execute('SELECT * FROM compositions WHERE id_composicion=?',(cid,)).fetchone()
        if not c or not project_access(con,c['id_proyecto'],u,True): return jsonify(ok=False,message='Sin permiso.'),403
        last=con.execute('SELECT COALESCE(MAX(version),0) v FROM scores WHERE id_composicion=?',(cid,)).fetchone()['v']
        con.execute('INSERT INTO scores(formato,version,id_composicion,contenido_json) VALUES(?,?,?,?)',('lyrics-score',last+1,cid,json.dumps(content,ensure_ascii=False)))
    return jsonify(ok=True,version=last+1)

@app.post('/api/compositions/<int:cid>/recordings')
@login_required
def add_recording(cid):
    u=current_user(); f=request.files.get('audio'); duration=float(request.form.get('duracion',0) or 0)
    with db() as con:
        c=con.execute('SELECT * FROM compositions WHERE id_composicion=?',(cid,)).fetchone()
        if not c or not project_access(con,c['id_proyecto'],u,True): return jsonify(ok=False,message='Sin permiso.'),403
        if not f: return jsonify(ok=False,message='No se recibió audio.'),400
        safe=f'{datetime.utcnow().strftime("%Y%m%d%H%M%S%f")}_{secure_filename(f.filename or "grabacion.webm")}'; f.save(UPLOADS/safe)
        cur=con.execute('INSERT INTO recordings(archivo_audio,duracion,formato,id_composicion,id_usuario) VALUES(?,?,?,?,?)',(safe,duration,(f.filename.rsplit('.',1)[-1] if '.' in f.filename else 'webm'),cid,u['id_usuario']))
    return jsonify(ok=True,id_grabacion=cur.lastrowid,url='/uploads/'+safe)

@app.get('/api/compositions/<int:cid>/recordings')
@login_required
def recordings(cid):
    u=current_user()
    with db() as con:
        c=con.execute('SELECT * FROM compositions WHERE id_composicion=?',(cid,)).fetchone()
        if not c or not project_access(con,c['id_proyecto'],u): return jsonify(ok=False,message='Sin acceso.'),403
        rows=[dict(x) for x in con.execute('''SELECT r.*,u.nombre usuario FROM recordings r JOIN users u ON u.id_usuario=r.id_usuario WHERE r.id_composicion=? ORDER BY r.fecha DESC''',(cid,))]
    return jsonify(ok=True,recordings=rows)

@app.post('/api/projects/<int:pid>/analyses')
@login_required
def add_analysis(pid):
    u=current_user(); d=payload()
    with db() as con:
        if not project_access(con,pid,u,True): return jsonify(ok=False,message='Sin permiso.'),403
        cur=con.execute('INSERT INTO analyses(tipo,resultado,observaciones,id_grabacion,id_proyecto) VALUES(?,?,?,?,?)',(str(d.get('tipo','musical')),str(d.get('resultado','')),str(d.get('observaciones','')),d.get('id_grabacion') or None,pid))
        touch_project(con,pid)
    return jsonify(ok=True,id_analisis=cur.lastrowid)

@app.get('/api/activities')
@login_required
def activities():
    u=current_user()
    with db() as con:
        if u['rol'] in ('docente','mixto','administrador'):
            rows=con.execute('''SELECT a.*,u.nombre docente,(SELECT COUNT(*) FROM evaluations e WHERE e.id_actividad=a.id_actividad) evaluaciones FROM activities a JOIN users u ON u.id_usuario=a.id_docente ORDER BY a.fecha_creacion DESC''').fetchall()
        else:
            rows=con.execute('SELECT * FROM activities ORDER BY fecha_creacion DESC').fetchall()
    return jsonify(ok=True,activities=[dict(x) for x in rows])

@app.post('/api/activities')
@roles_required('docente','mixto','administrador')
def create_activity():
    u=current_user(); d=payload(); name=str(d.get('nombre','')).strip()
    if not name: return jsonify(ok=False,message='Nombre requerido.'),400
    with db() as con:
        cur=con.execute('INSERT INTO activities(nombre,descripcion,id_docente,id_proyecto) VALUES(?,?,?,?)',(name,str(d.get('descripcion','')),u['id_usuario'],d.get('id_proyecto') or None))
    return jsonify(ok=True,id_actividad=cur.lastrowid)

@app.post('/api/activities/<int:aid>/evaluations')
@roles_required('docente','mixto','administrador')
def create_evaluation(aid):
    d=payload(); title=str(d.get('titulo','')).strip()
    if not title: return jsonify(ok=False,message='Título requerido.'),400
    with db() as con:
        if not con.execute('SELECT 1 FROM activities WHERE id_actividad=?',(aid,)).fetchone(): return jsonify(ok=False,message='Actividad inexistente.'),404
        cur=con.execute('INSERT INTO evaluations(titulo,tipo,id_actividad) VALUES(?,?,?)',(title,str(d.get('tipo','formativa')),aid))
    return jsonify(ok=True,id_evaluacion=cur.lastrowid)

@app.post('/api/evaluations/<int:eid>/results')
@login_required
def submit_result(eid):
    u=current_user(); d=payload(); grade=d.get('calificacion')
    try: grade=float(grade) if grade is not None and grade!='' else None
    except ValueError: return jsonify(ok=False,message='Calificación inválida.'),400
    with db() as con:
        if not con.execute('SELECT 1 FROM evaluations WHERE id_evaluacion=?',(eid,)).fetchone(): return jsonify(ok=False,message='Evaluación inexistente.'),404
        result_sql = '''INSERT INTO evaluation_results(calificacion,observaciones,id_evaluacion,id_usuario) VALUES(?,?,?,?) ON CONFLICT(id_evaluacion,id_usuario) DO UPDATE SET calificacion=excluded.calificacion,observaciones=excluded.observaciones,fecha=CURRENT_TIMESTAMP'''
        if DB_BACKEND != 'sqlite':
            result_sql = '''INSERT INTO evaluation_results(calificacion,observaciones,id_evaluacion,id_usuario) VALUES(?,?,?,?) ON DUPLICATE KEY UPDATE calificacion=VALUES(calificacion),observaciones=VALUES(observaciones),fecha=CURRENT_TIMESTAMP'''
        con.execute(result_sql,(grade,str(d.get('observaciones','')),eid,u['id_usuario']))
    return jsonify(ok=True)

@app.get('/api/evaluations')
@login_required
def evaluations():
    u=current_user()
    with db() as con:
        rows=con.execute('''SELECT e.*,a.nombre actividad,(SELECT COUNT(*) FROM evaluation_results r WHERE r.id_evaluacion=e.id_evaluacion) respuestas FROM evaluations e JOIN activities a ON a.id_actividad=e.id_actividad ORDER BY e.fecha_creacion DESC''').fetchall()
    return jsonify(ok=True,evaluations=[dict(x) for x in rows])

@app.post('/api/projects/<int:pid>/tracking')
@login_required
def add_tracking(pid):
    u=current_user(); d=payload(); progress=max(0,min(100,int(d.get('progreso',0))))
    with db() as con:
        if not project_access(con,pid,u,True): return jsonify(ok=False,message='Sin permiso.'),403
        cur=con.execute('INSERT INTO tracking(progreso,comentarios,id_proyecto,id_usuario) VALUES(?,?,?,?)',(progress,str(d.get('comentarios','')),pid,u['id_usuario']))
    return jsonify(ok=True,id_seguimiento=cur.lastrowid)

@app.get('/api/stats')
@login_required
def stats():
    u=current_user()
    with db() as con:
        q=lambda sql,args=(): con.execute(sql,args).fetchone()[0]
        projects_count=q('SELECT COUNT(DISTINCT p.id_proyecto) FROM projects p LEFT JOIN project_users pu ON pu.id_proyecto=p.id_proyecto AND pu.id_usuario=? WHERE p.id_usuario_creador=? OR pu.id_usuario=?',(u['id_usuario'],u['id_usuario'],u['id_usuario']))
        comp=q('SELECT COUNT(*) FROM compositions c JOIN projects p ON p.id_proyecto=c.id_proyecto LEFT JOIN project_users pu ON pu.id_proyecto=p.id_proyecto AND pu.id_usuario=? WHERE p.id_usuario_creador=? OR pu.id_usuario=?',(u['id_usuario'],u['id_usuario'],u['id_usuario']))
        rec=q('SELECT COUNT(*) FROM recordings WHERE id_usuario=?',(u['id_usuario'],))
        analyses=q('SELECT COUNT(*) FROM analyses a JOIN projects p ON p.id_proyecto=a.id_proyecto LEFT JOIN project_users pu ON pu.id_proyecto=p.id_proyecto AND pu.id_usuario=? WHERE p.id_usuario_creador=? OR pu.id_usuario=?',(u['id_usuario'],u['id_usuario'],u['id_usuario']))
        activities_count=q('SELECT COUNT(*) FROM activities WHERE id_docente=?',(u['id_usuario'],))
    return jsonify(ok=True,stats={'proyectos':projects_count,'composiciones':comp,'grabaciones':rec,'analisis':analyses,'actividades':activities_count})

@app.get('/api/projects/<int:pid>/export')
@login_required
def export_project(pid):
    u=current_user()
    with db() as con:
        if not project_access(con,pid,u): return jsonify(ok=False,message='Sin acceso.'),403
        p=con.execute('SELECT * FROM projects WHERE id_proyecto=?',(pid,)).fetchone()
        out={'proyecto':dict(p), 'recursos':[dict(x) for x in con.execute('SELECT * FROM resources WHERE id_proyecto=?',(pid,))], 'composiciones':[]}
        for c in con.execute('SELECT * FROM compositions WHERE id_proyecto=?',(pid,)).fetchall():
            c=dict(c); c['partituras']=[dict(x) for x in con.execute('SELECT id_partitura,formato,version,fecha_creacion,contenido_json FROM scores WHERE id_composicion=?',(c['id_composicion'],))]; c['grabaciones']=[dict(x) for x in con.execute('SELECT id_grabacion,archivo_audio,duracion,formato,fecha,id_usuario FROM recordings WHERE id_composicion=?',(c['id_composicion'],))]; out['composiciones'].append(c)
    return app.response_class(json.dumps(out,ensure_ascii=False,indent=2),mimetype='application/json',headers={'Content-Disposition':f'attachment; filename=lyrics_proyecto_{pid}.json'})

@app.get('/uploads/<path:filename>')
@login_required
def uploaded(filename):
    u=current_user()
    with db() as con:
        recording=con.execute('''SELECT c.id_proyecto FROM recordings r JOIN compositions c ON c.id_composicion=r.id_composicion WHERE r.archivo_audio=?''',(filename,)).fetchone()
        resource=con.execute('SELECT id_proyecto FROM resources WHERE url_archivo=?',(f'/uploads/{filename}',)).fetchone()
        authorized=(recording and project_access(con,recording['id_proyecto'],u)) or (resource and project_access(con,resource['id_proyecto'],u))
    if not authorized: return jsonify(ok=False,message='Archivo no encontrado.'),404
    return send_from_directory(UPLOADS,filename,as_attachment=False)

@app.get('/api/health')
def health(): return jsonify(ok=True,app='Lyrics',status='running')

if __name__ == '__main__':
    app.run(host='127.0.0.1',port=5000,debug=True)
