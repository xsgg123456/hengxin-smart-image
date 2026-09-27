#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
release=${1:?release required}
mode=${2:-deploy}
[[ "$release" =~ ^delivery-20260927-[0-9a-f]{7}$ ]]
[[ "$mode" = deploy || "$mode" = build-only ]]
app=/opt/hengxin-smart-image
work=/opt/hengxin-releases/$release
src=$work/src
backup=/opt/hengxin-backups/$release
native=$app/backend
image=hengxin-smart-image-backend:$release
helper=$src/scripts/release/image-inputs-worker.py
native_helper=$src/scripts/release/delivery-native.py
wait_seconds=${DRAIN_WAIT_SECONDS:-1800}
[[ "$wait_seconds" =~ ^[0-9]+$ ]]
cd "$app/infra"
old=(docker compose -f compose.yaml -f compose.vps.yaml -f compose.api-image.yaml
  -f /opt/hengxin-releases/three-fixes-20260923/api-override.yaml
  -f /opt/hengxin-releases/cli-two-hour-20260923/api-override.yaml
  -f /opt/hengxin-releases/inputs-20260923-b2841c7/api-override.yaml
  -f /opt/hengxin-releases/annotation-20260924-6b43b3c/api-override.yaml
  -f /opt/hengxin-releases/materials-20260924-e3c60c9/api-override.yaml
  -f /opt/hengxin-releases/materials-20260924-2cdb4ff/api-override.yaml)
new=("${old[@]}" -f "$work/api-override.yaml")
sql() { docker exec hengxin-vps-staging-postgres-1 psql -v ON_ERROR_STOP=1 -U hengxin -d hengxin -Atc "$1"; }
api_control() { docker exec -i hengxin-vps-staging-api-image-worker-1 python - "$1" "$wait_seconds" < "$helper"; }
python3 - "$src" "$work/api-override.yaml" "$image" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]); manifest=json.loads((root/'release.json').read_text())
assert manifest['files'] and manifest['backendOnly'] is True
for name,digest in manifest['files'].items():
    path=root/name
    assert path.resolve().is_relative_to(root.resolve()) and not path.is_symlink(),name
    assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
services={name:{'image':sys.argv[3],'build':{'context':str(root),'dockerfile':'infra/Dockerfile.backend'}} for name in ('api','migrate','outbox','api-image-worker','api-image-outbox')}
Path(sys.argv[2]).write_text(json.dumps({'services':services},indent=2))
print('PACKAGE_HASHES_OK',len(manifest['files']))
PY
"${old[@]}" config --format json > "$work/old-compose.private.json"
verify_old() {
python3 - "$work/old-compose.private.json" <<'PY'
import json,subprocess,sys
services=json.load(open(sys.argv[1]))['services']
for name in ('api','outbox','api-image-worker','api-image-outbox'):
    live=json.loads(subprocess.check_output(['docker','inspect',f'hengxin-vps-staging-{name}-1']))[0]
    spec=services[name]; config=live['Config']
    assert live['State']['Running'] and config['Image']==spec['image'],name
    assert config['Image']=='hengxin-smart-image-backend:materials-20260924-2cdb4ff',name
    env=dict(value.split('=',1) for value in config['Env'])
    assert all(env.get(k)==str(v) for k,v in spec.get('environment',{}).items()),name
    assert not spec.get('command') or spec['command']==config['Cmd'],name
print('LIVE_CONFIGURATION_MATCHES')
PY
}
verify_old
"${new[@]}" config --quiet
if [[ "$mode" = build-only ]]; then
  docker build -f "$src/infra/Dockerfile.backend" -t "$image" "$src"
  # Download only the two added pure-Python dependencies, verify against the lock.
  python3 - "$src/backend/uv.lock" "$work/wheels" <<'PY'
import hashlib,sys,tomllib,urllib.request
from pathlib import Path
lock=tomllib.loads(Path(sys.argv[1]).read_text()); dest=Path(sys.argv[2]); dest.mkdir(exist_ok=True)
for package in lock['package']:
    if package['name'] not in ('markdown-it-py','mdurl'): continue
    wheel=next(w for w in package['wheels'] if w['url'].endswith('py3-none-any.whl'))
    raw=urllib.request.urlopen(wheel['url'],timeout=60).read()
    assert 'sha256:'+hashlib.sha256(raw).hexdigest()==wheel['hash']
    (dest/wheel['url'].rsplit('/',1)[1]).write_bytes(raw)
print('NATIVE_DEPENDENCIES_VERIFIED')
PY
  docker run --rm --network none --entrypoint python "$image" -m compileall -q app migrations
  echo BUILD_COMPLETE
  exit 0
fi
test "$(cat "$work/INSTALL_TEST_IMAGE_ID")" = "$(docker image inspect --format '{{.Id}}' "$image")"
test ! -e "$backup"
test "$(sql 'select version_num from alembic_version')" = 0017
test "$(sql 'select paused from api_image_channel where id=1')" = f
test "$(sql "SELECT (SELECT count(*) FROM api_image_tasks WHERE state NOT IN ('succeeded','failed','partial_failed')) + (SELECT count(*) FROM api_image_items WHERE state NOT IN ('succeeded','failed'))")" = 0
test "$(sql "SELECT count(*) FROM job_records WHERE status NOT IN ('succeeded','partial','failed','cancelled')")" = 0
pid=$(systemctl show hengxin-vps-codex-worker -p MainPID --value)
test "$(readlink "/proc/$pid/cwd")" = "$native"
install -d -m 0700 "$backup"
closed=0; native_stopped=0; native_changed=0; api_started=0
recover() {
  code=$?; if [[ "$code" = 0 ]]; then code=1; fi
  trap - ERR INT TERM
  set +e
  blocked() {
    "${new[@]}" stop -t 30 web api outbox api-image-outbox >/dev/null 2>&1
    sql 'update api_image_channel set paused=true where id=1' >/dev/null 2>&1
    echo "ROLLBACK_BLOCKED_INTAKE_REMAINS_CLOSED backup=$backup"
    exit "$code"
  }
  if [[ "$closed" = 1 ]]; then
    "${new[@]}" stop -t 30 web api outbox api-image-outbox || blocked
    sql 'update api_image_channel set paused=true where id=1' || blocked
    if [[ "$api_started" = 1 ]]; then
      running=$(docker inspect --format '{{.State.Running}}' hengxin-vps-staging-api-image-worker-1) || blocked
      if [[ "$running" = true ]]; then api_control api-drain || blocked; fi
      "${new[@]}" stop -t 30 api-image-worker || blocked
    fi
    if [[ "$native_changed" = 1 ]]; then
      state=$(systemctl show hengxin-vps-codex-worker -p ActiveState --value) || blocked
      case "$state" in
        active) python3 "$helper" run-native-stop "$wait_seconds" || blocked ;;
        inactive|failed) ;;
        *) blocked ;;
      esac
      python3 "$native_helper" restore "$native" "$backup" || blocked
    fi
    if [[ "$native_stopped" = 1 ]]; then systemctl start hengxin-vps-codex-worker || blocked; fi
    "${old[@]}" up -d --no-deps --wait api api-image-worker outbox api-image-outbox || blocked
    verify_old || blocked
    api_control api-resume || blocked
    api_control api-verify || blocked
    python3 "$helper" run-native-verify 90 || blocked
    curl --retry 5 --retry-delay 2 -fsS http://127.0.0.1:18008/api/v1/health/ready || blocked
    sql 'update api_image_channel set paused=false where id=1' || blocked
    "${old[@]}" up -d --no-deps --wait web || blocked
    docker exec hengxin-vps-staging-web-1 nginx -s reload || blocked
  fi
  echo "DEPLOY_FAILED_ROLLED_BACK backup=$backup"
  exit "$code"
}
trap recover ERR INT TERM
closed=1
"${old[@]}" stop -t 30 web api outbox api-image-outbox
sql 'update api_image_channel set paused=true where id=1'
api_control api-drain
"${old[@]}" stop -t 30 api-image-worker
native_stopped=1
python3 "$helper" run-native-stop "$wait_seconds"
cp -p "$work/old-compose.private.json" "$backup/old-compose.private.json"
docker inspect --format '{{.Name}} {{.Config.Image}} {{.Image}}' hengxin-vps-staging-api-1 \
  hengxin-vps-staging-outbox-1 hengxin-vps-staging-api-image-worker-1 \
  hengxin-vps-staging-api-image-outbox-1 > "$backup/actual-images.txt"
docker exec hengxin-vps-staging-postgres-1 pg_dump -U hengxin -d hengxin -Fc > "$backup/database.dump"
test -s "$backup/database.dump"
docker exec -i hengxin-vps-staging-postgres-1 pg_restore --list < "$backup/database.dump" > "$backup/database-list.txt"
python3 "$native_helper" backup "$native" "$backup"
echo BACKUP_COMPLETE
native_changed=1
python3 "$native_helper" install "$src" "$native"
(umask 022; uv pip install --python "$native/.venv/bin/python" --no-deps --no-index --link-mode copy "$work"/wheels/*.whl)
uv pip check --python "$native/.venv/bin/python"
(cd "$native"; runuser -u codex -- "$native/.venv/bin/python" -c 'import markdown_it; assert markdown_it.__version__ == "4.0.0"; from app.execution import delivery_acceptance,delivery_storage; from app.worker import reconcile')
systemctl start hengxin-vps-codex-worker
python3 "$helper" run-native-verify 90
"${new[@]}" up -d --no-deps --wait api
api_started=1
"${new[@]}" up -d --no-deps api-image-worker outbox api-image-outbox
sleep 5
api_control api-verify
curl --retry 5 --retry-delay 2 -fsS http://127.0.0.1:18008/api/v1/health/ready
test "$(sql 'select version_num from alembic_version')" = 0017
sql 'update api_image_channel set paused=false where id=1'
"${new[@]}" up -d --no-deps --wait web
docker exec hengxin-vps-staging-web-1 nginx -s reload
curl --retry 5 --retry-delay 2 -fsS http://127.0.0.1:18080/ >/dev/null
trap - ERR INT TERM
echo "DEPLOY_COMPLETE backup=$backup image=$image"
