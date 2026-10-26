import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp, rm, mkdir} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {chromium} from 'playwright';
import {createVirtualAuthenticator} from '@malaber/fastpasskey/playwright';

const temp = await mkdtemp(path.join(os.tmpdir(), 'postcard-browser-'));
const origin = 'http://localhost:8766';
const env = {...process.env, DATABASE_PATH: path.join(temp, 'db.sqlite3'), MEDIA_ROOT: path.join(temp, 'media'), APP_BASE_URL: origin, DEBUG: 'true'};
const python = process.env.PYTHON ?? '.venv/bin/python';
function run(args) { return new Promise((resolve, reject) => {
  const child = spawn(python, args, {env, stdio: 'inherit'});
  child.on('error', reject); child.on('exit', code => code === 0 ? resolve() : reject(new Error(`Exit ${code}`)));
}); }
let server, browser;
try {
  await run(['manage.py', 'migrate', '--noinput']);
  server = spawn(python, ['manage.py', 'runserver', '8766', '--noreload'], {env, stdio: 'inherit'});
  for (let i = 0; ; i++) {
    try { if ((await fetch(origin)).ok) break; } catch {}
    if (i > 60) throw new Error('Backend did not start');
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  const authenticator = await createVirtualAuthenticator(context, page);
  await page.goto(origin + '/auth/login/');
  await page.getByLabel('Username', {exact: false}).fill('browser-user');
  await page.getByRole('button', {name: 'Create account', exact: true}).click();
  await page.waitForURL(origin + '/');
  await page.getByRole('button', {name: 'Logout', exact: true}).click();
  await page.goto(origin + '/auth/login/');
  await page.getByRole('button', {name: 'Sign in with passkey', exact: true}).click();
  await page.waitForURL(origin + '/');

  await page.goto(origin + '/auth/passkeys/');
  await authenticator.replace();
  await page.getByRole('button', {name: 'Add passkey', exact: true}).click();
  await page.waitForFunction(() => document.querySelectorAll('[data-key]').length === 2);
  const secondKey = page.locator('[data-key]').nth(1);
  await secondKey.getByLabel('Passkey name').fill('Phone');
  await secondKey.getByRole('button', {name: 'Rename', exact: true}).click();
  await page.waitForFunction(() => [...document.querySelectorAll('[data-key] input')].some(input => input.value === 'Phone'));
  page.once('dialog', dialog => dialog.accept());
  await page.locator('[data-key]').first().getByRole('button', {name: 'Remove', exact: true}).click();
  await page.waitForFunction(() => document.querySelectorAll('[data-key]').length === 1);
  assert.equal(await page.getByLabel('Passkey name').inputValue(), 'Phone');
  assert.equal(await page.getByRole('button', {name: 'Remove', exact: true}).isDisabled(), true);

  const verifier = crypto.randomBytes(32).toString('base64url');
  const challenge = crypto.createHash('sha256').update(verifier).digest('base64url');
  const state = crypto.randomBytes(32).toString('base64url');
  const authorize = await context.request.get(`${origin}/api/v1/auth/mobile/authorize?state=${state}&code_challenge=${challenge}`, {maxRedirects: 0});
  assert.equal(authorize.status(), 302);
  const callback = new URL(authorize.headers().location);
  assert.equal(callback.protocol, 'de.malaber.postcard:'); assert.equal(callback.searchParams.get('state'), state);
  const payload = {code: callback.searchParams.get('code'), code_verifier: verifier};
  const tokenResponse = await context.request.post(origin + '/api/v1/auth/mobile/token', {data: payload});
  assert.equal(tokenResponse.status(), 200);
  const token = (await tokenResponse.json()).access_token;
  assert.equal((await context.request.post(origin + '/api/v1/auth/mobile/token', {data: payload})).status(), 401);
  const headers = {Authorization: `Bearer ${token}`};
  const create = await context.request.post(origin + '/api/v1/frames/', {headers, data: {name: 'Family screen'}});
  assert.equal(create.status(), 201); let viewer = await create.json();
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a0WQAAAAASUVORK5CYII=', 'base64');
  const upload = await context.request.post(`${origin}/api/v1/frames/${viewer.id}/photos/`, {headers,
    multipart: {caption: 'Hello from E2E', image: {name: 'test.png', mimeType: 'image/png', buffer: png}}});
  assert.equal(upload.status(), 201); const photo = await upload.json();
  await page.goto(viewer.viewer_url);
  await page.waitForFunction(() => { const image = document.querySelector('#photo'); return image && !image.hidden && image.naturalWidth > 0; });
  await mkdir('test-results', {recursive: true});
  await page.screenshot({path: 'test-results/viewer.png'});
  assert.equal((await context.request.patch(`${origin}/api/v1/photos/${photo.id}/`, {headers, data: {is_active: false}})).status(), 200);
  await page.waitForFunction(() => document.querySelector('#photo').hidden);
  await context.request.post(`${origin}/api/v1/frames/${viewer.id}/rotate/`, {headers, data: {}});
  assert.equal((await context.request.get(viewer.viewer_url)).status(), 404);
  await context.request.delete(`${origin}/api/v1/frames/${viewer.id}/`, {headers});
  await context.request.post(origin + '/api/v1/auth/mobile/logout', {headers});
  assert.equal((await context.request.get(origin + '/api/v1/frames/', {headers})).status(), 401);
  console.log('PASS: real passkey registration/login → PKCE → upload → viewer → hide → rotation → deletion → revoke');
} finally {
  await browser?.close();
  if (server) { server.kill(); await new Promise(resolve => server.once('exit', resolve)); }
  await rm(temp, {recursive: true, force: true});
}
