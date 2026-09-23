#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
release=${1:?release required}
mode=${2:-deploy}
[[ "$release" =~ ^inputs-20260923-[0-9a-f]{7}$ ]]
[[ "$mode" = deploy || "$mode" = build-only ]]
app=/opt/hengxin-smart-image
work=/opt/hengxin-releases/$release
src=$work/src
backup=/opt/hengxin-backups/$release
image=hengxin-smart-image-backend:$release
helper=$src/scripts/release/image-inputs-worker.py
native=$app/backend
wait_seconds=${DRAIN_WAIT_SECONDS:-1800}
[[ "$wait_seconds" =~ ^[0-9]+$ ]]
cd "$app/infra"
# Actual live overlays, not stale API_RELEASE metadata. Assert against live config below.
old=(docker compose -f compose.yaml -f compose.vps.yaml -f compose.api-image.yaml
  -f /opt/hengxin-releases/three-fixes-20260923/api-override.yaml
  -f /opt/hengxin-releases/cli-two-hour-20260923/api-override.yaml)
new=("${old[@]}" -f "$work/api-override.yaml")
sql() { docker exec hengxin-vps-staging-postgres-1 psql -v ON_ERROR_STOP=1 -U hengxin -d hengxin -Atc "$1"; }
api_control() { docker exec -i hengxin-vps-staging-api-image-worker-1 python - "$1" "$wait_seconds" < "$helper"; }
python3 - "$src" "$work/api-override.yaml" "$image" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]); manifest=json.loads((root/'release.json').read_text())
assert manifest['files'], 'Empty manifest'
for name,digest in manifest['files'].items():
    path=root/name
    assert path.resolve().is_relative_to(root.resolve()),name
    assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
services={name:{'image':sys.argv[3],'build':{'context':str(root),'dockerfile':'infra/Dockerfile.backend'}} for name in ('api','migrate','outbox','api-image-worker','api-image-outbox')}
Path(sys.argv[2]).write_text(json.dumps({'services':services},indent=2))
print('PACKAGE_HASHES_OK',len(manifest['files']))
PY
test -f "$helper"
"${old[@]}" config --format json > "$work/old-compose.private.json"
python3 - "$work/old-compose.private.json" <<'PY'
import json,subprocess,sys
services=json.load(open(sys.argv[1]))['services']
for name in ('api','outbox','api-image-worker','api-image-outbox'):
    live=json.loads(subprocess.check_output(['docker','inspect',f'hengxin-vps-staging-{name}-1']))[0]
    spec=services[name]; config=live['Config']
    assert live['State']['Running'],name
    assert config['Image']==spec['image'],f'Live image differs: {name}'
    env=dict(value.split('=',1) for value in config['Env'])
    assert all(env.get(key)==str(value) for key,value in spec.get('environment',{}).items()),f'Live environment differs: {name}'
    if spec.get('command'):
        assert spec['command']==config['Cmd'],f'Live command differs: {name}'
print('LIVE_CONFIGURATION_MATCHES')
PY
"${new[@]}" config --quiet
docker build -f "$src/infra/Dockerfile.backend" -t "$image" "$src"
docker run --rm --network none --entrypoint python "$image" -m compileall -q app migrations
if [[ "$mode" = build-only ]]; then echo BUILD_COMPLETE; exit 0; fi
# Operator must run installation tests on this exact image before service interruption.
test "$(cat "$work/INSTALL_TEST_IMAGE_ID")" = "$(docker image inspect --format '{{.Id}}' "$image")"
test ! -e "$backup"
test "$(sql 'select version_num from alembic_version')" = 0016
paused=$(sql 'select paused from api_image_channel where id=1')
[[ "$paused" = f ]]
# Refuse before interruption if queued/uncertain work cannot drain with dispatch paused.
test "$(sql "SELECT (SELECT count(*) FROM api_image_tasks WHERE state NOT IN ('succeeded','failed','partial_failed')) + (SELECT count(*) FROM api_image_items WHERE state NOT IN ('succeeded','failed'))")" = 0
pid=$(systemctl show hengxin-vps-codex-worker -p MainPID --value)
test "$(readlink "/proc/$pid/cwd")" = "$native"
install -d -m 0700 "$backup"
closed=0; migrated=0; native_changed=0; native_stopped=0; backed=0
recover() {
  code=$?
  if [[ "$code" = 0 ]]; then code=1; fi
  trap - ERR INT TERM
  set +e
  if [[ "$closed" = 1 ]]; then
    "${new[@]}" stop -t 30 web api outbox api-image-outbox
    sql "update api_image_channel set paused=true where id=1"
    if [[ "$migrated" = 1 ]] && [[ "$(docker inspect --format '{{.State.Running}}' hengxin-vps-staging-api-image-worker-1)" = true ]]; then
      api_control api-drain || { echo ROLLBACK_BLOCKED_API_BUSY; exit "$code"; }
      "${new[@]}" stop -t 30 api-image-worker
    fi
    if [[ "$native_changed" = 1 ]]; then
      if systemctl is-active --quiet hengxin-vps-codex-worker; then
        python3 "$helper" run-native-stop "$wait_seconds" || { echo ROLLBACK_BLOCKED_NATIVE_BUSY; exit "$code"; }
      fi
      tar -xpf "$backup/native.tar" -C "$native"
      if [[ -f "$backup/native-new-file-absent" ]]; then rm -f "$native/app/image_revision_prompt.py"; fi
    fi
    if [[ "$native_stopped" = 1 ]]; then systemctl start hengxin-vps-codex-worker; fi
    if [[ "$backed" = 1 ]]; then tar -xpf "$backup/application.tar" -C "$app"; fi
    if [[ -f "$backup/NATIVE_IMAGE_INPUTS_RELEASE.json" ]]; then
      cp -p "$backup/NATIVE_IMAGE_INPUTS_RELEASE.json" "$app/"
    elif [[ "$native_changed" = 1 ]]; then
      rm -f "$app/NATIVE_IMAGE_INPUTS_RELEASE.json"
    fi
    # No downgrade, database restore or forced worker stop. New requests stay closed after migration.
    api_control api-resume >/dev/null 2>&1
    "${old[@]}" up -d --no-deps api-image-worker api-image-outbox outbox
    if [[ "$migrated" = 0 ]]; then
      sql "update api_image_channel set paused=false where id=1"
      "${old[@]}" up -d --no-deps --wait api web
      docker exec hengxin-vps-staging-web-1 nginx -s reload
    else
      sql "update api_image_channel set paused=true where id=1"
      "${old[@]}" create --no-deps api
      echo ROLLBACK_OLD_CODE_RESTORED_HTTP_CLOSED_DATABASE_PRESERVED
    fi
  fi
  echo "DEPLOY_FAILED backup=$backup"
  exit "$code"
}
trap recover ERR INT TERM
closed=1
"${old[@]}" stop -t 30 web api outbox api-image-outbox
sql "update api_image_channel set paused=true where id=1"
api_control api-drain
"${old[@]}" stop -t 30 api-image-worker
python3 "$helper" run-native-stop "$wait_seconds"
native_stopped=1
cp -p "$work/old-compose.private.json" "$backup/old-compose.private.json"
docker inspect --format '{{.Name}} {{.Config.Image}} {{.Image}}' \
  hengxin-vps-staging-api-1 hengxin-vps-staging-outbox-1 \
  hengxin-vps-staging-api-image-worker-1 hengxin-vps-staging-api-image-outbox-1 > "$backup/actual-images.txt"
docker exec hengxin-vps-staging-postgres-1 pg_dump -U hengxin -d hengxin -Fc > "$backup/database.dump"
test -s "$backup/database.dump"
docker exec -i hengxin-vps-staging-postgres-1 pg_restore --list < "$backup/database.dump" > "$backup/database-list.txt"
test -s "$backup/database-list.txt"
tar -C "$app" -cpf "$backup/application.tar" frontend/dist frontend/package.json API_RELEASE.json API_IMAGE_RELEASE.json FRONTEND_RELEASE.json
if [[ -f "$app/NATIVE_IMAGE_INPUTS_RELEASE.json" ]]; then cp -p "$app/NATIVE_IMAGE_INPUTS_RELEASE.json" "$backup/"; fi
files=(app/execution/prompts.py)
if [[ -f "$native/app/image_revision_prompt.py" ]]; then files+=(app/image_revision_prompt.py); else touch "$backup/native-new-file-absent"; fi
tar -C "$native" -cpf "$backup/native.tar" "${files[@]}"
backed=1
echo BACKUP_COMPLETE
# Set before migration: any failure may have committed schema changes.
migrated=1
"${new[@]}" run --rm --no-deps migrate
test "$(sql 'select version_num from alembic_version')" = 0017
native_changed=1
python3 - "$src" "$native" <<'PY'
import os,shutil,sys
from pathlib import Path
source,target=map(Path,sys.argv[1:])
for name in ('app/execution/prompts.py','app/image_revision_prompt.py'):
    dest=target/name; temporary=dest.with_suffix('.release-new')
    stat=dest.stat() if dest.exists() else (target/'app/execution/prompts.py').stat()
    shutil.copyfile(source/'backend'/name,temporary)
    os.chown(temporary,stat.st_uid,stat.st_gid); os.chmod(temporary,stat.st_mode & 0o777)
    os.replace(temporary,dest)
PY
systemctl start hengxin-vps-codex-worker
python3 "$helper" run-native-verify 90
"${new[@]}" up -d --no-deps --wait api
"${new[@]}" up -d --no-deps api-image-worker outbox api-image-outbox
sleep 5
api_control api-verify
curl --retry 5 --retry-delay 2 -fsS http://127.0.0.1:18008/api/v1/health/ready
python3 "$src/scripts/release/image-inputs-frontend.py" "$src" "$app" "$work/api-override.yaml"
sql "update api_image_channel set paused=false where id=1"
"${new[@]}" up -d --no-deps --wait web
docker exec hengxin-vps-staging-web-1 nginx -s reload
curl --retry 5 --retry-delay 2 -fsS http://127.0.0.1:18080/ >/dev/null
trap - ERR INT TERM
echo "DEPLOY_COMPLETE backup=$backup image=$image"
