import {publicKeyFromJSON, credentialToJSON} from '/auth/assets/fastpasskey.js';
const form = document.querySelector('#auth-form');
async function authenticate(kind) {
  const buttons = [...form.querySelectorAll('button')];
  buttons.forEach(button => button.disabled = true);
  const status = document.querySelector('#status');
  async function post(step, payload) {
    const response = await fetch(`/auth/${kind}/${step}/`, {
      method: 'POST', headers: {'Content-Type': 'application/json',
        'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value},
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Sign-in failed. Please try again.');
    return data;
  }
  try {
    status.textContent = 'Continue with your passkey…';
    const options = await post('options', {username: form.username.value});
    const publicKey = publicKeyFromJSON(options);
    const credential = kind === 'register' ? await navigator.credentials.create({publicKey})
      : await navigator.credentials.get({publicKey});
    await post('verify', {credential: credentialToJSON(credential)});
    window.location.assign(form.dataset.next || '/');
  } catch (error) { status.textContent = error.message; }
  finally { buttons.forEach(button => button.disabled = false); }
}
form.addEventListener('submit', event => {event.preventDefault(); authenticate('login');});
document.querySelector('#register').addEventListener('click', () => authenticate('register'));
