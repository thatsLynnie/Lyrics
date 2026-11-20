# Lyrics — Plataforma web musical

Lyrics is a Flask and MySQL application for musical projects, scores, recording and learning. It uses the bundled Lyrics image assets, VexFlow 4.2.3 for score notation, and browser audio APIs for recording and monophonic pitch estimation.

## Requirements

- Python 3.11 or later.
- MySQL 8.0 or later, with an empty database named `lyrics` created before first run.
- Internet access for the VexFlow CDN, Google Fonts and the Bootstrap styles used by the landing page.
- A browser with `getUserMedia`, `MediaRecorder` and Web Audio support for recording. Microphone access requires `localhost` or HTTPS and user permission.

## Run on Windows

Install the Python dependencies and create `.env` from the example:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Create the database and a dedicated local application user. Open `setup_mysql.sql` in phpMyAdmin or MySQL Workbench and execute the script while connected as a MySQL administrator. Then, from PowerShell in this folder, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\configurar_mysql.ps1
```

When prompted, paste the generated 48-character hexadecimal password. PowerShell hides it, writes it to `.env`, and starts the app. The SQL script grants the application user permissions only on the `lyrics` database. Open `http://127.0.0.1:5000`, choose **Registrarse**, then use the Dashboard.

Update `.env` with the host, port, user, password, database and a persistent secret key for your MySQL server. The app loads this file automatically; keep `.env` private and do not commit it. The database user needs permission to create tables and alter them for application migrations. A database-editor extension connects only its own editor view; the Flask app uses the credentials in `.env` through `mysql-connector-python`.

MySQL is the default backend. SQLite is retained only for the automated test suite by setting `LYRICS_DB_BACKEND=sqlite`; uploaded audio defaults to `uploads/` and can be relocated with `LYRICS_UPLOADS`.

The registration form asks for one username, an email and a password. On successful registration the app creates the session and opens the Dashboard, where the profile is populated from the account stored in MySQL.

## Musical AI assistant

The **IA Musical** workspace is available to every signed-in role and stores text conversations privately per account in the application database. It can use OpenAI or Google Gemini; add `OPENAI_API_KEY` and/or `GEMINI_API_KEY` to the private `.env` file on the server. Optionally configure `OPENAI_MODEL` (default: `gpt-4o-mini`), `GEMINI_MODEL` (default: `gemini-3.8-flash`), `LYRICS_AI_ASSISTANT_NAME` and `LYRICS_AI_DAILY_LIMIT` (default: 40 completed responses per user in 24 hours). The selector also offers an offline local helper. If a selected online provider fails, Lyrics tries the other configured provider, then uses the local helper. That helper provides deterministic guidance for common music topics such as scales, chords, rhythm and composition; it is not a generative AI model and labels its responses accordingly. Both API keys stay on the Flask server and must never be added to browser code or committed. Messages sent to online providers are processed by those providers, so do not include personal student information.

The workspace includes searchable conversation history, copyable formatted answers, keyboard shortcuts, a responsive layout, an optional welcome arpeggio, browser-based speech dictation, and optional spoken answers. Dictation is handled by the browser's speech-recognition service; only the recognized text is sent to the selected provider when the user explicitly submits it. Voice support depends on the browser and its microphone permissions. This first phase supports musical explanations and text drafts of educational and composition ideas. It does not yet accept or analyze score files, perform OMR, validate music automatically, render or play generated notation, or export AI resources. Drafts should be reviewed by the user. The SQLite and MySQL schemas create private conversation storage automatically.

### AI personalization

Each reply is tailored per account. The server builds the system prompt from the signed-in user's **role** (teacher, composer, mixed, administrator), their first name and a **musical level** (beginner, intermediate, advanced) chosen in the *Nivel* selector of the chat header and stored in `ai_preferences`. The suggested prompts also change with the role. The base prompt that states the assistant's limits is always kept. Only the first name, role and level are sent to the provider, never the email or project data. See `build_system_prompt` in `ai_service.py`.

## Contact form

Public page at `/contacto` (`contacto.html`, `contacto.css`, `contact.js`), and a reusable block in `contact-snippet.html` for the landing page: paste the `<section>` before the footer, add `<link rel="stylesheet" href="/contacto.css">` in `<head>` and `<script src="/contact.js"></script>` before `</body>`.

`POST /api/contact` validates every field on the server, saves the message in `contact_messages` and answers with per-field errors (400), a rate-limit message (429, 3 messages per 10 minutes per IP) or success. A hidden honeypot field discards simple bots. Administrators read and manage messages in **Administración → Mensajes de contacto** (change `estado` to `leido` or `respondido`). The page shows a sending state, per-field errors and clear network/server error messages.

## Database administration

The in-app **Administración** section is shown only to users with the administrator role. It can search and page through records, and create, edit or delete records in the application data tables. User accounts have a separate management view for creating accounts, assigning roles and deleting accounts. Password hashes are never returned or displayed, and roles can only be assigned from the built-in role list. Deleting users or parent records can cascade to related data.

To grant the initial administrator role to an already registered account, stop the app, run `python promote_admin.py` from this folder, and enter that account's email. The script immediately changes the role if the account exists. Start the app again and sign in; the **Administración** section will appear. Only promote an account that belongs to you.

On hosting where you cannot run that script, set `LYRICS_ADMIN_EMAIL` and `LYRICS_ADMIN_PASSWORD` (12+ characters) in the server environment: the account is created on startup only if the email does not exist, and an existing account is never modified.

### Administrator authentication

Every `/api/admin/*` and user-management route is protected server-side by the `administrador` role (hiding the menu item is only cosmetic). Logins are limited to 5 failed attempts per IP and email every 15 minutes, a successful login starts a fresh session, and session cookies are `HttpOnly`, `SameSite=Lax` and `Secure` when `LYRICS_ENV=production`. Run `python app.py` for local development; `LYRICS_DEBUG=1` enables the debugger and is ignored in production. Unexpected API errors return a clear JSON message and are logged on the server without leaking details.

## Deployment (Netlify + Flask backend)

Netlify hosts static files and functions; it cannot run this Flask + MySQL backend. The supported setup is split in two:

1. **Backend**: deploy Flask and MySQL on a service that runs Python (for example Render, Railway or PythonAnywhere), using `gunicorn app:app`. Set `LYRICS_ENV=production`, a fixed `LYRICS_SECRET_KEY`, the MySQL variables, the AI keys, `LYRICS_TRUST_PROXY=1`, `LYRICS_AI_TIMEOUT=20` and optionally `LYRICS_ADMIN_EMAIL`/`LYRICS_ADMIN_PASSWORD`.
2. **Frontend on Netlify**: connect the repository and set the environment variable `LYRICS_BACKEND_URL` to the backend's HTTPS address. `netlify.toml` runs `scripts/build_netlify.py`, which publishes only the frontend files (plus `Lyrics_F/` when present) to `dist/` and generates `_redirects`, so `/api/*` and `/uploads/*` are proxied to the backend and the browser sees a single origin.

Things to know: Netlify proxied requests time out after 26 seconds ([docs](https://docs.netlify.com/manage/routing/redirects/rewrites-proxies)), hence `LYRICS_AI_TIMEOUT=20`; the first deployment should confirm that the session cookie survives the proxy by logging in on the Netlify domain; large audio uploads go through the same proxy and should be tested.

## Working with OpenCode

`AGENTS.md` describes the project layout, commands and conventions so that OpenCode (or any coding agent) can work on the repository safely.

phpMyAdmin remains available for full database-level maintenance. Select the `lyrics` database in its left navigation to inspect tables and rows. The application database user has access only to `lyrics`; use a MySQL administrator account for creating database users or changing server-level permissions. Back up the database before bulk edits or deletions.

## Run tests

```powershell
python -m unittest discover -s tests -v
```

The tests use a temporary SQLite database and cover route delivery, registration, profile persistence, score persistence, library favorites, project access isolation, and authenticated AI conversations across roles. The application runtime uses MySQL.

## Implemented behavior

- Account registration, login and logout with Werkzeug password hashing.
- Project creation, editing, deletion and access control.
- Composition creation, VexFlow score rendering and versioned score persistence.
- Interactive score editing with five note durations, rests, rendered sharps/flats/naturals, ties between consecutive notes of the same pitch, dots, italic dynamics, accents, fermatas, repeats, text, chords, tempo and time-signature controls. Tresillos and seisillos can be entered or applied to any selected figure duration. Eighth and sixteenth notes, including mixed rhythms, can be grouped manually or beamed automatically. Select a note and hold `Delete` or `Backspace` to remove notes sequentially; a held-key deletion is a single undo step. Crescendo and diminuendo can be applied across a selected range. Accidentals on selected notes also affect playback; ties are sustained during playback.
- Keyboard editing: the `?` control opens configurable shortcuts for note durations, inserting the next note, selection, note movement, deletion, undo/redo, saving, accidentals, tuplets, hairpins and manual beaming. The left-side **Acciones rápidas** palette lets users choose and reorder quick actions; its configuration and shortcuts are saved in the browser. Click **Cambiar** and press the desired key or combination; `Ctrl/Cmd`, `Alt` and `Shift` are supported. Shortcut conflicts are rejected, **Quitar** clears a binding, **Escape** cancels capture, and `Tab` is reserved for navigation. By default, focus the score and press `Enter` to insert the next note at the same pitch and duration after the selected note (or at the end if nothing is selected). Other defaults include `1`–`5` for durations, arrow keys for moving notes, `Delete`/`Backspace` for sequential deletion, `Ctrl/Cmd`+`Z` to undo, `Ctrl/Cmd`+`Shift`+`Z` or `Ctrl/Cmd`+`Y` to redo, and `Ctrl/Cmd`+`S` to save. `Ctrl/Cmd`+click selects multiple notes for ties and dynamics.
- Scores remain on one continuous horizontal staff as measures grow and are horizontally scrollable; notes can be selected precisely or entered at a staff position.
- Basic monophonic Web Audio playback at the score tempo, with optional metronome and volume control.
- Recording upload and playback, stored recording history, download of the current take, and monophonic note estimation.
- Adding detected or manually entered notes to a composition score.
- A score library drawn from accessible project compositions with search, metadata filters and user favorites.
- Persistent profile name, biography and country.
- Musical assistant for every signed-in role, with OpenAI-backed text conversations, per-user history, browser voice controls, and server-side API-key handling.

## Known limitations

- The supplied workspace contains no original mockup screenshots. The available image files are product illustrations, so pixel-level comparison to the referenced mockups was not possible.
- Pitch estimation is a basic autocorrelation estimate for monophonic input; it is not polyphonic transcription and should not be treated as a complete audio-to-score system.
- The score editor supports a single treble staff and basic notation. Professional engraving, multiple independent parts/voices and advanced score layout are not implemented.
- Instrument selection does not provide instrument-specific sound. Educational lesson/progress workflows and PDF/MIDI/MusicXML interoperability still need broader compatibility validation.
- The musical AI is currently text-only. OMR, score generation and validation, audio playback, and export are not integrated.
- Audio input-device selection and capture settings depend on browser capabilities and are not yet fully wired to the recording stream.
- VexFlow is loaded from jsDelivr, so score notation needs a network connection.

Do not expose the development server publicly. Use a production WSGI server, a stable secret key, HTTPS, and deployment-specific upload and database locations before deployment.
