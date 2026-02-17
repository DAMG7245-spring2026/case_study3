-- ============================================================
-- Snowflake: Create signal_raw_collections table
-- Run this script in Snowflake (Worksheets or SnowSQL).
-- Adjust USE DATABASE/SCHEMA to your environment.
-- ============================================================

-- Optional: set your database and schema (uncomment and edit)
-- USE DATABASE your_database;
-- USE SCHEMA your_schema;

CREATE TABLE IF NOT EXISTS signal_raw_collections (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL,
    category VARCHAR(30) NOT NULL,
    collected_at TIMESTAMP_NTZ NOT NULL,
    payload VARIANT NOT NULL,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    UNIQUE(company_id, category)
);

-- Optional: verify
-- DESC TABLE signal_raw_collections;
