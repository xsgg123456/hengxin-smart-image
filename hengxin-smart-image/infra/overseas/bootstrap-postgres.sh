#!/bin/sh
set -eu
if [ "$OVERSEAS_POSTGRES_PASSWORD" = "$OVERSEAS_OWNER_PASSWORD" ] || \
   [ "$OVERSEAS_POSTGRES_PASSWORD" = "$OVERSEAS_APP_PASSWORD" ] || \
   [ "$OVERSEAS_OWNER_PASSWORD" = "$OVERSEAS_APP_PASSWORD" ]; then
  echo 'PostgreSQL administrator, owner and app passwords must differ' >&2
  exit 1
fi
export PGPASSWORD="$OVERSEAS_POSTGRES_PASSWORD"
psql -h overseas-postgres -U postgres -d "$OVERSEAS_POSTGRES_DB" -v ON_ERROR_STOP=1 \
  -v db="$OVERSEAS_POSTGRES_DB" -v owner_password="$OVERSEAS_OWNER_PASSWORD" \
  -v app_password="$OVERSEAS_APP_PASSWORD" <<'SQL'
SELECT 'CREATE ROLE overseas_owner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname='overseas_owner') \gexec
SELECT 'CREATE ROLE overseas_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname='overseas_app') \gexec
ALTER ROLE overseas_owner PASSWORD :'owner_password';
ALTER ROLE overseas_app PASSWORD :'app_password';
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO overseas_owner, overseas_app;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO overseas_owner;
GRANT USAGE ON SCHEMA public TO overseas_app;
ALTER DEFAULT PRIVILEGES FOR ROLE overseas_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO overseas_app;
ALTER DEFAULT PRIVILEGES FOR ROLE overseas_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO overseas_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO overseas_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO overseas_app;
SELECT 'REVOKE INSERT, UPDATE, DELETE ON overseas_alembic_version FROM overseas_app'
WHERE to_regclass('public.overseas_alembic_version') IS NOT NULL \gexec
SQL
