# Lyrics — guía para agentes de código (OpenCode y similares)

Plataforma web musical en español: editor de partituras (VexFlow), grabación, biblioteca, módulo educativo, IA musical, contacto y panel de administración.

## Estructura

| Ruta | Qué es |
|---|---|
| `app.py` | Backend Flask: rutas `/api/*`, sesión, roles, panel admin, contacto, errores JSON |
| `ai_service.py` | Proveedores de IA (OpenAI, Gemini, local), prompt personalizado (`build_system_prompt`) |
| `dashboard.html/.js/.css` | App autenticada (vanilla JS, sin build) |
| `ai.js` / `ai.css` | Pantalla de IA musical |
| `contacto.html`, `contact.js`, `contacto.css`, `contact-snippet.html` | Formulario de contacto |
| `landing.js` | Login y registro de la landing (`Lyrics_F/`, no incluida en todos los ZIP) |
| `schema.sql` | Esquema MySQL (backend real) |
| `scripts/build_netlify.py`, `netlify.toml` | Construcción del frontend para Netlify |
| `tests/` | Pruebas `unittest` sobre SQLite temporal |

## Comandos

```bash
pip install -r requirements.txt
python app.py                                  # desarrollo en http://127.0.0.1:5000
python -m unittest discover -s tests -v        # pruebas
LYRICS_BACKEND_URL=https://... python scripts/build_netlify.py   # genera dist/ para Netlify
```

## Reglas del proyecto

- Interfaz, mensajes de error y comentarios en **español**. Identidad: vino `#832A41`, crema `#FEFCEF`, tipografía Alan Sans.
- Toda ruta `/api/` responde JSON `{ok, message}`; los errores deben ser claros y accionables, nunca trazas.
- Toda acción asíncrona de la interfaz necesita estado de carga (botón deshabilitado + texto) y manejo de error visible.
- Las rutas de administración usan `@roles_required('administrador')`; no basta con ocultar el menú.
- Cada consulta SQL debe funcionar en SQLite **y** MySQL (`?` como marcador; el adaptador lo traduce). Cualquier tabla nueva va en `SCHEMA` (SQLite) y en `schema.sql` (MySQL).
- Las claves de IA solo viven en el servidor (`.env`). Nunca en el navegador ni en commits.
- `dashboard.js` y `ai.js` están escritos en estilo compacto; conserva ese estilo al editarlos y verifica con `node --check`.
- Los archivos del repositorio usan finales de línea CRLF; respétalos.
- No inventes funciones: la IA actual es solo texto (sin OMR, audio ni exportación).
