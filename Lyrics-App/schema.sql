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
  fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_proyecto INTEGER NOT NULL,
  FOREIGN KEY (id_proyecto) REFERENCES projects(id_proyecto) ON DELETE CASCADE
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
