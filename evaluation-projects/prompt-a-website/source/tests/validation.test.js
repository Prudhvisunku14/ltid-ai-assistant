// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert/strict');
const { validateContact, escapeHtml, projectCardHtml } = require('../app.js');
const PROJECTS = require('../data/projects-data.js');

test('empty form reports all three required fields', () => {
  const r = validateContact({});
  assert.equal(r.valid, false);
  assert.deepEqual(Object.keys(r.errors).sort(), ['email', 'message', 'name']);
});

test('invalid email is rejected, valid email accepted', () => {
  assert.ok(validateContact({ name: 'Ada', email: 'ada@', message: 'Hello there, studio' }).errors.email);
  assert.equal(validateContact({ name: 'Ada', email: 'ada@example.com', message: 'Hello there, studio' }).valid, true);
});

test('whitespace-only values are treated as empty', () => {
  const r = validateContact({ name: '   ', email: ' ', message: '      ' });
  assert.equal(Object.keys(r.errors).length, 3);
});

test('short message is rejected', () => {
  assert.ok(validateContact({ name: 'A', email: 'a@b.co', message: 'hi' }).errors.message);
});

test('escapeHtml neutralises markup', () => {
  assert.equal(escapeHtml('<img src=x onerror="a">'), '&lt;img src=x onerror=&quot;a&quot;&gt;');
});

test('project card renders title, alt text and escapes content', () => {
  const html = projectCardHtml({ ...PROJECTS[0], title: '<b>x</b>' });
  assert.match(html, /&lt;b&gt;x&lt;\/b&gt;/);
  assert.match(html, /alt="[^"]+"/);
});

test('portfolio data contains at least three projects', () => {
  assert.ok(PROJECTS.length >= 3);
});
