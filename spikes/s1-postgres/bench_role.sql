-- SPDX-License-Identifier: AGPL-3.0-or-later
-- S1: role of the "norls" variant only (docs/spikes/S1.md §3.4). It bypasses row-level
-- security so that the same queries can be timed without the policies. Never created by the
-- product. Run by a superuser after generate.py; :'password' is a psql variable.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'otlet_bench') THEN
        CREATE ROLE otlet_bench LOGIN BYPASSRLS;
    END IF;
END
$$;
ALTER ROLE otlet_bench LOGIN BYPASSRLS PASSWORD :'password';
GRANT CONNECT ON DATABASE otlet TO otlet_bench;
GRANT USAGE ON SCHEMA public TO otlet_bench;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO otlet_bench;
