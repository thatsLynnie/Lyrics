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

    button.disabled = true;
    showMessage(message, '');
    try {
      const response = await fetch(`/api/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.message || 'No se pudo completar la solicitud.');
      window.location.assign('/dashboard');
    } catch (error) {
      showMessage(message, error.message || 'No se pudo conectar con el servidor.', true);
    } finally {
      button.disabled = false;
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
          const response = await fetch('/api/logout', { method: 'POST' });
          if (!response.ok) throw new Error('No se pudo cerrar la sesión.');
          window.location.reload();
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
