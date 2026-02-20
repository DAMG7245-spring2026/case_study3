-- =====================================================
-- Industries table
-- =====================================================
CREATE TABLE IF NOT EXISTS industries (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    sector VARCHAR(100) NOT NULL,
    h_r_base DECIMAL(5,2),
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- =====================================================
-- Companies table
-- =====================================================
CREATE TABLE IF NOT EXISTS companies (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    ticker VARCHAR(10),
    industry_id VARCHAR(36),
    position_factor DECIMAL(4,3) DEFAULT 0.0,
    is_deleted BOOLEAN DEFAULT FALSE,
    domain VARCHAR(500),
    careers_url VARCHAR(500),
    news_url VARCHAR(500),
    leadership_url VARCHAR(500),
    glassdoor_company_id VARCHAR(20),
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- =====================================================
-- Assessments table
-- =====================================================
CREATE TABLE IF NOT EXISTS assessments (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL,
    assessment_type VARCHAR(20) NOT NULL,
    assessment_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',
    h_r_score NUMBER(5,2),
    synergy NUMBER(5,2),
    v_r_score DECIMAL(5,2),
    confidence_lower DECIMAL(5,2),
    confidence_upper DECIMAL(5,2),
    evidence_count INT DEFAULT 0,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- =====================================================
-- Dimension scores table
-- =====================================================
CREATE TABLE IF NOT EXISTS dimension_scores (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL,
    dimension VARCHAR(30) NOT NULL,
    score DECIMAL(5,2) NOT NULL,
    total_weight DECIMAL(4,3),
    confidence DECIMAL(4,3) DEFAULT 0.8,
    evidence_count INT DEFAULT 0,
    contributing_sources VARIANT,
    weights_hash VARCHAR(64),
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- =====================================================
-- Signal dimension weights table
-- =====================================================
CREATE TABLE IF NOT EXISTS signal_dimension_weights (
    signal_source  VARCHAR(50)  NOT NULL,
    dimension      VARCHAR(30)  NOT NULL,
    weight         DECIMAL(6,4) NOT NULL,
    is_primary     BOOLEAN      NOT NULL DEFAULT FALSE,
    reliability    DECIMAL(6,4) NOT NULL DEFAULT 0.80,
    updated_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    updated_by     VARCHAR(100) DEFAULT 'system',
    PRIMARY KEY (signal_source, dimension)
);

-- =====================================================
-- Seed data for industries
-- =====================================================
-- Using MERGE to avoid duplicate inserts on re-runs
MERGE INTO industries AS target
USING (
    SELECT '550e8400-e29b-41d4-a716-446655440001' as id, 'Manufacturing' as name, 'Industrials' as sector, 72 as h_r_base UNION ALL
    SELECT '550e8400-e29b-41d4-a716-446655440002', 'Healthcare Services', 'Healthcare', 78 UNION ALL
    SELECT '550e8400-e29b-41d4-a716-446655440003', 'Business Services', 'Services', 75 UNION ALL
    SELECT '550e8400-e29b-41d4-a716-446655440004', 'Retail', 'Consumer', 70 UNION ALL
    SELECT '550e8400-e29b-41d4-a716-446655440005', 'Financial Services', 'Financial', 80 UNION ALL
    SELECT '550e8400-e29b-41d4-a716-446655440006', 'Technology', 'Technology', 85 UNION ALL
    SELECT '550e8400-e29b-41d4-a716-446655440007', 'Energy', 'Energy', 68 UNION ALL
    SELECT '550e8400-e29b-41d4-a716-446655440008', 'Real Estate', 'Real Estate', 65
) AS source
ON target.id = source.id
WHEN NOT MATCHED THEN
    INSERT (id, name, sector, h_r_base)
    VALUES (source.id, source.name, source.sector, source.h_r_base);

-- =====================================================
-- Documents table
-- =====================================================
CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL,
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

-- =====================================================
-- Document chunks table
-- =====================================================
CREATE TABLE IF NOT EXISTS document_chunks (
    id VARCHAR(36) PRIMARY KEY,
    document_id VARCHAR(36) NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    section VARCHAR(50),
    start_char INT,
    end_char INT,
    word_count INT,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- =====================================================
-- External signals table
-- =====================================================
CREATE TABLE IF NOT EXISTS external_signals (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL,
    category VARCHAR(30) NOT NULL,
    source VARCHAR(30) NOT NULL,
    signal_date DATE NOT NULL,
    raw_value VARCHAR(500),
    normalized_score DECIMAL(5,2),
    confidence DECIMAL(4,3),
    metadata VARIANT, -- Snowflake JSON type
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- =====================================================
-- Company signal summary
-- =====================================================
CREATE TABLE IF NOT EXISTS company_signal_summaries (
    company_id VARCHAR(36) PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    technology_hiring_score DECIMAL(5,2),
    innovation_activity_score DECIMAL(5,2),
    digital_presence_score DECIMAL(5,2),
    leadership_signals_score DECIMAL(5,2),
    composite_score DECIMAL(5,2),
    signal_count INT,
    last_updated TIMESTAMP_NTZ
);

-- =====================================================
-- Raw collected signal data (before compute)
-- =====================================================
CREATE TABLE IF NOT EXISTS signal_raw_collections (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL,
    category VARCHAR(30) NOT NULL,
    collected_at TIMESTAMP_NTZ NOT NULL,
    payload VARIANT NOT NULL,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    UNIQUE(company_id, category)
);

-- =====================================================
-- Seed data for signal_dimension_weights
-- =====================================================
-- One row per (signal_source, dimension) pair from SIGNAL_TO_DIMENSION_MAP
MERGE INTO signal_dimension_weights AS target
USING (
    -- technology_hiring (reliability=0.9)
    SELECT 'technology_hiring' AS signal_source, 'technology_stack'    AS dimension, 0.7  AS weight, TRUE  AS is_primary, 0.9  AS reliability UNION ALL
    SELECT 'technology_hiring',                   'talent_skills',                   0.2,             FALSE,              0.9  UNION ALL
    SELECT 'technology_hiring',                   'use_case_portfolio',               0.1,             FALSE,              0.9  UNION ALL
    -- innovation_activity (reliability=0.85)
    SELECT 'innovation_activity',                 'technology_stack',                0.8,             TRUE,               0.85 UNION ALL
    SELECT 'innovation_activity',                 'use_case_portfolio',               0.1,             FALSE,              0.85 UNION ALL
    SELECT 'innovation_activity',                 'culture_change',                  0.1,             FALSE,              0.85 UNION ALL
    -- digital_presence (reliability=0.75)
    SELECT 'digital_presence',                    'technology_stack',                0.6,             TRUE,               0.75 UNION ALL
    SELECT 'digital_presence',                    'data_infrastructure',             0.4,             FALSE,              0.75 UNION ALL
    -- leadership_signals (reliability=0.95)
    SELECT 'leadership_signals',                  'leadership_vision',               0.7,             TRUE,               0.95 UNION ALL
    SELECT 'leadership_signals',                  'culture_change',                  0.1,             FALSE,              0.95 UNION ALL
    SELECT 'leadership_signals',                  'ai_governance',                   0.2,             FALSE,              0.95 UNION ALL
    -- sec_item_1 (reliability=0.95)
    SELECT 'sec_item_1',                          'use_case_portfolio',               0.5,             TRUE,               0.95 UNION ALL
    SELECT 'sec_item_1',                          'technology_stack',                0.2,             FALSE,              0.95 UNION ALL
    SELECT 'sec_item_1',                          'leadership_vision',               0.3,             FALSE,              0.95 UNION ALL
    -- sec_item_1a (reliability=0.9)
    SELECT 'sec_item_1a',                         'ai_governance',                   0.6,             TRUE,               0.9  UNION ALL
    SELECT 'sec_item_1a',                         'data_infrastructure',             0.4,             FALSE,              0.9  UNION ALL
    -- sec_item_7 (reliability=0.9)
    SELECT 'sec_item_7',                          'leadership_vision',               0.6,             TRUE,               0.9  UNION ALL
    SELECT 'sec_item_7',                          'use_case_portfolio',               0.2,             FALSE,              0.9  UNION ALL
    SELECT 'sec_item_7',                          'data_infrastructure',             0.2,             FALSE,              0.9  UNION ALL
    -- glassdoor_reviews (reliability=0.6)
    SELECT 'glassdoor_reviews',                   'culture_change',                  0.8,             TRUE,               0.6  UNION ALL
    SELECT 'glassdoor_reviews',                   'talent_skills',                   0.1,             FALSE,              0.6  UNION ALL
    SELECT 'glassdoor_reviews',                   'leadership_vision',               0.1,             FALSE,              0.6  UNION ALL
    -- board_composition (reliability=0.85)
    SELECT 'board_composition',                   'ai_governance',                   0.7,             TRUE,               0.85 UNION ALL
    SELECT 'board_composition',                   'leadership_vision',               0.3,             FALSE,              0.85
) AS source
ON target.signal_source = source.signal_source AND target.dimension = source.dimension
WHEN NOT MATCHED THEN
    INSERT (signal_source, dimension, weight, is_primary, reliability)
    VALUES (source.signal_source, source.dimension, source.weight, source.is_primary, source.reliability)
WHEN MATCHED THEN
    UPDATE SET
        weight     = source.weight,
        is_primary = source.is_primary,
        reliability = source.reliability,
        updated_at  = CURRENT_TIMESTAMP(),
        updated_by  = 'seed';
