from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3, os, json, csv, io

BASE = Path(__file__).resolve().parent
DB = Path(os.environ.get('LYRICS_DATABASE', BASE / 'lyrics.db')).expanduser().resolve()
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
'''

ROLE_DATA = [
 ('administrador','Control y manejo de la plataforma en general.'),
 ('docente','Creación de actividades, evaluaciones y seguimiento académico.'),
 ('compositor','Composición, grabación, organización y análisis musical.'),
 ('mixto','Funciones de docente y compositor.')
]

@contextmanager
def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with db() as con:
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
        for name, desc in ROLE_DATA:
            con.execute('INSERT OR IGNORE INTO roles(nombre,descripcion) VALUES (?,?)',(name,desc))

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
def home(): return send_from_directory(BASE, 'index.html')

@app.get('/dashboard')
def dashboard():
    return send_from_directory(BASE, 'dashboard.html')

@app.get('/dashboard.css')
def dashboard_styles():
    return send_from_directory(BASE, 'dashboard.css')

@app.get('/dashboard.js')
def dashboard_script():
    return send_from_directory(BASE, 'dashboard.js')

@app.get('/landing.js')
def landing_script():
    return send_from_directory(BASE, 'landing.js')

@app.get('/estilo.css')
def landing_styles():
    return send_from_directory(BASE, 'estilo.css')

@app.get('/img/<path:filename>')
def image_asset(filename):
    return send_from_directory(ASSETS, filename)

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
        except sqlite3.IntegrityError: return jsonify(ok=False,message='Ya existe una cuenta con ese correo.'),409
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

@app.get('/api/users')
@roles_required('administrador')
def users():
    with db() as con: rows=[dict(x) for x in con.execute('''SELECT u.id_usuario,u.nombre,u.correo,u.estado,u.fecha_creacion,r.nombre rol,r.id_rol FROM users u JOIN roles r ON r.id_rol=u.id_rol ORDER BY u.id_usuario DESC''')]
    return jsonify(ok=True,users=rows)

@app.put('/api/users/<int:uid>/role')
@roles_required('administrador')
def change_role(uid):
    d=payload(); rid=int(d.get('id_rol',0))
    with db() as con:
        if not con.execute('SELECT 1 FROM roles WHERE id_rol=?',(rid,)).fetchone(): return jsonify(ok=False,message='Rol inexistente.'),400
        con.execute('UPDATE users SET id_rol=? WHERE id_usuario=?',(rid,uid))
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
        con.execute('INSERT OR REPLACE INTO project_users(id_proyecto,id_usuario,permiso) VALUES(?,?,?)',(pid,target['id_usuario'],perm))
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
        con.execute('''INSERT INTO evaluation_results(calificacion,observaciones,id_evaluacion,id_usuario) VALUES(?,?,?,?) ON CONFLICT(id_evaluacion,id_usuario) DO UPDATE SET calificacion=excluded.calificacion,observaciones=excluded.observaciones,fecha=CURRENT_TIMESTAMP''',(grade,str(d.get('observaciones','')),eid,u['id_usuario']))
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

init_db()
if __name__ == '__main__':
    app.run(host='127.0.0.1',port=5000,debug=True)
