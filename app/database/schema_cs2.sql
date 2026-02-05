-- ============================================
-- Case Study 2: Evidence Collection Schema
-- Snowflake CHECK constraints
-- ============================================

-- USE DATABASE PE_ORG_AIR;
-- USE SCHEMA PUBLIC;

-- ============================================
-- 1. Documents SEC filings metadata
-- ============================================
CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id),
    ticker VARCHAR(10) NOT NULL,
    filing_type VARCHAR(20) NOT NULL,
    filing_date DATE NOT NULL,
    source_url VARCHAR(500),
    local_path VARCHAR(500),
    s3_key VARCHAR(500),
    content_hash VARCHAR(64),
    word_count INT,
    chunk_count INT,
    status VARCHAR(20) DEFAULT 'pending',
    error_message VARCHAR(1000),
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    processed_at TIMESTAMP_NTZ
);

-- ============================================
-- 2. Document Chunks
-- ============================================
CREATE TABLE IF NOT EXISTS document_chunks (
    id VARCHAR(36) PRIMARY KEY,
    document_id VARCHAR(36) NOT NULL REFERENCES documents(id),
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    section VARCHAR(50),
    start_char INT,
    end_char INT,
    word_count INT,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    UNIQUE (document_id, chunk_index)
);

-- ============================================
-- 3. External Signals 
-- ============================================
CREATE TABLE IF NOT EXISTS external_signals (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id),
    category VARCHAR(30) NOT NULL,
    source VARCHAR(30) NOT NULL,
    signal_date DATE NOT NULL,
    raw_value VARCHAR(500),
    normalized_score DECIMAL(5,2),
    confidence DECIMAL(4,3),
    metadata VARIANT,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ============================================
-- 4. Company Signal Summaries 
-- ============================================
CREATE TABLE IF NOT EXISTS company_signal_summaries (
    company_id VARCHAR(36) PRIMARY KEY REFERENCES companies(id),
    ticker VARCHAR(10) NOT NULL,
    technology_hiring_score DECIMAL(5,2) DEFAULT 0,
    innovation_activity_score DECIMAL(5,2) DEFAULT 0,
    digital_presence_score DECIMAL(5,2) DEFAULT 0,
    leadership_signals_score DECIMAL(5,2) DEFAULT 0,
    composite_score DECIMAL(5,2) DEFAULT 0,
    signal_count INT DEFAULT 0,
    last_updated TIMESTAMP_NTZ
);

-- ============================================
-- 5. Indexes
-- ============================================
CREATE INDEX IF NOT EXISTS idx_documents_company ON documents(company_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_ticker ON documents(ticker);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_signals_company ON external_signals(company_id);
CREATE INDEX IF NOT EXISTS idx_signals_category ON external_signals(category);


SHOW TABLES LIKE '%document%';
SHOW TABLES LIKE '%signal%';

-- ============================================
-- Useful Views
-- ============================================

-- View: Document summary by company
CREATE OR REPLACE VIEW v_company_document_summary AS
SELECT 
    c.id AS company_id,
    c.ticker,
    c.name AS company_name,
    COUNT(DISTINCT d.id) AS document_count,
    SUM(d.chunk_count) AS total_chunks,
    COUNT(DISTINCT CASE WHEN d.filing_type = '10-K' THEN d.id END) AS form_10k_count,
    COUNT(DISTINCT CASE WHEN d.filing_type = '10-Q' THEN d.id END) AS form_10q_count,
    COUNT(DISTINCT CASE WHEN d.filing_type = '8-K' THEN d.id END) AS form_8k_count,
    MAX(d.created_at) AS last_document_date
FROM companies c
LEFT JOIN documents d ON c.id = d.company_id AND d.status != 'failed'
WHERE c.is_deleted = FALSE
GROUP BY c.id, c.ticker, c.name;

-- View: Signal summary by company
CREATE OR REPLACE VIEW v_company_signal_overview AS
SELECT 
    c.id AS company_id,
    c.ticker,
    c.name AS company_name,
    css.technology_hiring_score,
    css.innovation_activity_score,
    css.digital_presence_score,
    css.leadership_signals_score,
    css.composite_score,
    css.signal_count,
    css.last_updated
FROM companies c
LEFT JOIN company_signal_summaries css ON c.id = css.company_id
WHERE c.is_deleted = FALSE;