import os
import time
import re
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from tqdm import tqdm
from collections import Counter

import normalize_utils as nu
from models import JobTitle, AbbreviationDict, StopPhrase

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

abbreviations = session.query(AbbreviationDict).filter(
    AbbreviationDict.is_active == True
).all()
stop_phrases = session.query(StopPhrase).all()

DATA_PATH = os.getenv("DATA_PATH")
df = nu.get_data(DATA_PATH)
df['step_1'] = df['должность'].apply(nu.step_1)

df['step_2'] = df['step_1'].apply(lambda x: nu.apply_db_rules(x, abbreviations, stop_phrases))

df['step_3'] = df['step_2'].apply(nu.remove_short_upper_words)

df['step_3'] = df['step_3'].apply(str.lower)

df['step_3'] = df['step_3'].apply(lambda x: nu.apply_db_rules(x, abbreviations, stop_phrases))

df['step_4'] = df['step_3'].apply(nu.step_4)

df = nu.truncate_and_filter_words(df, 'step_4')

#df = nu.remove_empty_and_duplicates(df, 'step_4')

df['step_5'] = df['step_4']

print("Начало лемматизации...")
tqdm.pandas()

df['step_5'] = df['step_5'].progress_apply(nu.lemmatize)

#df = nu.remove_empty_and_duplicates(df, 'step_5')

#res = nu.get_upper_dot_words_stats(df, 'step_1')
#res = nu.get_upper_alpha_words_stats(df, 'step_3')
#print(len(res))
#nu.print_list_elements(res)

#res = nu.analyze_text_column(df, 'step_5')
#nu.print_analysis(res)

print("\nЗагрузка данных в БД...")

inserted = 0
updated = 0
batch_size = 1000

for idx, row in df.iterrows():
    original = row['должность']
    cleaned = row['step_5']
    normalized = row['step_5']

    existing = session.query(JobTitle).filter_by(original_title=original).first()

    if existing:
        existing.normalized_title = cleaned
        existing.cleaned_title = cleaned
        existing.is_ai_processed = False
        existing.processing_method = 'algorithm'
        updated += 1
    else:
        new_job = JobTitle(
            original_title=original,
            cleaned_title=cleaned,
            normalized_title=normalized,
            is_ai_processed=False,
            processing_method='algorithm',
            file_number = row['номер файла'],
            line_number = row['номер должности'],
        )
        session.add(new_job)
        inserted += 1

    if (idx + 1) % batch_size == 0:
        session.commit()
        print(f"   Обработано {idx+1} из {len(df)} записей")

session.commit()
print(f"\nЗагрузка завершена.")
print(f"   Добавлено новых записей: {inserted}")
print(f"   Обновлено существующих записей: {updated}")