-- Create a new read-only role for the public app
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

-- Grant SELECT privileges strictly to the necessary tables
GRANT SELECT ON public.mowingactivities TO kiosk_public;
GRANT SELECT ON public.mowingsections TO kiosk_public;
GRANT SELECT ON public.mowingmaintenance TO kiosk_public;
GRANT SELECT ON public.customers TO kiosk_public;

-- Optional: ensure future tables do not accidentally inherit privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM kiosk_public;
