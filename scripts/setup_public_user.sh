#!/bin/bash
# Create the read-only public app database user and grant view permissions.
# Uses environment variables from .env for database credentials.
#
# Usage: ./scripts/setup_public_user.sh

set -euo pipefail

# Load environment variables from .env
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

DB_USER="${DB_USER:-KantinePOS}"
DB_NAME="${DB_NAME:-KantinePOS}"

echo "Setting up kiosk_public user on database '${DB_NAME}' as user '${DB_USER}'..."

docker exec -i kiosk-db-1 psql -U "${DB_USER}" -d "${DB_NAME}" <<SQL
-- Create the read-only role if it doesn't exist
DO
\$do\$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'kiosk_public') THEN
      CREATE ROLE kiosk_public WITH LOGIN PASSWORD 'public_read_only_pw_123';
   END IF;
END
\$do\$;

-- Grant connect to the database
GRANT CONNECT ON DATABASE "${DB_NAME}" TO kiosk_public;

-- Grant usage on the public schema
GRANT USAGE ON SCHEMA public TO kiosk_public;

-- Grant SELECT privileges to the views used by the public app
GRANT SELECT ON public.mowinghistory TO kiosk_public;
GRANT SELECT ON public.lastmowed TO kiosk_public;
GRANT SELECT ON public.maintenancestatus TO kiosk_public;

-- Ensure future tables do not accidentally inherit privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM kiosk_public;
SQL

echo "Done."
