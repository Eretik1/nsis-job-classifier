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

df = nu.remove_empty_and_duplicates(df, 'step_4')

df['step_5'] = df['step_4']

df['step_5'] = df['step_5'].apply(nu.lemmatize)

#res = nu.get_upper_dot_words_stats(df, 'step_1')
#res = nu.get_upper_alpha_words_stats(df, 'step_3')
#print(len(res))
#nu.print_list_elements(res)

res = nu.analyze_text_column(df, 'step_5')
nu.print_analysis(res)