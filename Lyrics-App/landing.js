(() => {
  const modal = document.getElementById('authModal');
  if (!modal) return;
  const form = document.getElementById('authForm');
  const title = document.getElementById('authTitle');
  const subtitle = document.getElementById('authSubtitle');
  const submit = document.getElementById('authSubmit');
  const switcher = document.getElementById('authSwitch');
  const nameGroup = document.getElementById('nameGroup');
  const nameInput = document.getElementById('authName');
  const emailInput = document.getElementById('authEmail');
  const passwordInput = document.getElementById('authPassword');
  const message = document.getElementById('authMessage');
  let mode = 'login';

  function setMode(next) {
    mode = next;
    const register = mode === 'register';
    title.textContent = register ? 'Únete a Lyrics' : 'Bienvenido a Lyrics';
    subtitle.textContent = register ? 'Crea tu cuenta y empieza a construir tu espacio musical.' : 'Inicia sesión para continuar.';
    submit.textContent = register ? 'Crear cuenta' : 'Iniciar sesión';
    switcher.textContent = register ? '¿Ya tienes cuenta? Inicia sesión' : '¿No tienes cuenta? Regístrate';
    nameGroup.classList.toggle('hidden', !register);
    nameInput.required = register;
    message.textContent = '';
  }
  function open(modeValue) {
    setMode(modeValue || 'login');
    modal.classList.add('show');
    modal.setAttribute('aria-hidden','false');
    document.body.style.overflow='hidden';
    setTimeout(()=> (mode === 'register' ? nameInput : emailInput).focus(), 50);
  }
  function close() {
    modal.classList.remove('show');
    modal.setAttribute('aria-hidden','true');
    document.body.style.overflow='';
  }
  document.querySelectorAll('.auth-trigger').forEach(btn => btn.addEventListener('click', e => {
    e.preventDefault(); open(btn.dataset.authMode || 'login');
  }));
  document.querySelectorAll('[data-close-auth]').forEach(el => el.addEventListener('click', close));
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
  switcher.addEventListener('click', ()=>setMode(mode === 'login' ? 'register' : 'login'));

  function setMessage(text, error=false){ message.textContent=text; message.classList.toggle('error',error); message.classList.toggle('success',!error && !!text); }
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const payload = {email: emailInput.value.trim(), password: passwordInput.value};
    if (mode === 'register') payload.name = nameInput.value.trim();
    if (!payload.email || !payload.password || (mode==='register' && !payload.name)) return setMessage('Completa todos los campos.', true);
    submit.disabled=true; submit.textContent='Procesando...';
    try {
      const res = await fetch(`/api/${mode}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.message || 'Ocurrió un error.');
      setMessage(data.message,false);
      setTimeout(()=>{ close(); form.reset(); window.location.href='/dashboard'; },450);
    } catch(err) { setMessage(err.message,true); }
    finally { submit.disabled=false; submit.textContent=mode==='register'?'Crear cuenta':'Iniciar sesión'; }
  });

  function updateUser(user) {
    if (!user) return;
    document.querySelectorAll('.btn-login').forEach(el => {
      el.textContent = `Hola, ${(user.nombre || 'usuario').split(' ')[0]}`;
      el.classList.remove('auth-trigger');
      el.onclick = () => { window.location.href='/dashboard'; };
    });
    document.querySelectorAll('.btn-register').forEach(el => { el.textContent = 'Cerrar sesión'; el.dataset.authMode='logout'; el.classList.remove('auth-trigger'); el.onclick = async ev => { ev.preventDefault(); await fetch('/api/logout',{method:'POST'}); location.reload(); }; });
  }
  fetch('/api/me').then(r=>r.json()).then(d=>{if(d.ok) updateUser(d.user)}).catch(()=>{});

  // Active nav link while scrolling.
  const sections=[...document.querySelectorAll('section[id], footer[id]')];
  const links=[...document.querySelectorAll('.nav-link[href^="#"]')];
  const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{
    if(entry.isIntersecting){ links.forEach(l=>l.classList.toggle('active',l.getAttribute('href')==='#'+entry.target.id)); }
  }),{rootMargin:'-35% 0px -55% 0px',threshold:0});
  sections.forEach(s=>observer.observe(s));
})();
