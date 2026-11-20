(() => {
  function showMessage(element, text, isError = false) {
    element.textContent = text;
    element.classList.toggle('error', isError);
  }

  async function submitAuth(event, mode) {
    event.preventDefault();
    const form = event.currentTarget;
    const message = document.getElementById(mode === 'register' ? 'registerMessage' : 'loginMessage');
    const button = form.querySelector('button[type="submit"]');
    const payload = {
      email: document.getElementById(mode === 'register' ? 'registerEmail' : 'loginEmail').value.trim(),
      password: document.getElementById(mode === 'register' ? 'registerPassword' : 'loginPassword').value
    };

    if (mode === 'register') {
      payload.name = document.getElementById('registerUsername').value.trim();
      if (payload.password !== document.getElementById('registerPasswordConfirm').value) {
        showMessage(message, 'Las contraseñas no coinciden.', true);
        return;
      }
    }

    // Estado de carga: se bloquea el botón (evita envíos dobles) y se avisa que algo está pasando.
    const idleLabel = button.textContent;
    button.disabled = true;
    button.textContent = mode === 'register' ? 'Creando cuenta…' : 'Entrando…';
    showMessage(message, '');
    try {
      let response;
      try {
        response = await fetch(`/api/${mode}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } catch (networkError) {
        console.error('Fallo de red en autenticación:', networkError);
        throw new Error('No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.');
      }
      // Un error de proxy o de servidor puede devolver HTML en lugar de JSON.
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) {
        const fallback = response.status >= 500
          ? 'El servidor tuvo un problema. Inténtalo de nuevo en unos minutos.'
          : 'No se pudo completar la solicitud.';
        throw new Error(data.message || fallback);
      }
      window.location.assign('/dashboard');
    } catch (error) {
      showMessage(message, error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = idleLabel;
    }
  }

  document.getElementById('loginForm').addEventListener('submit', event => submitAuth(event, 'login'));
  document.getElementById('registerForm').addEventListener('submit', event => submitAuth(event, 'register'));

  fetch('/api/me')
    .then(response => response.json())
    .then(data => {
      if (!data.ok || !data.user) return;
      document.querySelectorAll('.btn-login').forEach(link => {
        link.textContent = `Hola, ${(data.user.nombre || 'usuario').split(' ')[0]}`;
        link.href = '/dashboard';
      });
      document.querySelectorAll('.btn-register').forEach(link => {
        link.textContent = 'Cerrar sesión';
        link.href = '#logout';
        link.addEventListener('click', async event => {
          event.preventDefault();
          try {
            const response = await fetch('/api/logout', { method: 'POST' });
            if (!response.ok) throw new Error(`Error ${response.status}`);
            window.location.reload();
          } catch (error) {
            console.error('No se pudo cerrar la sesión:', error);
            window.alert('No se pudo cerrar la sesión. Inténtalo de nuevo.');
          }
        });
      });
    })
    .catch(error => console.error('No se pudo cargar la sesión:', error));

  const sections = [...document.querySelectorAll('section[id], footer[id]')];
  const links = [...document.querySelectorAll('.nav-link[href^="#"]')];
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) {
        links.forEach(link => link.classList.toggle('active', link.getAttribute('href') === `#${entry.target.id}`));
      }
    }), { rootMargin: '-35% 0px -55% 0px', threshold: 0 });
    sections.forEach(section => observer.observe(section));
  }
})();
