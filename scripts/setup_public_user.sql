-- Create a new read-only role for the public app
-- How to run:
-- cat setup_public_user.sql | docker exec -i kiosk-db-1 psql -U KantinePOS -d KantinePOS
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'kiosk_public') THEN
      CREATE ROLE kiosk_public WITH LOGIN PASSWORD 'public_read_only_pw_123';
   END IF;
END
$do$;

-- Connect to the correct database to grant privileges
\c KantinePOS;

-- Grant connect to the database
GRANT CONNECT ON DATABASE "KantinePOS" TO kiosk_public;

-- Grant usage on the public schema
GRANT USAGE ON SCHEMA public TO kiosk_public;

-- Grant SELECT privileges to the views used by the public app
GRANT SELECT ON public.mowinghistory TO kiosk_public;
GRANT SELECT ON public.lastmowed TO kiosk_public;
GRANT SELECT ON public.maintenancestatus TO kiosk_public;

-- Optional: ensure future tables do not accidentally inherit privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM kiosk_public;
