import io
import tempfile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from accounts.models import User
from accounts.mobile import issue_token
from .models import Frame, Photo


class APITests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings = override_settings(MEDIA_ROOT=self.directory.name)
        self.settings.enable(); self.addCleanup(self.settings.disable)
        self.user = User.objects.create_user(username='owner')
        self.other = User.objects.create_user(username='other')
        self.headers = {'HTTP_AUTHORIZATION': 'Bearer ' + issue_token(self.user)}
        self.frame = Frame.objects.create(owner=self.user, name='Kitchen')
        self.foreign = Frame.objects.create(owner=self.other, name='Private')

    def mutate(self, path, body, method='post'):
        return getattr(self.client, method)(path, body, content_type='application/json', **self.headers)

    def upload(self):
        image = io.BytesIO(); Image.new('RGB', (32, 20), 'orange').save(image, 'PNG')
        return self.client.post(f'/api/v1/frames/{self.frame.id}/photos/',
            {'image': SimpleUploadedFile('photo.png', image.getvalue()), 'caption': 'Hello'}, **self.headers)

    def test_image_reaches_only_assigned_viewer(self):
        response = self.upload(); self.assertEqual(response.status_code, 201)
        photo = Photo.objects.get()
        self.assertEqual(photo.caption, 'Hello')
        self.assertTrue(photo.image.name.endswith('.jpg'))
        endpoint = f'/p/frame/{self.frame.access_token}/api/'
        self.assertEqual(len(self.client.get(endpoint).json()['photos']), 1)
        self.assertEqual(self.client.get(photo.viewer_image_url).status_code, 200)
        self.assertEqual(self.client.get(f'/p/frame/{self.foreign.access_token}/api/').json()['photos'], [])
        response = self.mutate(f'/api/v1/photos/{photo.id}/', {'is_active': False}, 'patch')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(endpoint).json()['photos'], [])
        self.assertEqual(self.client.get(photo.viewer_image_url).status_code, 404)

    def test_owner_scope_and_validation(self):
        self.assertEqual(self.mutate('/api/v1/frames/', {'name': ''}).status_code, 400)
        self.assertEqual(self.mutate(f'/api/v1/frames/{self.foreign.id}/', {'name': 'stolen'}, 'patch').status_code, 404)
        self.assertEqual(self.mutate(f'/api/v1/frames/{self.foreign.id}/rotate/', {}).status_code, 404)
        self.upload(); photo = Photo.objects.get()
        self.assertEqual(self.mutate(f'/api/v1/photos/{photo.id}/', {'frame_id': str(self.foreign.id)}, 'patch').status_code, 404)
        self.assertEqual(self.mutate(f'/api/v1/photos/{photo.id}/', {'is_active': 'false'}, 'patch').status_code, 400)
        response = self.client.post(f'/api/v1/frames/{self.frame.id}/photos/',
            {'image': SimpleUploadedFile('fake.jpg', b'not an image')}, **self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Photo.objects.count(), 1)

    def test_crud_rotation_assignment_and_file_cleanup(self):
        response = self.mutate('/api/v1/frames/', {'name': 'Bedroom'})
        self.assertEqual(response.status_code, 201)
        destination = response.json()['id']
        self.upload(); photo = Photo.objects.get()
        old_url = photo.viewer_image_url
        self.assertEqual(self.mutate(f'/api/v1/photos/{photo.id}/', {'frame_id': destination, 'caption': 'Moved'}, 'patch').status_code, 200)
        self.assertEqual(self.client.get(old_url).status_code, 404)
        photo.refresh_from_db(); old_url = photo.viewer_image_url
        self.assertEqual(self.mutate(f'/api/v1/frames/{destination}/rotate/', {}).status_code, 200)
        self.assertEqual(self.client.get(old_url).status_code, 404)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.mutate(f'/api/v1/frames/{destination}/', {}, 'delete').status_code, 204)
        self.assertFalse(photo.image.storage.exists(photo.image.name))
        self.assertFalse(Photo.objects.exists())
