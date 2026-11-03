import app


def main():
    app.init_db()
    email = input('Correo de la cuenta registrada que será administradora: ').strip().lower()
    if not email or '@' not in email:
        raise SystemExit('Escribe un correo válido.')

    with app.db() as connection:
        user = connection.execute(
            'SELECT id_usuario,nombre FROM users WHERE correo=?',
            (email,),
        ).fetchone()
        if not user:
            raise SystemExit('No existe una cuenta con ese correo. Regístrala e inténtalo de nuevo.')
        role = connection.execute(
            "SELECT id_rol FROM roles WHERE nombre='administrador'",
        ).fetchone()
        if not role:
            raise SystemExit('No existe el rol administrador en la base de datos.')

        connection.execute(
            'UPDATE users SET id_rol=? WHERE id_usuario=?',
            (role['id_rol'], user['id_usuario']),
        )

    print('Rol administrador asignado correctamente. Cierra sesión y vuelve a entrar en Lyrics.')


if __name__ == '__main__':
    main()
