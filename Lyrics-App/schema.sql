CREATE DATABASE IF NOT EXISTS lyrics
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE lyrics;

CREATE TABLE IF NOT EXISTS roles (
  id_rol INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(80) NOT NULL UNIQUE,
  descripcion VARCHAR(1000)
);
CREATE TABLE IF NOT EXISTS users (
  id_usuario INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(160) NOT NULL,
  correo VARCHAR(255) NOT NULL UNIQUE,
  contrasena_hash VARCHAR(255) NOT NULL,
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  estado VARCHAR(32) NOT NULL DEFAULT 'activo',
  biografia VARCHAR(2000) NOT NULL DEFAULT '',
  pais VARCHAR(100) NOT NULL DEFAULT '',
  id_rol INT NOT NULL,
  FOREIGN KEY (id_rol) REFERENCES roles(id_rol)
);
CREATE TABLE IF NOT EXISTS projects (
  id_proyecto INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(200) NOT NULL,
  descripcion VARCHAR(2000) DEFAULT '',
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  estado VARCHAR(32) NOT NULL DEFAULT 'activo',
  id_usuario_creador INT NOT NULL,
  FOREIGN KEY (id_usuario_creador) REFERENCES users(id_usuario) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS project_users (
  id_proyecto INT NOT NULL,
  id_usuario INT NOT NULL,
  permiso VARCHAR(32) NOT NULL DEFAULT 'editor',
  fecha_asignacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_proyecto,id_usuario),
  FOREIGN KEY (id_proyecto) REFERENCES projects(id_proyecto) ON DELETE CASCADE,
  FOREIGN KEY (id_usuario) REFERENCES users(id_usuario) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS resources (
  id_recurso INT AUTO_INCREMENT PRIMARY KEY,
  tipo VARCHAR(80) NOT NULL,
  nombre VARCHAR(255) NOT NULL,
  url_archivo VARCHAR(512),
  descripcion VARCHAR(2000) DEFAULT '',
  fecha_subida TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_proyecto INT NOT NULL,
  FOREIGN KEY (id_proyecto) REFERENCES projects(id_proyecto) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS compositions (
  id_composicion INT AUTO_INCREMENT PRIMARY KEY,
  titulo VARCHAR(255) NOT NULL,
  descripcion VARCHAR(2000) DEFAULT '',
  instrumento VARCHAR(80) NOT NULL DEFAULT 'Piano',
  dificultad VARCHAR(40) NOT NULL DEFAULT '',
  genero VARCHAR(80) NOT NULL DEFAULT '',
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_proyecto INT NOT NULL,
  FOREIGN KEY (id_proyecto) REFERENCES projects(id_proyecto) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS score_favorites (
  id_usuario INT NOT NULL,
  id_composicion INT NOT NULL,
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_usuario,id_composicion),
  FOREIGN KEY (id_usuario) REFERENCES users(id_usuario) ON DELETE CASCADE,
  FOREIGN KEY (id_composicion) REFERENCES compositions(id_composicion) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS scores (
  id_partitura INT AUTO_INCREMENT PRIMARY KEY,
  formato VARCHAR(80) NOT NULL DEFAULT 'lyrics-score',
  url_archivo VARCHAR(512),
  version INT NOT NULL DEFAULT 1,
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_composicion INT NOT NULL,
  contenido_json LONGTEXT NOT NULL,
  FOREIGN KEY (id_composicion) REFERENCES compositions(id_composicion) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS recordings (
  id_grabacion INT AUTO_INCREMENT PRIMARY KEY,
  archivo_audio VARCHAR(255) NOT NULL,
  duracion DOUBLE DEFAULT 0,
  formato VARCHAR(32) DEFAULT 'webm',
  fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_composicion INT NOT NULL,
  id_usuario INT NOT NULL,
  FOREIGN KEY (id_composicion) REFERENCES compositions(id_composicion) ON DELETE CASCADE,
  FOREIGN KEY (id_usuario) REFERENCES users(id_usuario) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS analyses (
  id_analisis INT AUTO_INCREMENT PRIMARY KEY,
  tipo VARCHAR(80) NOT NULL,
  resultado LONGTEXT NOT NULL,
  observaciones VARCHAR(2000) DEFAULT '',
  fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_grabacion INT,
  id_proyecto INT NOT NULL,
  FOREIGN KEY (id_grabacion) REFERENCES recordings(id_grabacion) ON DELETE SET NULL,
  FOREIGN KEY (id_proyecto) REFERENCES projects(id_proyecto) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS activities (
  id_actividad INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(255) NOT NULL,
  descripcion VARCHAR(2000) DEFAULT '',
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_docente INT NOT NULL,
  id_proyecto INT,
  FOREIGN KEY (id_docente) REFERENCES users(id_usuario) ON DELETE CASCADE,
  FOREIGN KEY (id_proyecto) REFERENCES projects(id_proyecto) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS evaluations (
  id_evaluacion INT AUTO_INCREMENT PRIMARY KEY,
  titulo VARCHAR(255) NOT NULL,
  tipo VARCHAR(80) NOT NULL DEFAULT 'formativa',
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_actividad INT NOT NULL,
  FOREIGN KEY (id_actividad) REFERENCES activities(id_actividad) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS evaluation_results (
  id_resultado INT AUTO_INCREMENT PRIMARY KEY,
  calificacion DOUBLE,
  observaciones VARCHAR(2000) DEFAULT '',
  fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_evaluacion INT NOT NULL,
  id_usuario INT NOT NULL,
  UNIQUE(id_evaluacion,id_usuario),
  FOREIGN KEY (id_evaluacion) REFERENCES evaluations(id_evaluacion) ON DELETE CASCADE,
  FOREIGN KEY (id_usuario) REFERENCES users(id_usuario) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS tracking (
  id_seguimiento INT AUTO_INCREMENT PRIMARY KEY,
  progreso INT NOT NULL DEFAULT 0,
  comentarios VARCHAR(2000) DEFAULT '',
  fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_proyecto INT NOT NULL,
  id_usuario INT NOT NULL,
  FOREIGN KEY (id_proyecto) REFERENCES projects(id_proyecto) ON DELETE CASCADE,
  FOREIGN KEY (id_usuario) REFERENCES users(id_usuario) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS ai_conversations (
  id_conversacion INT AUTO_INCREMENT PRIMARY KEY,
  titulo VARCHAR(100) NOT NULL DEFAULT 'Nueva conversación',
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_usuario INT NOT NULL,
  FOREIGN KEY (id_usuario) REFERENCES users(id_usuario) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS ai_messages (
  id_mensaje INT AUTO_INCREMENT PRIMARY KEY,
  rol VARCHAR(16) NOT NULL,
  contenido LONGTEXT NOT NULL,
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  id_conversacion INT NOT NULL,
  FOREIGN KEY (id_conversacion) REFERENCES ai_conversations(id_conversacion) ON DELETE CASCADE
);
