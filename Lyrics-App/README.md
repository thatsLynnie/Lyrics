# Lyrics — Plataforma web musical

Lyrics is an existing Flask and SQLite application for musical projects, scores, recording and learning. It uses the bundled Lyrics image assets, VexFlow 4.2.3 for score notation, and browser audio APIs for recording and monophonic pitch estimation.

## Requirements

- Python 3.11 or later.
- Internet access for the VexFlow CDN, Google Fonts and the Bootstrap styles used by the landing page.
- A browser with `getUserMedia`, `MediaRecorder` and Web Audio support for recording. Microphone access requires `localhost` or HTTPS and user permission.

## Run on Windows

Open PowerShell in this directory and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:LYRICS_SECRET_KEY = 'replace-with-a-long-random-value'
python app.py
```

Open `http://127.0.0.1:5000`, choose **Registrarse**, then use the Dashboard.

For a persistent secret, set `LYRICS_SECRET_KEY` in the environment before starting the app. `.env.example` lists optional database and upload-directory settings; Flask does not load `.env` automatically.

The SQLite database defaults to `lyrics.db` in this folder, and uploaded audio defaults to `uploads/`. Override their locations with `LYRICS_DATABASE` and `LYRICS_UPLOADS`.

## Run tests

```powershell
python -m unittest discover -s tests -v
```

The tests use a temporary SQLite database and cover route delivery, registration, profile persistence, score persistence, library favorites and project access isolation.

## Implemented behavior

- Account registration, login and logout with Werkzeug password hashing.
- Project creation, editing, deletion and access control.
- Composition creation, VexFlow score rendering and versioned score persistence.
- Interactive score editing with five note durations, rests, rendered sharps/flats/naturals, ties between consecutive notes of the same pitch, dots, italic dynamics, accents, fermatas, repeats, text, chords, tempo and time-signature controls. Accidentals on selected notes also affect playback; ties are sustained during playback.
- Keyboard editing: the `?` control opens configurable shortcuts for note durations, inserting the next note, selection, note movement, deletion, undo/redo, saving and accidentals. Click **Cambiar** and press the desired key or combination; `Ctrl/Cmd`, `Alt` and `Shift` are supported. Shortcuts are saved in the browser, conflicts are rejected, **Quitar** clears a binding, **Escape** cancels capture, and `Tab` is reserved for navigation. By default, focus the score and press `Enter` to insert the next note at the same pitch and duration after the selected note (or at the end if nothing is selected). Other defaults include `1`–`5` for durations, arrow keys for moving notes, `Delete`/`Backspace` to remove the selection, `Ctrl/Cmd`+`Z` to undo, `Ctrl/Cmd`+`Shift`+`Z` or `Ctrl/Cmd`+`Y` to redo, and `Ctrl/Cmd`+`S` to save. `Ctrl/Cmd`+click still selects multiple notes for ties.
- Scores wrap into new staff systems as measures grow and are vertically scrollable; notes can be selected precisely or entered at a staff position.
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
