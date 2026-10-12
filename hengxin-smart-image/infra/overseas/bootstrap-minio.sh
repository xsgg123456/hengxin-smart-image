#!/bin/sh
set -eu
if [ "$OVERSEAS_MINIO_ROOT_USER" = "$OVERSEAS_MINIO_ACCESS_KEY" ] || \
   [ "$OVERSEAS_MINIO_ROOT_PASSWORD" = "$OVERSEAS_MINIO_SECRET_KEY" ]; then
  echo 'MinIO root and application credentials must differ' >&2
  exit 1
fi
case "$OVERSEAS_MINIO_BUCKET" in *[!a-z0-9.-]*|'') echo 'Invalid bucket name' >&2; exit 1;; esac
mc alias set overseas http://overseas-minio:9000 "$OVERSEAS_MINIO_ROOT_USER" "$OVERSEAS_MINIO_ROOT_PASSWORD" >/dev/null
mc mb --ignore-existing "overseas/$OVERSEAS_MINIO_BUCKET" >/dev/null
mc anonymous set none "overseas/$OVERSEAS_MINIO_BUCKET" >/dev/null
mc admin user add overseas "$OVERSEAS_MINIO_ACCESS_KEY" "$OVERSEAS_MINIO_SECRET_KEY" >/dev/null
cat > /tmp/overseas-policy.json <<EOF
{"Version":"2012-10-17","Statement":[
 {"Effect":"Allow","Action":["s3:GetBucketLocation","s3:ListBucket","s3:ListBucketMultipartUploads","s3:GetBucketPolicy"],"Resource":["arn:aws:s3:::$OVERSEAS_MINIO_BUCKET"]},
 {"Effect":"Allow","Action":["s3:GetObject","s3:PutObject","s3:DeleteObject","s3:AbortMultipartUpload","s3:ListMultipartUploadParts"],"Resource":["arn:aws:s3:::$OVERSEAS_MINIO_BUCKET/*"]}
]}
EOF
mc admin policy create overseas overseas-app /tmp/overseas-policy.json >/dev/null
mc admin policy attach overseas overseas-app --user "$OVERSEAS_MINIO_ACCESS_KEY" >/dev/null
