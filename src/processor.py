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

df['step_1'] = df['step_1'].apply(lambda x: nu.apply_db_rules(x, abbreviations, stop_phrases))

def get_upper_dot_words_stats(df, column_name):
    if column_name not in df.columns:
        raise ValueError(f"Столбец '{column_name}' не найден")

    all_words = []
    first_occurrence = {}
    pattern = re.compile(r'\b\w+\.')

    for value in df[column_name]:
        if not isinstance(value, str):
            continue
        matches = pattern.findall(value)
        for match in matches:
            word = match[:-1].lower()
            all_words.append(word)
            if word not in first_occurrence:
                first_occurrence[word] = value

    word_counts = Counter(all_words)

    result = [
        [first_occurrence[word], word, word_counts[word]]
        for word in first_occurrence.keys()
    ]
    result.sort(key=lambda x: x[2], reverse=True)
    return result

res = get_upper_dot_words_stats(df, 'step_1')
print(len(res))
nu.print_list_elements(res)