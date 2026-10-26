# Postcard

Send photos from your iPhone or iPad to private browser-based picture viewers.
The SwiftUI app focuses on choosing a viewer, adding photos from the system Photos
picker, and seeing them appear on that screen. Viewers can be created, renamed,
deleted, shared, and disconnected by replacing their private link. Photos support
captions, visibility, reassignment, and deletion.

## Backend

Python 3.14+, uv, SQLite (default):

```sh
uv sync --frozen
uv run python manage.py migrate
uv run python manage.py runserver
```

Open `http://localhost:8000/auth/login/` to register a passkey. Existing accounts,
credential IDs, public keys, viewer IDs, and photos survive migration. Existing
non-discoverable credentials can still sign in by entering their username.
`/auth/passkeys/` adds and renames keys; removal requires another key's fresh
assertion, and the final key cannot be removed.

Authentication uses **Malaber FastPasskey 0.2.6**, the same pinned wheel and browser
module as Tracy, Planini, and Onionary. Django adapts the framework-neutral core;
no copied WebAuthn implementation or FastAPI rewrite. Ceremonies are expiring,
session-bound, and consumed once in the database. Browser mutations require CSRF.

Production environment:

```sh
export APP_BASE_URL=https://postcard.example.com
export SECRET_KEY='<generate a long random secret>'
export DEBUG=false
export DATABASE_PATH=/persistent/postcard.sqlite3
export MEDIA_ROOT=/persistent/media
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
```

Serve `config.wsgi:application` or `config.asgi:application` with your production
server behind HTTPS. Serve `staticfiles/` at `/static/`. **Do not expose `MEDIA_ROOT`
through a public static alias**: photos are served through token-scoped Django
routes. Set proxy Host to the configured hostname and preserve HTTPS origin.
`APP_BASE_URL` must be an origin, with no path, query, or fragment. Changing the
relying-party hostname makes old passkeys unavailable at the new hostname.

Viewer URLs are bearer secrets; anyone holding one can see that viewer's active
photos. Link rotation invalidates old URLs, including photo URLs. Players poll
for changes every five seconds and advance every fifteen seconds. While offline,
the last loaded photo remains visible; there is no persistent offline cache.
Already downloaded images cannot be remotely recalled. Native uploads convert
HEIC and other system-supported formats to JPEG; the server validates, resizes,
and strips metadata before storing. Limits: 20 selected photos, 25 MB/upload,
40 megapixels/server input, 255-character captions. Web uploads use the same
normalization. Back up the database and media together.

## iOS

See [iOS guide](ios/Postcard/README.md). Bundle ID and App Store Connect SKU:
**`de.malaber.postcard`**. iPhone/iPad, iOS 17+.

```sh
bash ios/Postcard/Scripts/test.sh
bash ios/Postcard/Scripts/upload_testflight.sh 0.1.0 1
```

TestFlight upload requires the App Store Connect record you will create later.
No upload or Apple record creation is performed by setup.

## Verification

```sh
uv run python manage.py test
npm ci
npx playwright install chromium
npm run test:e2e
bash ios/Postcard/Scripts/test.sh
```

GitHub Actions runs both browser and iOS E2E on pushes and PRs. Browser E2E uses
Malaber's virtual authenticator against real Django: passkey registration/login,
PKCE handoff, upload, actual viewer image rendering, hiding, rotation, deletion,
and token revocation. Native XCTest uses a real isolated backend and token minted
by a CLI fixture; only OS passkey prompts and the Photos picker are bypassed.
The fixture upload button and token injection exist only in Debug. This is not a
claim of automated iCloud/Face ID or system photo-picker testing. Simulator tests
exercise native viewer creation, JPEG upload, caption edit, link replacement,
and deletion. Results and screenshots are retained as CI artifacts.
