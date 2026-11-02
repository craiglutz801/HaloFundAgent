-- First-boot roles for the Compose PostgreSQL 17 service.
-- The application role cannot bypass row security. The migrator owns tables.

CREATE ROLE halo_app LOGIN PASSWORD 'halo_app_fixture' NOBYPASSRLS;
CREATE ROLE halo_migrator LOGIN PASSWORD 'halo_migrator_fixture' BYPASSRLS CREATEDB;
CREATE ROLE temporal LOGIN PASSWORD 'temporal' CREATEDB;

CREATE DATABASE halo_fixture OWNER halo_migrator;
CREATE DATABASE halo_fixture_test OWNER halo_migrator;

GRANT CONNECT ON DATABASE halo_fixture TO halo_app;
GRANT CONNECT ON DATABASE halo_fixture_test TO halo_app;
