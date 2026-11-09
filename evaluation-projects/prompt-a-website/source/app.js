// Northstar Studio — Release 1.0
// Vanilla JavaScript (no build step, no external services) so the site runs from any static server or file://.
'use strict';
const BUILD_VERSION = '1.0.0';

/* ---------- Pure helpers (also exported for automated tests) ---------- */

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function validateContact(values) {
  const v = values || {};
  const errors = {};
  const name = String(v.name || '').trim();
  const email = String(v.email || '').trim();
  const message = String(v.message || '').trim();
  if (!name) errors.name = 'Please enter your name.';
  if (!email) errors.email = 'Please enter your email address.';
  else if (!EMAIL_PATTERN.test(email)) errors.email = 'Please enter a valid email address, like name@example.com.';
  if (!message) errors.message = 'Please enter a message.';
  else if (message.length < 10) errors.message = 'Please write at least 10 characters so we can help.';
  return { valid: Object.keys(errors).length === 0, errors };
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function projectCardHtml(p) {
  const tags = (p.tags || []).map((t) => `<li>${escapeHtml(t)}</li>`).join('');
  return `<article class="card" role="listitem">
    <img src="${escapeHtml(p.image)}" alt="${escapeHtml(p.alt || '')}" width="320" height="200" loading="lazy">
    <div class="card__body">
      <p class="card__cat">${escapeHtml(p.category)}</p>
      <h3>${escapeHtml(p.title)}</h3>
      <p>${escapeHtml(p.summary)}</p>
      <ul class="tags" aria-label="Tags">${tags}</ul>
    </div>
  </article>`;
}

function renderProjects(container, projects) {
  container.innerHTML = projects.map(projectCardHtml).join('');
  return projects.length;
}

/* ---------- Browser behaviour ---------- */

function initNav(doc) {
  const toggle = doc.getElementById('nav-toggle');
  const nav = doc.getElementById('site-nav');
  if (!toggle || !nav) return;
  doc.documentElement.classList.add('js');
  toggle.hidden = false;

  const setOpen = (open, returnFocus) => {
    nav.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    if (!open && returnFocus) toggle.focus();
  };
  setOpen(false, false);

  toggle.addEventListener('click', () => setOpen(toggle.getAttribute('aria-expanded') !== 'true', false));
  doc.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') setOpen(false, true);
  });
  nav.addEventListener('click', (e) => { if (e.target.closest('a')) setOpen(false, false); });
}

function initPortfolio(doc, win) {
  const grid = doc.getElementById('project-grid');
  if (!grid) return;
  const data = win.NORTHSTAR_PROJECTS;
  if (!Array.isArray(data) || data.length === 0) {
    grid.innerHTML = '<p class="muted">Projects are temporarily unavailable.</p>';
    return;
  }
  renderProjects(grid, data);
}

function initContactForm(doc) {
  const form = doc.getElementById('contact-form');
  const status = doc.getElementById('form-status');
  if (!form || !status) return;
  const fields = ['name', 'email', 'message'];

  const showErrors = (errors) => {
    fields.forEach((f) => {
      const input = doc.getElementById(f);
      const err = doc.getElementById(f + '-error');
      if (errors[f]) {
        err.textContent = errors[f];
        err.hidden = false;
        input.setAttribute('aria-invalid', 'true');
      } else {
        err.textContent = '';
        err.hidden = true;
        input.removeAttribute('aria-invalid');
      }
    });
  };

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const values = {};
    fields.forEach((f) => { values[f] = doc.getElementById(f).value; });
    const result = validateContact(values);
    showErrors(result.errors);
    if (!result.valid) {
      const count = Object.keys(result.errors).length;
      status.className = 'form-status is-error';
      status.textContent = `Please fix ${count} ${count === 1 ? 'field' : 'fields'} before sending.`;
      doc.getElementById(Object.keys(result.errors)[0]).focus();
      return;
    }
    // Local demo only: no network request is made and nothing is stored.
    status.className = 'form-status is-success';
    status.textContent = 'Thanks! Your message passed validation. This is a local demo, so it was not sent to anyone.';
    form.reset();
    showErrors({});
  });

  // Clear a field's error as soon as the user fixes it.
  fields.forEach((f) => {
    const input = doc.getElementById(f);
    input.addEventListener('input', () => {
      if (input.getAttribute('aria-invalid') !== 'true') return;
      const single = validateContact({ name: 'x', email: 'a@b.co', message: 'xxxxxxxxxx', [f]: input.value });
      if (!single.errors[f]) {
        const err = doc.getElementById(f + '-error');
        err.textContent = '';
        err.hidden = true;
        input.removeAttribute('aria-invalid');
      }
    });
  });
}

if (typeof document !== 'undefined') {
  const boot = () => { initNav(document); initPortfolio(document, window); initContactForm(document); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
  console.info(`Northstar Studio ${BUILD_VERSION}`);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { validateContact, escapeHtml, projectCardHtml, renderProjects, BUILD_VERSION };
}
