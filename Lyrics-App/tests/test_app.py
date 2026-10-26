import json
import tempfile
import unittest
from pathlib import Path

import app as lyrics


class LyricsAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_db = lyrics.DB
        self.previous_uploads = lyrics.UPLOADS
        lyrics.DB = Path(self.temp_dir.name) / "lyrics.db"
        lyrics.UPLOADS = Path(self.temp_dir.name) / "uploads"
        lyrics.UPLOADS.mkdir()
        lyrics.init_db()
        lyrics.app.config.update(TESTING=True, SECRET_KEY="test-session-key")
        self.client = lyrics.app.test_client()

    def tearDown(self):
        lyrics.DB = self.previous_db
        lyrics.UPLOADS = self.previous_uploads
        self.temp_dir.cleanup()

    def register(self, client, email):
        return client.post(
            "/api/register",
            json={"name": "Compositora Test", "email": email, "password": "password123"},
        )

    def test_app_pages_and_public_assets_are_served(self):
        for path in ("/", "/dashboard", "/dashboard.css", "/dashboard.js", "/img/Logo2.png"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            response.close()
        self.assertEqual(self.client.get("/app.py").status_code, 404)

    def test_registration_profile_score_library_and_access_boundaries(self):
        response = self.register(self.client, "uno@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("contrasena_hash", self.client.get("/api/me").json["user"])

        profile = self.client.put(
            "/api/profile",
            json={"nombre": "Compositora Uno", "biografia": "Pianista", "pais": "Colombia"},
        )
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json["user"]["biografia"], "Pianista")

        project = self.client.post(
            "/api/projects", json={"nombre": "Suite", "descripcion": "Borrador"}
        ).json["project"]["id_proyecto"]
        composition = self.client.post(
            f"/api/projects/{project}/compositions",
            json={"titulo": "Tema principal", "instrumento": "Piano"},
        ).json["id_composicion"]
        score = {
            "notes": [
                {
                    "name": "C#",
                    "octave": 4,
                    "duration": "q",
                    "dotted": True,
                    "accent": True,
                    "accidental": "#",
                    "dynamic": "mf",
                },
                {"name": "C#", "octave": 4, "duration": "q", "accidental": "#"},
                {"name": "Bb", "octave": 4, "duration": "8", "rest": True},
                {"name": "B", "octave": 4, "duration": "q", "accidental": "n"},
            ],
            "ties": [[0, 1]],
            "meter": {"numerator": 3, "denominator": 4},
            "tempo": 96,
        }
        self.assertEqual(
            self.client.post(
                f"/api/compositions/{composition}/score", json={"contenido": score}
            ).status_code,
            200,
        )
        loaded_score = self.client.get(f"/api/compositions/{composition}/score").json["score"]
        self.assertEqual(json.loads(loaded_score["contenido_json"]), score)

        self.assertEqual(
            self.client.put(
                f"/api/compositions/{composition}/favorite", json={"favorita": True}
            ).status_code,
            200,
        )
        library = self.client.get("/api/library").json["compositions"]
        self.assertEqual(len(library), 1)
        self.assertTrue(library[0]["favorita"])

        other_user = lyrics.app.test_client()
        self.assertEqual(self.register(other_user, "dos@example.com").status_code, 200)
        self.assertEqual(other_user.get(f"/api/projects/{project}/detail").status_code, 403)
        self.assertEqual(other_user.get("/api/library").json["compositions"], [])


if __name__ == "__main__":
    unittest.main()
