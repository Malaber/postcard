import base64
import hashlib
import json
from datetime import timedelta
from urllib.parse import parse_qs, urlparse
from django.test import Client, TestCase
from django.utils import timezone
from .models import AuthFlow, User
from .mobile import issue_token


class AuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='owner')

    def grant(self):
        self.client.force_login(self.user)
        self.verifier = 'x' * 43
        self.challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).decode().rstrip('=')
        response = self.client.get('/api/v1/auth/mobile/authorize', {'state': 's' * 43, 'code_challenge': self.challenge})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('de.malaber.postcard://auth?'))
        return parse_qs(urlparse(response['Location']).query)['code'][0]

    def exchange(self, code, verifier):
        return self.client.post('/api/v1/auth/mobile/token', {'code': code, 'code_verifier': verifier}, content_type='application/json')

    def test_pkce_replay_revocation(self):
        code = self.grant()
        self.assertEqual(self.exchange(code, 'y' * 43).status_code, 401)
        response = self.exchange(code, self.verifier)
        self.assertEqual(response.status_code, 200)
        token = response.json()['access_token']
        self.assertEqual(self.exchange(code, self.verifier).status_code, 401)
        self.assertEqual(self.client.get('/api/v1/frames/').status_code, 401)
        headers = {'HTTP_AUTHORIZATION': 'Bearer ' + token}
        self.assertEqual(self.client.get('/api/v1/frames/', **headers).status_code, 200)
        self.assertEqual(self.client.post('/api/v1/auth/mobile/logout', **headers).status_code, 204)
        self.assertEqual(self.client.get('/api/v1/frames/', **headers).status_code, 401)

    def test_expired_grant(self):
        code = self.grant()
        AuthFlow.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.exchange(code, self.verifier).status_code, 401)

    def test_inactive_account(self):
        token = issue_token(self.user)
        self.user.is_active = False; self.user.save()
        self.assertEqual(self.client.get('/api/v1/frames/', HTTP_AUTHORIZATION='Bearer ' + token).status_code, 401)

    def test_csrf_and_method_enforced(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/auth/register/options/', '{}', content_type='application/json').status_code, 403)
        self.assertEqual(self.client.get('/auth/register/options/').status_code, 405)

    def test_registration_uses_fastpasskey_and_cannot_replay(self):
        response = self.client.post('/auth/register/options/', {'username': 'new'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        options = response.json()
        self.assertEqual(options['authenticatorSelection']['residentKey'], 'required')
        self.assertEqual(options['authenticatorSelection']['userVerification'], 'required')
        self.assertEqual(options['rp']['id'], 'localhost')
        for _ in range(2):
            response = self.client.post('/auth/register/verify/', {'credential': {'id': 'invalid'}}, content_type='application/json')
            self.assertEqual(response.status_code, 400)
        self.assertTrue(AuthFlow.objects.get().consumed)
        self.assertFalse(User.objects.filter(username='new').exists())

    def test_no_open_redirect(self):
        response = self.client.get('/auth/login/', {'next': '//evil.example/'})
        self.assertEqual(response.context['next_url'], '/')

    def test_passkey_management_requires_owner_and_another_key(self):
        from .models import PasskeyCredential
        key = PasskeyCredential.objects.create(user=self.user, credential_id='YWJj', public_key='YWJj')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/auth/passkeys/').status_code, 200)
        self.assertEqual(self.client.post(f'/auth/passkeys/{key.id}/delete/options/', '{}', content_type='application/json').status_code, 400)
        response = self.client.post(f'/auth/passkeys/{key.id}/rename/', {'name': 'My phone'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        key.refresh_from_db(); self.assertEqual(key.name, 'My phone')
        other = User.objects.create_user(username='other')
        self.client.force_login(other)
        self.assertEqual(self.client.post(f'/auth/passkeys/{key.id}/rename/', {'name': 'stolen'}, content_type='application/json').status_code, 404)
