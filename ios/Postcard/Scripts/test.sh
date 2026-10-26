#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$root"
work=$(mktemp -d "${TMPDIR:-/tmp}/postcard-ios.XXXXXX")
export DATABASE_PATH="$work/db.sqlite3" MEDIA_ROOT="$work/media"
python=${PYTHON:-"$root/.venv/bin/python"}
port=$("$python" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')
export APP_BASE_URL="http://localhost:$port" DEBUG=true
server_pid=''
cleanup() {
  if [[ -n "$server_pid" ]]; then kill "$server_pid" 2>/dev/null || true; wait "$server_pid" 2>/dev/null || true; fi
  mkdir -p "$root/test-results"
  if [[ -f "$work/backend.log" ]]; then cp "$work/backend.log" "$root/test-results/ios-backend.log"; fi
  rm -f "$root/ios/Postcard/UITests/Fixture.json"
  rm -rf "$work"
}
trap cleanup EXIT
"$python" manage.py migrate --noinput
PYTHONPATH="$root" "$python" scripts/ios-fixture.py
"$python" manage.py runserver "127.0.0.1:$port" --noreload > "$work/backend.log" 2>&1 &
server_pid=$!
for attempt in {1..60}; do
  if ! kill -0 "$server_pid" 2>/dev/null; then cat "$work/backend.log"; exit 1; fi
  if curl --silent --fail "$APP_BASE_URL/" > /dev/null; then break; fi
  if [[ "$attempt" == 60 ]]; then cat "$work/backend.log"; exit 1; fi
  sleep 0.5
done
if [[ -z "${SIMULATOR_ID:-}" ]]; then
  SIMULATOR_ID=$(xcrun simctl list devices available -j | "$python" -c 'import json,sys; devices=json.load(sys.stdin)["devices"]; print(next(d["udid"] for group in devices.values() for d in group if d["name"].startswith("iPhone")))')
fi
cd ios/Postcard
xcodegen generate
mkdir -p "$root/test-results"
xcodebuild -project Postcard.xcodeproj -scheme Postcard -configuration Debug \
  -destination "platform=iOS Simulator,id=$SIMULATOR_ID" \
  -derivedDataPath "$work/build" -resultBundlePath "$root/test-results/ios-$(date +%s).xcresult" \
  -parallel-testing-enabled NO -maximum-concurrent-test-simulator-destinations 1 \
  CODE_SIGNING_ALLOWED=NO test
