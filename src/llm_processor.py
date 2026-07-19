import os
import time
import re
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from tqdm import tqdm

import normalize_utils as nu
from models import JobTitle, AbbreviationDict, StopPhrase

load_dotenv()

print("\nНОРМАЛИЗАЦИЯ ДОЛЖНОСТЕЙ С ИСПОЛЬЗОВАНИЕМ LLM")
print("-" * 60)




print("\n1. Подключение к базе данных...")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "positions")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

print(f"   Подключено к {DB_NAME} на {DB_HOST}:{DB_PORT}")




print("\n2. Загрузка и первичная обработка данных...")

DATA_PATH = os.getenv("DATA_PATH")
df = nu.get_data(DATA_PATH)
print(f"   Загружено {len(df)} записей из файлов")

combined_df = df.copy()

print("   Применение step_1...")
combined_df['должность'] = combined_df['должность'].apply(nu.step_1)

print("   Применение clean...")
combined_df = nu.clean(combined_df, 'должность')

print("   Применение замен из БД...")
abbreviations = session.query(AbbreviationDict).filter(
    AbbreviationDict.is_active == True
).all()
stop_phrases = session.query(StopPhrase).all()

def apply_db_rules(text):
    if not isinstance(text, str):
        return text
    for abbr in abbreviations:
        pattern = r'\b' + re.escape(abbr.abbreviation) + r'(\.?)\b'
        text = re.sub(pattern, lambda m: abbr.expansion + ('.' if m.group(1) else ''), text, flags=re.IGNORECASE)
    for sp in stop_phrases:
        if sp.pattern_type == 'literal':
            text = text.replace(sp.phrase, '')
        elif sp.pattern_type == 'regex':
            try:
                text = re.sub(sp.phrase, '', text, flags=re.IGNORECASE)
            except:
                pass
    text = re.sub(r'\s+', ' ', text).strip()
    return text

combined_df['должность'] = combined_df['должность'].apply(apply_db_rules)

if 'file_number' not in combined_df.columns:
    combined_df['file_number'] = 1
if 'line_number' not in combined_df.columns:
    combined_df['line_number'] = combined_df.index + 1

print(f"   Подготовлено {len(combined_df)} записей")

print("\n3. Определение записей для обработки...")


existing_by_cleaned = {}
for job in session.query(JobTitle).all():
    if job.cleaned_title:
        key = job.cleaned_title.strip()
        if key not in existing_by_cleaned:
            existing_by_cleaned[key] = job

to_process = []
for idx, row in combined_df.iterrows():
    cleaned = row['должность'].strip()
    existing = existing_by_cleaned.get(cleaned)
    if existing is None:
        to_process.append((row, None))
    else:
        if not existing.is_ai_processed:
            to_process.append((row, existing))

print(f"   Всего записей для обработки: {len(to_process)}")




print("\n4. Запуск обработки LLM...")
print("-" * 60)

success_count = 0
error_count = 0
start_time = time.time()

pbar = tqdm(
    total=len(to_process),
    desc="Обработка LLM",
    unit="запись",
    bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
)

for row, existing_job in to_process:
    try:
        text = row['должность']
        normalized = nu.normalize_profession_llm(text, model="llama3")
        normalized = nu.extract_after_arrow(normalized)
        normalized = nu.remove_duplicate_words(normalized)
        normalized = nu.step_2(normalized)
        normalized = nu.lemmatize(normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        normalized = normalized.replace('?', '').strip()

        if existing_job is None:
            job = JobTitle(
                file_number=row['file_number'],
                line_number=row['line_number'],
                original_title=row['должность'],
                cleaned_title=row['должность'],
                normalized_title=normalized,
                is_ai_processed=True,
                processing_method='llm'
            )
            session.add(job)
        else:
            existing_job.normalized_title = normalized
            existing_job.is_ai_processed = True
            existing_job.processing_method = 'llm'

        session.commit()  
        success_count += 1

    except Exception as e:
        print(f"\n   ОШИБКА при обработке file={row['file_number']}, line={row['line_number']}: {e}")
        session.rollback()
        error_count += 1

    pbar.update(1)
    pbar.set_postfix({'успешно': success_count, 'ошибок': error_count})

pbar.close()

elapsed_time = time.time() - start_time
minutes = int(elapsed_time // 60)
seconds = int(elapsed_time % 60)

print("\n" + "-" * 60)
print("ОБРАБОТКА ЗАВЕРШЕНА")
print("-" * 60)
print(f"Всего обработано: {len(to_process)} записей")
print(f"Успешно: {success_count}")
print(f"С ошибками: {error_count}")
print(f"Затрачено времени: {minutes} мин {seconds} сек")
print("-" * 60 + "\n")

session.close()