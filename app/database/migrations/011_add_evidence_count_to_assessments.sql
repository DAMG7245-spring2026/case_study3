-- Migration 011: add evidence_count to assessments
-- Stores the total evidence items (signals + document chunks) used when
-- the assessment was scored, so the UI can display reliability context
-- without re-querying dimension_scores at read time.
ALTER TABLE assessments
    ADD COLUMN IF NOT EXISTS evidence_count INT DEFAULT 0;
