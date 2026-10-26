"""CLI-only test setup. No fixture endpoint or production auth bypass exists."""
import json
import os
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from accounts.models import User
from accounts.mobile import issue_token
user = User.objects.create_user(username='ios-e2e')
Path('ios/Postcard/UITests/Fixture.json').write_text(json.dumps({
    'server': os.environ['APP_BASE_URL'], 'token': issue_token(user),
}))
