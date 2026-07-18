import os
import re
import sys
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import normalize_utils as nu
from models import ReferenceTitle, JobTitle, AbbreviationDict, StopPhrase

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




print("Загрузка эталонов и правил...")
reference_titles = session.query(ReferenceTitle).all()
if not reference_titles:
    print("Ошибка: в таблице reference_titles нет записей. Сначала запустите build_reference.py")
    sys.exit(1)

ref_texts = [r.canonical_title for r in reference_titles]
ref_ids = [r.id for r in reference_titles]
print(f"Загружено {len(ref_texts)} эталонов.")


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




def normalize_input(text):

    if not isinstance(text, str):
        return ''
    text = nu.step_1(text)
    text = nu.clean_single(text)
    text = apply_db_rules(text)
    text = nu.step_2(text)
    text = nu.lemmatize(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text



def clean_single(text):
    if not isinstance(text, str):
        return ''

    text = re.sub(r'\s+', ' ', text).strip()
    return text


if not hasattr(nu, 'clean_single'):
    nu.clean_single = clean_single




def get_first_words(text, n=2):
    words = text.split()
    return ' '.join(words[:n]) if len(words) >= n else text

print("Обучение векторизатора на эталонах...")
vectorizer_main = TfidfVectorizer(
    analyzer='char_wb',
    ngram_range=(2, 4),
    min_df=1
)
X_main = vectorizer_main.fit_transform(ref_texts)

vectorizer_first = TfidfVectorizer(
    analyzer='word',
    ngram_range=(1, 2),
    min_df=1
)
first_words = [get_first_words(t, 2) for t in ref_texts]
X_first = vectorizer_first.fit_transform(first_words)

from scipy.sparse import hstack
weight_first = 2.0
X_ref = hstack([X_main, weight_first * X_first])
print("Векторизатор обучен.")




def classify(text, threshold=0.6):

    norm_text = normalize_input(text)
    if not norm_text:
        return None, 0.0, "Некорректный ввод"


    x_main = vectorizer_main.transform([norm_text])
    first_words_input = [get_first_words(norm_text, 2)]
    x_first = vectorizer_first.transform(first_words_input)
    x_vec = hstack([x_main, weight_first * x_first])


    sim = cosine_similarity(x_vec, X_ref).flatten()
    best_idx = np.argmax(sim)
    best_score = sim[best_idx]
    best_ref = ref_texts[best_idx]
    best_id = ref_ids[best_idx]

    if best_score < threshold:
        return None, best_score, f"Нет эталона с достаточной уверенностью (лучший: {best_score:.3f})"

    return best_id, best_score, best_ref




def interactive_mode():
    print("\nВведите должность для классификации (или 'exit' для выхода):")
    while True:
        text = input("> ").strip()
        if text.lower() in ('exit', 'quit', 'q'):
            break
        if not text:
            continue
        ref_id, score, ref_title = classify(text)
        if ref_id is None:
            print(f"Не удалось классифицировать (уверенность: {score:.3f})")
            print(f"Информация: {ref_title}")
        else:
            print(f"Эталон: {ref_title} (ID: {ref_id})")
            print(f"Уверенность: {score:.3f}")
        print()




if __name__ == "__main__":
    if len(sys.argv) > 1:

        user_input = ' '.join(sys.argv[1:])
        ref_id, score, ref_title = classify(user_input)
        if ref_id is None:
            print(f"Не удалось классифицировать (уверенность: {score:.3f})")
            print(f"Информация: {ref_title}")
        else:
            print(f"Эталон: {ref_title} (ID: {ref_id})")
            print(f"Уверенность: {score:.3f}")
    else:

        interactive_mode()

    session.close()