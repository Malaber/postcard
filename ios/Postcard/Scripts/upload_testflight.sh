#!/usr/bin/env bash
set -euo pipefail
package_dir=$(cd "$(dirname "$0")/.." && pwd)
version=${1:-}
build=${2:-}
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ || ! "$build" =~ ^[1-9][0-9]*$ ]]; then
  echo "Usage: $0 <version, e.g. 0.1.0> <unique positive build number>" >&2; exit 2
fi
# Test before every upload. App Store Connect record must already exist.
bash "$package_dir/Scripts/test.sh"
release_dir=$(mktemp -d "${TMPDIR:-/tmp}/postcard-release.XXXXXX")
archive="$release_dir/Postcard.xcarchive"
cd "$package_dir"
xcodegen generate
auth=()
# Optional App Store Connect API key allows fully unattended CLI signing/upload.
if [[ -n "${ASC_KEY_PATH:-}" ]]; then
  : "${ASC_KEY_ID:?Set ASC_KEY_ID}" "${ASC_ISSUER_ID:?Set ASC_ISSUER_ID}"
  auth=(-authenticationKeyPath "$ASC_KEY_PATH" -authenticationKeyID "$ASC_KEY_ID" -authenticationKeyIssuerID "$ASC_ISSUER_ID")
fi
env PATH=/usr/bin:/bin:/usr/sbin:/sbin /usr/bin/xcodebuild \
  -project Postcard.xcodeproj -scheme Postcard -configuration Release \
  -destination 'generic/platform=iOS' -archivePath "$archive" \
  DEVELOPMENT_TEAM=VWKG94374J PRODUCT_BUNDLE_IDENTIFIER=de.malaber.postcard \
  MARKETING_VERSION="$version" CURRENT_PROJECT_VERSION="$build" \
  CODE_SIGN_STYLE=Automatic -allowProvisioningUpdates ${auth[@]+"${auth[@]}"} archive
env PATH=/usr/bin:/bin:/usr/sbin:/sbin /usr/bin/xcodebuild \
  -exportArchive -archivePath "$archive" -exportPath "$release_dir/export" \
  -exportOptionsPlist "$package_dir/ExportOptions.TestFlight.plist" \
  -allowProvisioningUpdates ${auth[@]+"${auth[@]}"}
echo "Upload accepted; Apple processing still pending. Archive: $archive"
