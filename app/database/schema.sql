-- PE Org-AI-R Platform Database Schema
-- Snowflake DDL Statements

-- =====================================================
-- Industries table (reference data)
-- =====================================================
CREATE TABLE IF NOT EXISTS industries (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    sector VARCHAR(100) NOT NULL,
    h_r_base DECIMAL(5,2) CHECK (h_r_base BETWEEN 0 AND 100),
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- =====================================================
-- Companies table
-- =====================================================
CREATE TABLE IF NOT EXISTS companies (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    ticker VARCHAR(10),
    industry_id VARCHAR(36) REFERENCES industries(id),
    position_factor DECIMAL(4,3) DEFAULT 0.0
        CHECK (position_factor BETWEEN -1.0 AND 1.0),
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- =====================================================
-- Assessments table
-- =====================================================
CREATE TABLE IF NOT EXISTS assessments (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id),
    assessment_type VARCHAR(20) NOT NULL
        CHECK (assessment_type IN ('screening', 'due_diligence', 'quarterly', 'exit_prep')),
    assessment_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'draft'
        CHECK (status IN ('draft', 'in_progress', 'submitted', 'approved', 'superseded')),
    primary_assessor VARCHAR(255),
    secondary_assessor VARCHAR(255),
    v_r_score DECIMAL(5,2) CHECK (v_r_score BETWEEN 0 AND 100),
    confidence_lower DECIMAL(5,2),
    confidence_upper DECIMAL(5,2),
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- =====================================================
-- Dimension scores table
-- =====================================================
CREATE TABLE IF NOT EXISTS dimension_scores (
    id VARCHAR(36) PRIMARY KEY,
    assessment_id VARCHAR(36) NOT NULL REFERENCES assessments(id),
    dimension VARCHAR(30) NOT NULL
        CHECK (dimension IN (
            'data_infrastructure', 'ai_governance', 'technology_stack',
            'talent_skills', 'leadership_vision', 'use_case_portfolio',
            'culture_change'
        )),
    score DECIMAL(5,2) NOT NULL CHECK (score BETWEEN 0 AND 100),
    weight DECIMAL(4,3) CHECK (weight BETWEEN 0 AND 1),
    confidence DECIMAL(4,3) DEFAULT 0.8 CHECK (confidence BETWEEN 0 AND 1),
    evidence_count INT DEFAULT 0,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    UNIQUE (assessment_id, dimension)
);

-- =====================================================
-- Indexes for common queries
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_companies_industry 
    ON companies(industry_id);
CREATE INDEX IF NOT EXISTS idx_companies_deleted 
    ON companies(is_deleted);
CREATE INDEX IF NOT EXISTS idx_assessments_company 
    ON assessments(company_id);
CREATE INDEX IF NOT EXISTS idx_assessments_status 
    ON assessments(status);
CREATE INDEX IF NOT EXISTS idx_assessments_type 
    ON assessments(assessment_type);
CREATE INDEX IF NOT EXISTS idx_dimension_scores_assessment 
    ON dimension_scores(assessment_id);

-- =====================================================
-- Seed data for industries
-- =====================================================
INSERT INTO industries (id, name, sector, h_r_base) VALUES
    ('550e8400-e29b-41d4-a716-446655440001', 'Manufacturing', 'Industrials', 72),
    ('550e8400-e29b-41d4-a716-446655440002', 'Healthcare Services', 'Healthcare', 78),
    ('550e8400-e29b-41d4-a716-446655440003', 'Business Services', 'Services', 75),
    ('550e8400-e29b-41d4-a716-446655440004', 'Retail', 'Consumer', 70),
    ('550e8400-e29b-41d4-a716-446655440005', 'Financial Services', 'Financial', 80),
    ('550e8400-e29b-41d4-a716-446655440006', 'Technology', 'Technology', 85),
    ('550e8400-e29b-41d4-a716-446655440007', 'Energy', 'Energy', 68),
    ('550e8400-e29b-41d4-a716-446655440008', 'Real Estate', 'Real Estate', 65);