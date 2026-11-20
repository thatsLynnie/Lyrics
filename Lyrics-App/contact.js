/*
 * Formulario de contacto de Lyrics.
 *
 * Funciona en cualquier página que incluya el bloque de contacto-snippet.html
 * (por ejemplo contacto.html o la landing). Solo necesita un <form id="contactForm">.
 *
 * Flujo: validar en el navegador -> deshabilitar el botón y mostrar "Enviando…" ->
 * POST /api/contact -> mostrar éxito, errores por campo o un mensaje general claro.
 * Las reglas de validación se repiten aquí solo para dar respuesta inmediata; la
 * validación que cuenta es la del servidor (app.py: validate_contact).
 */
(() => {
  const form = document.getElementById('contactForm');
  if (!form) return;

  const RULES = {
    nombre: { label: 'El nombre', min: 2, max: 120 },
    correo: { label: 'El correo', min: 5, max: 255 },
    asunto: { label: 'El asunto', min: 3, max: 150 },
    mensaje: { label: 'El mensaje', min: 10, max: 3000 },
  };
  const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

  const submitButton = form.querySelector('button[type="submit"]');
  const submitLabel = submitButton.textContent;
  const status = document.getElementById('contactStatus');
  const counter = document.getElementById('contactCounter');
  const messageField = form.elements.mensaje;

  /** Muestra u oculta el error de un campo y lo vincula con aria para lectores de pantalla. */
  function setFieldError(name, message) {
    const field = form.elements[name];
    const slot = document.getElementById(`error-${name}`);
    if (!field || !slot) return;
    slot.textContent = message || '';
    field.setAttribute('aria-invalid', message ? 'true' : 'false');
  }

  /** Mensaje general (éxito o error) en la región con aria-live. */
  function setStatus(message, kind) {
    status.textContent = message;
    status.className = `contact-status${kind ? ` is-${kind}` : ''}`;
    status.hidden = !message;
  }

  function validate() {
    const errors = {};
    for (const [name, rule] of Object.entries(RULES)) {
      const value = form.elements[name].value.trim();
      if (!value) errors[name] = `${rule.label} es obligatorio.`;
      else if (value.length < rule.min) errors[name] = `${rule.label} debe tener al menos ${rule.min} caracteres.`;
      else if (value.length > rule.max) errors[name] = `${rule.label} no puede superar ${rule.max} caracteres.`;
    }
    if (!errors.correo && !EMAIL_PATTERN.test(form.elements.correo.value.trim())) {
      errors.correo = 'Escribe un correo válido, por ejemplo nombre@correo.com.';
    }
    return errors;
  }

  /** Traduce un fallo de red o de servidor a un texto que la persona pueda entender. */
  function describeFailure(response, data) {
    if (!response) return 'No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.';
    if (data && data.message) return data.message;
    if (response.status >= 500) return 'El servidor tuvo un problema. Inténtalo de nuevo en unos minutos.';
    return `No se pudo enviar el mensaje (error ${response.status}).`;
  }

  function setLoading(loading) {
    submitButton.disabled = loading;
    submitButton.textContent = loading ? 'Enviando…' : submitLabel;
    form.setAttribute('aria-busy', String(loading));
  }

  messageField.addEventListener('input', () => {
    counter.textContent = `${messageField.value.length} / ${RULES.mensaje.max}`;
  });
  // Al corregir un campo se limpia su error sin esperar a un nuevo envío.
  form.addEventListener('input', event => {
    if (event.target.name && RULES[event.target.name]) setFieldError(event.target.name, '');
  });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (submitButton.disabled) return; // evita envíos dobles
    setStatus('', '');

    const errors = validate();
    Object.keys(RULES).forEach(name => setFieldError(name, errors[name]));
    const firstInvalid = Object.keys(errors)[0];
    if (firstInvalid) {
      setStatus('Revisa los campos marcados.', 'error');
      form.elements[firstInvalid].focus();
      return;
    }

    setLoading(true);
    let response = null;
    let data = null;
    try {
      response = await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nombre: form.elements.nombre.value.trim(),
          correo: form.elements.correo.value.trim(),
          asunto: form.elements.asunto.value.trim(),
          mensaje: form.elements.mensaje.value.trim(),
          sitio_web: form.elements.sitio_web.value, // honeypot: debe ir vacío
        }),
      });
      data = await response.json().catch(() => null); // un 502 de proxy puede no traer JSON
    } catch (error) {
      console.error('Fallo de red al enviar el formulario de contacto:', error);
    } finally {
      setLoading(false);
    }

    if (response && response.ok && data && data.ok) {
      form.reset();
      counter.textContent = `0 / ${RULES.mensaje.max}`;
      setStatus(data.message || 'Gracias, recibimos tu mensaje.', 'success');
      return;
    }
    // El servidor puede devolver errores por campo (400); si no, un mensaje general.
    if (data && data.errors) {
      Object.entries(data.errors).forEach(([name, message]) => setFieldError(name, message));
      const field = Object.keys(data.errors).find(name => form.elements[name]);
      if (field) form.elements[field].focus();
    }
    setStatus(describeFailure(response, data), 'error');
  });
})();
