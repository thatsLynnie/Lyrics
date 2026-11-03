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

## Database administration

The in-app **Administración** section is shown only to users with the administrator role. It can search and page through records, and create, edit or delete records in the application data tables. User accounts have a separate management view for creating accounts, assigning roles and deleting accounts. Password hashes are never returned or displayed, and roles can only be assigned from the built-in role list. Deleting users or parent records can cascade to related data.

To grant the initial administrator role to an already registered account, stop the app, run `python promote_admin.py` from this folder, and enter that account's email. The script immediately changes the role if the account exists. Start the app again and sign in; the **Administración** section will appear. Only promote an account that belongs to you.

phpMyAdmin remains available for full database-level maintenance. Select the `lyrics` database in its left navigation to inspect tables and rows. The application database user has access only to `lyrics`; use a MySQL administrator account for creating database users or changing server-level permissions. Back up the database before bulk edits or deletions.

## Run tests

```powershell
python -m unittest discover -s tests -v
```

The tests use a temporary SQLite database and cover route delivery, registration, profile persistence, score persistence, library favorites and project access isolation. The application runtime uses MySQL.

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

## Known limitations

- The supplied workspace contains no original mockup screenshots. The available image files are product illustrations, so pixel-level comparison to the referenced mockups was not possible.
- Pitch estimation is a basic autocorrelation estimate for monophonic input; it is not polyphonic transcription and should not be treated as a complete audio-to-score system.
- The score editor supports a single treble staff and basic notation. Professional engraving, multiple independent parts/voices and advanced score layout are not implemented.
- Instrument selection does not provide instrument-specific sound. Educational lesson/progress workflows and PDF/MIDI/MusicXML interoperability still need broader compatibility validation.
- Audio input-device selection and capture settings depend on browser capabilities and are not yet fully wired to the recording stream.
- VexFlow is loaded from jsDelivr, so score notation needs a network connection.

Do not expose the development server publicly. Use a production WSGI server, a stable secret key, HTTPS, and deployment-specific upload and database locations before deployment.
