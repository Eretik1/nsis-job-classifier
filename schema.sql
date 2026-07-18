-- 1. Таблица эталонных должностей (результат кластеризации)
CREATE TABLE reference_titles (
    id SERIAL PRIMARY KEY,
    canonical_title TEXT NOT NULL UNIQUE,   -- каноническое название
    cluster_id INT,                         -- номер кластера (опционально)
    cluster_size INT,                       -- количество элементов в кластере
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE reference_titles IS 'Эталонные должности, полученные после кластеризации';
COMMENT ON COLUMN reference_titles.canonical_title IS 'Нормализованное эталонное название должности';

-- 2. Основная таблица с должностями
CREATE TABLE job_titles (
    id SERIAL PRIMARY KEY,
    file_number INT NOT NULL,               -- номер файла/выгрузки
    line_number INT NOT NULL,               -- номер строки в файле
    original_title TEXT NOT NULL,           -- исходная «сырая» запись
    cleaned_title TEXT,                     -- после алгоритмической очистки (без ИИ)
    normalized_title TEXT,                  -- финальный нормализованный вариант
    is_ai_processed BOOLEAN NOT NULL DEFAULT FALSE,  -- обработано ли ИИ
    processing_method VARCHAR(20) DEFAULT 'algorithm', -- 'algorithm' | 'llm' | 'manual'
    reference_id INT,                       -- ссылка на эталонную должность
    confidence FLOAT,                       -- уверенность классификации (0..1)
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_manual_verified BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_reference FOREIGN KEY (reference_id) 
        REFERENCES reference_titles(id) ON DELETE SET NULL
);

COMMENT ON TABLE job_titles IS 'Исходные и обработанные записи должностей';
COMMENT ON COLUMN job_titles.cleaned_title IS 'Результат алгоритмической очистки (без LLM)';
COMMENT ON COLUMN job_titles.normalized_title IS 'Финальный нормализованный вариант, используемый для классификации';

-- 3. Словарь сокращений и аббревиатур
CREATE TABLE abbreviation_dict (
    id SERIAL PRIMARY KEY,
    abbreviation VARCHAR(100) NOT NULL UNIQUE,  -- сокращение (в нижнем регистре, без точек)
    expansion TEXT NOT NULL,                    -- полная расшифровка
    category VARCHAR(50),                       -- например 'department', 'qualification', 'role'
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    added_by VARCHAR(50) DEFAULT 'system',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE abbreviation_dict IS 'Справочник сокращений для алгоритмической замены';
COMMENT ON COLUMN abbreviation_dict.abbreviation IS 'Сокращение (ключ для поиска, например "ахч")';
COMMENT ON COLUMN abbreviation_dict.expansion IS 'Полное название, на которое заменяем';

-- 4. Стоп-фразы (удаляемая лишняя информация)
CREATE TABLE stop_phrases (
    id SERIAL PRIMARY KEY,
    phrase TEXT NOT NULL UNIQUE,                -- фраза или шаблон для удаления
    action VARCHAR(20) NOT NULL DEFAULT 'remove', -- 'remove' | 'mark'
    comment TEXT,                                -- пояснение, например "географическая привязка"
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE stop_phrases IS 'Фразы, которые следует удалять из названий должностей';

-- 5. Индексы для ускорения запросов
CREATE INDEX idx_job_titles_original ON job_titles(original_title);
CREATE INDEX idx_job_titles_normalized ON job_titles(normalized_title);
CREATE INDEX idx_job_titles_reference ON job_titles(reference_id);
CREATE INDEX idx_job_titles_ai_processed ON job_titles(is_ai_processed);
CREATE INDEX idx_abbreviation_abbr ON abbreviation_dict(abbreviation);
CREATE INDEX idx_stop_phrases_phrase ON stop_phrases(phrase);\
CREATE INDEX idx_job_titles_manual ON job_titles(is_manual_verified)

