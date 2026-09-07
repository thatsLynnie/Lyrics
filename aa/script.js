/* =========================================================
   LYRICS - FUNCIONALIDAD DE LA PÁGINA
   Login y registro compactos
========================================================= */

document.addEventListener('DOMContentLoaded', () => {
    const loginModal = document.getElementById('loginModal');
    const registerModal = document.getElementById('registerModal');
    const loginForm = loginModal?.querySelector('.auth-form');
    const registerForm = registerModal?.querySelector('.auth-form');

    function setModal(modal, open) {
        if (!modal) return;
        modal.style.display = open ? 'flex' : 'none';
        modal.setAttribute('aria-hidden', open ? 'false' : 'true');
        document.body.style.overflow = open ? 'hidden' : '';

        if (open) {
            setTimeout(() => {
                const firstInput = modal.querySelector('input:not([type="checkbox"])');
                firstInput?.focus();
            }, 100);
        }
    }

    function openLogin() {
        setModal(registerModal, false);
        setModal(loginModal, true);
    }

    function openRegister() {
        setModal(loginModal, false);
        setModal(registerModal, true);
    }

    function closeAuth() {
        setModal(loginModal, false);
        setModal(registerModal, false);
        document.body.style.overflow = '';
    }

    // Disponibles también para los botones onclick del HTML.
    window.openLogin = openLogin;
    window.openRegister = openRegister;
    window.closeLogin = closeAuth;
    window.closeRegister = closeAuth;

    // BOTONES DEL MENÚ
    document.querySelectorAll('.auth-trigger').forEach(button => {
        button.addEventListener('click', event => {
            event.preventDefault();
            const mode = button.dataset.authMode;
            mode === 'register' ? openRegister() : openLogin();
        });
    });

    // BOTONES DE CERRAR
    document.querySelectorAll('[data-close-auth], .close-auth').forEach(button => {
        button.addEventListener('click', closeAuth);
    });

    // Cerrar al hacer clic fuera del cuadro
    document.querySelectorAll('.auth-overlay').forEach(overlay => {
        overlay.addEventListener('click', event => {
            if (event.target === overlay) closeAuth();
        });
    });

    // Cerrar con ESC
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') closeAuth();
    });

    // CAMBIO ENTRE LOGIN Y REGISTRO
    loginModal?.querySelector('.switch-auth a')?.addEventListener('click', event => {
        event.preventDefault();
        openRegister();
    });

    registerModal?.querySelector('.switch-auth a')?.addEventListener('click', event => {
        event.preventDefault();
        openLogin();
    });

    function showMessage(form, text, type = 'error') {
        let message = form.querySelector('.auth-message');

        if (!message) {
            message = document.createElement('p');
            message.className = 'auth-message';
            form.prepend(message);
        }

        message.textContent = text;
        message.className = `auth-message ${type}`;
    }

    // REGISTRO FUNCIONAL EN EL NAVEGADOR
    registerForm?.addEventListener('submit', event => {
        event.preventDefault();

        const name = document.getElementById('registerName').value.trim();
        const lastName = document.getElementById('registerLastName').value.trim();
        const email = document.getElementById('registerEmail').value.trim().toLowerCase();
        const password = document.getElementById('registerPassword').value;
        const confirm = document.getElementById('registerConfirm').value;

        if (!name || !lastName || !email || !password || !confirm) {
            showMessage(registerForm, 'Please complete all fields.');
            return;
        }

        if (password.length < 6) {
            showMessage(registerForm, 'The password must contain at least 6 characters.');
            return;
        }

        if (password !== confirm) {
            showMessage(registerForm, 'Passwords do not match.');
            return;
        }

        const user = { name, lastName, email, password };
        localStorage.setItem('lyricsUser', JSON.stringify(user));
        localStorage.setItem('lyricsSession', JSON.stringify({ name, lastName, email }));

        showMessage(registerForm, 'Account created successfully!', 'success');
        registerForm.reset();

        setTimeout(() => {
            closeAuth();
            updateAuthButtons();
        }, 700);
    });

    // INICIO DE SESIÓN FUNCIONAL
    loginForm?.addEventListener('submit', event => {
        event.preventDefault();

        const email = document.getElementById('loginEmail').value.trim().toLowerCase();
        const password = document.getElementById('loginPassword').value;
        const savedUser = JSON.parse(localStorage.getItem('lyricsUser') || 'null');

        if (!savedUser) {
            showMessage(loginForm, 'No account was found. Please create one first.');
            return;
        }

        if (savedUser.email !== email || savedUser.password !== password) {
            showMessage(loginForm, 'Incorrect email or password.');
            return;
        }

        localStorage.setItem('lyricsSession', JSON.stringify({
            name: savedUser.name,
            lastName: savedUser.lastName,
            email: savedUser.email
        }));

        showMessage(loginForm, `Welcome back, ${savedUser.name}!`, 'success');
        loginForm.reset();

        setTimeout(() => {
            closeAuth();
            updateAuthButtons();
        }, 700);
    });

    // GOOGLE: interfaz preparada. OAuth real requiere configuración externa.
    document.querySelectorAll('[data-google-auth]').forEach(button => {
        button.addEventListener('click', () => {
            alert('Google sign-in needs Google Identity Services or Firebase Authentication to connect a real Google account.');
        });
    });

    function updateAuthButtons() {
        const session = JSON.parse(localStorage.getItem('lyricsSession') || 'null');
        const loginButtons = document.querySelectorAll('.btn-login');
        const registerButtons = document.querySelectorAll('.btn-register');

        if (session) {
            loginButtons.forEach(button => {
                button.textContent = `Hi, ${session.name}`;
                button.dataset.authMode = 'login';
            });

            registerButtons.forEach(button => {
                button.textContent = 'Log out';
                button.dataset.authMode = 'logout';
                button.onclick = event => {
                    event.preventDefault();
                    localStorage.removeItem('lyricsSession');
                    location.reload();
                };
            });
        }
    }

    updateAuthButtons();
});
