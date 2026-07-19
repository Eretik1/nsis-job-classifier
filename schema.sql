 CREATE TABLE reference_titles (
    id SERIAL PRIMARY KEY,
    canonical_title TEXT NOT NULL UNIQUE,   
    cluster_id INT,                         
    cluster_size INT,                       
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE reference_titles IS 'Эталонные должности, полученные после кластеризации';
COMMENT ON COLUMN reference_titles.canonical_title IS 'Нормализованное эталонное название должности';

CREATE TABLE job_titles (
    id SERIAL PRIMARY KEY,
    file_number INT NOT NULL,               
    line_number INT NOT NULL,               
    original_title TEXT NOT NULL,           
    cleaned_title TEXT,                     
    normalized_title TEXT,                  
    is_ai_processed BOOLEAN NOT NULL DEFAULT FALSE, 
    processing_method VARCHAR(20) DEFAULT 'algorithm', 
    reference_id INT,                       
    confidence FLOAT,                       
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_manual_verified BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_reference FOREIGN KEY (reference_id) 
        REFERENCES reference_titles(id) ON DELETE SET NULL
);

COMMENT ON TABLE job_titles IS 'Исходные и обработанные записи должностей';
COMMENT ON COLUMN job_titles.cleaned_title IS 'Результат алгоритмической очистки (без LLM)';
COMMENT ON COLUMN job_titles.normalized_title IS 'Финальный нормализованный вариант, используемый для классификации';

CREATE TABLE abbreviation_dict (
    id SERIAL PRIMARY KEY,
    abbreviation VARCHAR(100) NOT NULL UNIQUE,  
    expansion TEXT NOT NULL,                    
    category VARCHAR(50),                       
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    added_by VARCHAR(50) DEFAULT 'system',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE abbreviation_dict IS 'Справочник сокращений для алгоритмической замены';
COMMENT ON COLUMN abbreviation_dict.abbreviation IS 'Сокращение (ключ для поиска, например "ахч")';
COMMENT ON COLUMN abbreviation_dict.expansion IS 'Полное название, на которое заменяем';

CREATE TABLE stop_phrases (
    id SERIAL PRIMARY KEY,
    phrase TEXT NOT NULL UNIQUE,
    pattern_type VARCHAR(20) NOT NULL DEFAULT 'literal',
    action VARCHAR(20) NOT NULL DEFAULT 'remove',
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE stop_phrases IS 'Фразы, которые следует удалять из названий должностей';

CREATE INDEX idx_job_titles_original ON job_titles(original_title);
CREATE INDEX idx_job_titles_normalized ON job_titles(normalized_title);
CREATE INDEX idx_job_titles_reference ON job_titles(reference_id);
CREATE INDEX idx_job_titles_ai_processed ON job_titles(is_ai_processed);
CREATE INDEX idx_abbreviation_abbr ON abbreviation_dict(abbreviation);
CREATE INDEX idx_stop_phrases_phrase ON stop_phrases(phrase);
CREATE INDEX idx_job_titles_manual ON job_titles(is_manual_verified)

