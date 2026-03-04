#!/bin/bash
# Create the read-only public app database user, grant view permissions,
# and generate the .env.public file with a random password.
#
# Reads DB_HOST, DB_PORT, and DB_NAME from .env to keep settings consistent.
# Pre-existing environment variables take precedence over .env values.
#
# Usage: ./scripts/setup_public_user.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env as defaults (existing env vars take precedence)
if [ -f "$PROJECT_DIR/.env" ]; then
    while IFS='=' read -r key value; do
        [[ -z "$key" || "$key" =~ ^# ]] && continue
        if [ -z "${!key+x}" ]; then
            export "$key=$value"
        fi
    done < "$PROJECT_DIR/.env"
else
    echo "Error: .env file not found in $PROJECT_DIR"
    exit 1
fi

DB_USER="${DB_USER:-KantinePOS}"
DB_NAME="${DB_NAME:-KantinePOS}"
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"

# Generate a random password for the public user
PUBLIC_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
PUBLIC_USER="kiosk_public"

echo "Setting up '$PUBLIC_USER' on database '$DB_NAME' (user: $DB_USER)..."

# Wait for the database to be ready
echo "Waiting for database..."
for i in $(seq 1 10); do
    if docker exec kiosk-db-1 psql -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT 1" > /dev/null 2>&1; then
        break
    fi
    if [ "$i" -eq 10 ]; then
        echo "Error: Database not ready after 10 attempts"
        exit 1
    fi
    sleep 1
done

# Wait for the main app to be healthy (it creates the views on startup)
echo "Waiting for main app to create views..."
for i in $(seq 1 15); do
    VIEW_COUNT=$(docker exec kiosk-db-1 psql -U "${DB_USER}" -d "${DB_NAME}" -tAc \
        "SELECT count(*) FROM pg_views WHERE schemaname='public' AND viewname IN ('mowinghistory','lastmowed','maintenancestatus');" 2>/dev/null || echo "0")
    if [ "$VIEW_COUNT" -eq 3 ]; then
        break
    fi
    if [ "$i" -eq 15 ]; then
        echo "Warning: Views not found after 15 seconds. Make sure the main app has started."
        echo "You can re-run this script after the app is running to grant view permissions."
        exit 1
    fi
    sleep 1
done

docker exec -i kiosk-db-1 psql -U "${DB_USER}" -d "${DB_NAME}" <<SQL
-- Create or update the read-only role
DO
\$do\$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = '${PUBLIC_USER}') THEN
      CREATE ROLE ${PUBLIC_USER} WITH LOGIN PASSWORD '${PUBLIC_PASSWORD}';
   ELSE
      ALTER ROLE ${PUBLIC_USER} WITH PASSWORD '${PUBLIC_PASSWORD}';
   END IF;
END
\$do\$;

-- Grant connect to the database
GRANT CONNECT ON DATABASE "${DB_NAME}" TO ${PUBLIC_USER};

-- Grant usage on the public schema
GRANT USAGE ON SCHEMA public TO ${PUBLIC_USER};

-- Grant SELECT privileges to the views used by the public app
GRANT SELECT ON public.mowinghistory TO ${PUBLIC_USER};
GRANT SELECT ON public.lastmowed TO ${PUBLIC_USER};
GRANT SELECT ON public.maintenancestatus TO ${PUBLIC_USER};

-- Ensure future tables do not accidentally inherit privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM ${PUBLIC_USER};
SQL

# Generate .env.public
ENV_PUBLIC="$PROJECT_DIR/.env.public"
cat > "$ENV_PUBLIC" <<EOF
DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
DB_NAME=${DB_NAME}
DB_USER=${PUBLIC_USER}
DB_PASSWORD=${PUBLIC_PASSWORD}
EOF

echo "Created $ENV_PUBLIC"
echo "Done. Restart the public_app container to apply: docker compose restart public_app"
