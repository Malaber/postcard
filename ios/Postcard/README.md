# Postcard for iOS

Native SwiftUI app, iOS 17+, iPhone and iPad. Bundle ID and SKU:
`de.malaber.postcard`. Team: `VWKG94374J`, matching the sibling apps.

## Build

Requires Xcode, an installed iOS simulator, XcodeGen 2.38+, and root Python dependencies.

```sh
uv sync --frozen
cd ios/Postcard
xcodegen generate
xcodebuild -project Postcard.xcodeproj -scheme Postcard \
  -sdk iphonesimulator -configuration Debug CODE_SIGNING_ALLOWED=NO build
```

Generated Xcode project is ignored; `project.yml` is the source of truth.
Run `bash ios/Postcard/Scripts/test.sh` from the repository root for real-backend
simulator E2E. Set `SIMULATOR_ID` to choose a device. Tests use isolated temporary
SQLite/media directories and remove their temporary credentials afterward.

## Sign-in and uploads

Choose the deployed server origin on the welcome screen. The default is
`https://postcard.malaber.de`; configure another HTTPS host if deployment differs.
This default does not provision a server. HTTP is accepted only for localhost.
Passkeys run in `ASWebAuthenticationSession` on that server, followed by S256 PKCE,
a random state check, and a fixed `de.malaber.postcard://auth` callback. No bearer
token enters the URL. One-use codes expire after two minutes; native sessions
expire after 30 days. Tokens live in device-only Keychain and sign-out revokes
the server session. Custom domains need no associated-domain entitlement.

Create a viewer, then use Photos to choose up to twenty images and send them to
the selected viewer. System Photos picker grants access only to selected images;
no full-library permission is requested. Partial upload failures report the
successful count; select remaining images to retry. Uploads require the app to
remain active and online; no background retry queue is promised.

## CLI-only TestFlight

Create an iOS App Store Connect app with bundle ID and SKU `de.malaber.postcard`.
Then run:

```sh
bash ios/Postcard/Scripts/upload_testflight.sh 0.1.0 1
```

The script tests, archives Release, signs automatically, and exports directly to
App Store Connect. Use a fresh build number for each upload. Apple account setup
can use the existing Xcode account, or provide an App Store Connect API key:

```sh
export ASC_KEY_PATH=/absolute/path/AuthKey_KEYID.p8
export ASC_KEY_ID=KEYID
export ASC_ISSUER_ID=issuer-uuid
bash ios/Postcard/Scripts/upload_testflight.sh 0.1.0 2
```

API key permissions and local signing credentials must allow provisioning and
App Store distribution. Never commit keys. Successful export means upload
acceptance, not completed Apple processing or review. Archives remain in the
printed temporary directory for export retry. App Store privacy answers must
reflect your deployed server's photo/account processing; the privacy manifest
records local required-reason API use and no tracking SDKs.

## Icon

`Assets.xcassets/AppIcon.appiconset/AppIcon.png` is an opaque 1024×1024 app icon,
generated with the built-in ImageGen tool. Full prompt: [icon prompt](../../docs/icon-prompt.md).
