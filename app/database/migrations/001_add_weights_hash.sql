-- Migration 001: Add weights_hash column to dimension_scores
-- Run this against existing Snowflake installs where dimension_scores was created
-- before schema.sql included the weights_hash column.
ALTER TABLE dimension_scores ADD COLUMN IF NOT EXISTS weights_hash VARCHAR(64);
