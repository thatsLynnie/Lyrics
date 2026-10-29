import json
import tempfile
import unittest
from pathlib import Path

import app as lyrics


class LyricsAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_db = lyrics.DB
        self.previous_backend = lyrics.DB_BACKEND
        self.previous_uploads = lyrics.UPLOADS
        lyrics.DB_BACKEND = "sqlite"
        lyrics.DB = Path(self.temp_dir.name) / "lyrics.db"
        lyrics.DB_INITIALIZED = False
        lyrics.UPLOADS = Path(self.temp_dir.name) / "uploads"
        lyrics.UPLOADS.mkdir()
        lyrics.init_db()
        lyrics.app.config.update(TESTING=True, SECRET_KEY="test-session-key")
        self.client = lyrics.app.test_client()

    def tearDown(self):
        lyrics.DB = self.previous_db
        lyrics.DB_BACKEND = self.previous_backend
        lyrics.DB_INITIALIZED = False
        lyrics.UPLOADS = self.previous_uploads
        self.temp_dir.cleanup()

    def register(self, client, email):
        return client.post(
            "/api/register",
            json={"name": "Compositora Test", "email": email, "password": "password123"},
        )

    def test_app_pages_and_public_assets_are_served(self):
        for path in ("/", "/estilos.css", "/landing.js", "/dashboard", "/dashboard.css", "/dashboard.js", "/img/Logo2.png"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            response.close()
        dashboard = self.client.get("/dashboard")
        self.assertIn(b'id="screen-admin"', dashboard.data)
        dashboard.close()
        landing = self.client.get("/")
        self.assertIn(b'id="registerUsername"', landing.data)
        self.assertNotIn(b'Escribe tus apellidos', landing.data)
        landing.close()
        self.assertEqual(self.client.get("/app.py").status_code, 404)

    def test_registration_profile_score_library_and_access_boundaries(self):
        response = self.register(self.client, "uno@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["user"]["nombre"], "Compositora Test")
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

    def test_projects_can_be_deleted_sequentially_with_cascading_compositions(self):
        self.assertEqual(self.register(self.client, "borrar@example.com").status_code, 200)
        project_ids = []
        for title in ("Primero", "Segundo", "Tercero"):
            project = self.client.post("/api/projects", json={"nombre": title})
            self.assertEqual(project.status_code, 200)
            project_ids.append(project.json["project"]["id_proyecto"])

        composition = self.client.post(
            f"/api/projects/{project_ids[0]}/compositions",
            json={"titulo": "Composición temporal"},
        )
        self.assertEqual(composition.status_code, 200)
        composition_id = composition.json["id_composicion"]

        for project_id in project_ids:
            response = self.client.delete(f"/api/projects/{project_id}")
            self.assertEqual(response.status_code, 200)

        self.assertEqual(self.client.get("/api/projects").json["projects"], [])
        with lyrics.db() as connection:
            self.assertIsNone(
                connection.execute(
                    "SELECT id_composicion FROM compositions WHERE id_composicion=?",
                    (composition_id,),
                ).fetchone()
            )

    def test_admin_table_management_is_protected_and_hides_password_hashes(self):
        self.assertEqual(self.client.get("/api/admin/tables").status_code, 401)
        self.assertEqual(self.register(self.client, "admin@example.com").status_code, 200)
        self.assertEqual(self.client.get("/api/admin/tables").status_code, 403)
        with lyrics.db() as connection:
            admin_role = connection.execute(
                "SELECT id_rol FROM roles WHERE nombre='administrador'"
            ).fetchone()["id_rol"]
            composer_role = connection.execute(
                "SELECT id_rol FROM roles WHERE nombre='compositor'"
            ).fetchone()["id_rol"]
            user_id = self.client.get("/api/me").json["user"]["id_usuario"]
            connection.execute(
                "UPDATE users SET id_rol=? WHERE id_usuario=?",
                (admin_role, user_id),
            )
        self.client.get("/api/me")

        users = self.client.get("/api/admin/tables/users")
        self.assertEqual(users.status_code, 200)
        self.assertNotIn("contrasena_hash", [column["name"] for column in users.json["columns"]])
        self.assertNotIn("contrasena_hash", users.json["rows"][0])

        created = self.client.post(
            "/api/admin/tables/projects",
            json={"nombre": "Admin Suite", "descripcion": "Registro administrado", "id_usuario_creador": user_id},
        )
        self.assertEqual(created.status_code, 200)
        project_id = created.json["id"]
        updated = self.client.put(
            "/api/admin/tables/projects",
            json={"key": {"id_proyecto": project_id}, "values": {"nombre": "Admin Suite actualizada"}},
        )
        self.assertEqual(updated.status_code, 200)
        matching = self.client.get("/api/admin/tables/projects?q=actualizada")
        self.assertEqual(matching.status_code, 200)
        self.assertEqual(matching.json["total"], 1)

        deleted = self.client.delete(
            "/api/admin/tables/projects",
            json={"key": {"id_proyecto": project_id}},
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get("/api/admin/tables/projects?q=actualizada").json["total"], 0)
        self.assertEqual(
            self.client.post("/api/admin/tables/users", json={"nombre": "No permitido"}).status_code,
            403,
        )
        new_user = self.client.post(
            "/api/admin/users",
            json={
                "nombre": "Cuenta creada",
                "correo": "creada@example.com",
                "password": "una-clave-segura-123",
                "id_rol": composer_role,
            },
        )
        self.assertEqual(new_user.status_code, 200)
        admin_users = self.client.get("/api/admin/users?q=creada")
        self.assertEqual(admin_users.status_code, 200)
        self.assertEqual(len(admin_users.json["users"]), 1)
        self.assertNotIn("contrasena_hash", admin_users.json["users"][0])
        self.assertEqual(
            self.client.delete(f"/api/users/{new_user.json['id_usuario']}").status_code,
            200,
        )
        self.assertEqual(
            self.client.put(
                f"/api/users/{user_id}/role",
                json={"id_rol": composer_role},
            ).status_code,
            409,
        )


if __name__ == "__main__":
    unittest.main()
