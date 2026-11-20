"""Genera la carpeta `dist/` que Netlify publica como sitio estático.

Lyrics tiene dos partes: el frontend (HTML/CSS/JS, va a Netlify) y el backend Flask + MySQL
(NO puede ejecutarse en Netlify; debe estar en un servicio que corra Python). Netlify reenvía
/api/* y /uploads/* al backend con un "rewrite" de estado 200, de modo que el navegador solo
habla con el dominio de Netlify y las cookies de sesión siguen siendo del mismo origen.

Las redirecciones de netlify.toml no admiten variables de entorno, así que el archivo
`_redirects` se genera aquí a partir de LYRICS_BACKEND_URL.

Uso:  LYRICS_BACKEND_URL=https://mi-backend.example.com python scripts/build_netlify.py
"""
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist'
LANDING = ROOT / 'Lyrics_F'

# Lista blanca: solo se publica lo que el navegador necesita. Nunca .env, bases de datos ni código del servidor.
FRONTEND_FILES = [
    'dashboard.html', 'dashboard.css', 'dashboard.js',
    'ai.css', 'ai.js', 'landing.js',
    'contacto.html', 'contacto.css', 'contact.js',
]


def backend_url():
    url = os.environ.get('LYRICS_BACKEND_URL', '').strip().rstrip('/')
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.netloc:
        sys.exit(
            'Define LYRICS_BACKEND_URL con la dirección HTTPS del backend Flask '
            '(por ejemplo https://lyrics-api.onrender.com), sin barra final.'
        )
    return url


def main():
    backend = backend_url()
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    # La landing (index.html, estilos.css, img/...) va en la raíz del sitio, igual que la sirve Flask.
    if LANDING.is_dir():
        shutil.copytree(LANDING, DIST, dirs_exist_ok=True)
    else:
        print(f'Aviso: no existe {LANDING.name}/; el sitio se publicará sin la landing.')

    for name in FRONTEND_FILES:
        source = ROOT / name
        if not source.is_file():
            sys.exit(f'Falta el archivo {name}; no se puede construir el sitio.')
        shutil.copy2(source, DIST / name)

    # El primer patrón que coincide gana. Las páginas sin extensión replican las rutas de Flask.
    redirects = [
        f'/api/*      {backend}/api/:splat      200',
        f'/uploads/*  {backend}/uploads/:splat  200',
        '/dashboard   /dashboard.html           200',
        '/contacto    /contacto.html            200',
    ]
    (DIST / '_redirects').write_text('\n'.join(redirects) + '\n', encoding='utf-8')
    print(f'Sitio generado en {DIST} (backend: {backend})')


if __name__ == '__main__':
    main()
