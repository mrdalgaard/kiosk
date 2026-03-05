-- Kiosk Database Migration Script
-- Version: Initial Pending Migrations
-- Description: Applies pending tweaks for legacy installs. This script is designed to be idempotent.

BEGIN;

DO $$ 
BEGIN
    -- 1. Rename the existing "date" column to "timestamp" and cast it
    -- Only do this if the column actually exists (legacy database)
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'mowingactivities' 
          AND column_name = 'date'
    ) THEN
        ALTER TABLE public.mowingactivities RENAME COLUMN "date" TO "timestamp";
        ALTER TABLE public.mowingactivities ALTER COLUMN "timestamp" TYPE timestamp with time zone USING "timestamp"::timestamp with time zone;
    END IF;
END $$;

-- Update the default value for future inserts to use the current time
ALTER TABLE public.mowingactivities ALTER COLUMN "timestamp" SET DEFAULT now();

-- 2. Create the mowingmaintenance table linking to customers
CREATE TABLE IF NOT EXISTS public.mowingmaintenance
(
    id smallserial NOT NULL,
    maintenance_type character varying(100) COLLATE pg_catalog."default" NOT NULL,
    interval_h real NOT NULL,
    last_maintained_timestamp timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id integer,
    CONSTRAINT mowingmaintenance_pkey PRIMARY KEY (id),
    CONSTRAINT mowingmaintenance_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.customers(customerid)
);

-- 3. Insert the default maintenance schedule records
-- (Wait to run this until AFTER you have seeded the `customers` table with at least user ID 1)
INSERT INTO public.mowingmaintenance (id, maintenance_type, interval_h, last_maintained_timestamp, user_id) VALUES
(1, 'Alle åg-ender på PTO-akslen', 25, CURRENT_TIMESTAMP, 1),
(2, 'PTO-slanger', 80, CURRENT_TIMESTAMP, 1),
(3, 'Hydraulikstempel', 40, CURRENT_TIMESTAMP, 1),
(4, 'Hjulets drejepunkt', 80, CURRENT_TIMESTAMP, 1),
(5, 'Hjulets aksel', 80, CURRENT_TIMESTAMP, 1),
(6, 'Kontrollér oliestanden i gearkasserne', 80, CURRENT_TIMESTAMP, 1),
(7, 'Udskift olien i gearkasserne', 400, CURRENT_TIMESTAMP, 1)
ON CONFLICT (id) DO NOTHING;

-- Reset the auto-increment sequence
SELECT setval('mowingmaintenance_id_seq', (SELECT MAX(id) FROM mowingmaintenance));

-- 4. Add disabled column to mowingsections
ALTER TABLE public.mowingsections ADD COLUMN IF NOT EXISTS disabled boolean NOT NULL DEFAULT false;

-- 5. Link mowingactivities foreign key directly to customers
ALTER TABLE public.mowingactivities DROP CONSTRAINT IF EXISTS mowingactivities_user_id_fkey;
ALTER TABLE public.mowingactivities ADD CONSTRAINT mowingactivities_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.customers (customerid) MATCH SIMPLE ON UPDATE NO ACTION ON DELETE NO ACTION;

COMMIT;
