import pandas as pd
from pathlib import Path
import re
import sys
import pymorphy3
from collections import Counter
import numpy as np
import math
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import psycopg2
from typing import List, Tuple
from sqlalchemy.orm import Session
from models import AbbreviationDict, StopPhrase
from typing import Optional
import ollama
from typing import Optional, List
from datetime import datetime
from tqdm import tqdm
import time
from models import JobTitle

def get_data(path):
    from pathlib import Path
    import pandas as pd

    data_dir = Path(__file__).parent.parent / path
    csv_files = list(data_dir.glob('*.csv'))
    dfs = [pd.read_csv(file, encoding='cp1251', skiprows=1, header=None) for file in csv_files]
    combined_df = pd.concat(dfs, ignore_index=True)

    pattern = r'^\s*(\d+(?:\s\d+)*)##(\d+(?:\s\d+)*)##(.*)$'
    split_df = combined_df[0].str.extract(pattern)

    split_df = split_df.dropna()
    
    split_df[0] = split_df[0].str.replace(r'\s+', '', regex=True).astype(int)
    split_df[1] = split_df[1].str.replace(r'\s+', '', regex=True).astype(int)
    split_df[2] = split_df[2].str.strip()
    split_df.columns = ['номер файла', 'номер должности', 'должность']

    combined_df = combined_df.loc[split_df.index].drop(columns=[0])
    combined_df = pd.concat([combined_df, split_df], axis=1)

    return combined_df
    
def step_1(text):
    if not isinstance(text, str):
        return ''
    text = text.replace(';', '')  
    text = re.sub(r'\.(?=\S)', '. ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def clean(df: pd.DataFrame, column_name: str) -> pd.DataFrame:

    df[column_name] = df[column_name].apply(lambda x: re.sub(r'\s+', ' ', str(x)).strip())
    return df

def step_2(text):
    if not isinstance(text, str):
        return ''
    
    text = re.sub(r'[^a-zA-Zа-яА-ЯёЁ\s]', ' ', text)
    
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text.lower()

def analyze_text_column(df: pd.DataFrame, column_name: str) -> dict:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df должен быть pandas.DataFrame")
    if column_name not in df.columns:
        raise ValueError(f"Столбец '{column_name}' не найден в DataFrame")

    series = df[column_name].fillna('').astype(str)

    def is_russian_char(ch):
        return 'а' <= ch <= 'я' or 'А' <= ch <= 'Я' or ch in 'ёЁ'

    str_lengths = []
    word_counts = []
    avg_word_lengths = []
    all_words = []

    for text in series:
        str_len = len(text)
        str_lengths.append(str_len)

        words = text.split()
        word_counts.append(len(words))

        if words:
            word_lens = [len(w) for w in words]
            avg_len = np.mean(word_lens)
            avg_word_lengths.append(avg_len)
            all_words.extend(words)
        else:
            avg_word_lengths.append(0.0)

    total_rows = len(series)
    total_words = len(all_words)

    mean_str_len = np.mean(str_lengths)
    mean_word_count = np.mean(word_counts)
    mean_word_len = np.mean([len(w) for w in all_words]) if total_words > 0 else 0.0

    max_str_len = np.max(str_lengths)
    min_str_len = np.min(str_lengths)
    max_word_count = np.max(word_counts)
    min_word_count = np.min(word_counts)
    max_avg_word_len = np.max(avg_word_lengths) if avg_word_lengths else 0.0
    min_avg_word_len = np.min(avg_word_lengths) if avg_word_lengths else 0.0

    non_russian_chars = 0
    for text in series:
        for ch in text:
            if not is_russian_char(ch):
                non_russian_chars += 1

    short_words = 0
    dot_ending = 0
    non_russian_or_non_alpha = 0
    all_upper_alpha = 0

    for word in all_words:
        if len(word) <= 3:
            short_words += 1
        if word.endswith('.'):
            dot_ending += 1

        has_non_russian = False
        for ch in word:
            if not is_russian_char(ch):
                has_non_russian = True
                break
        if has_non_russian:
            non_russian_or_non_alpha += 1

        if word.isalpha() and word.isupper():
            all_upper_alpha += 1

    if total_words > 0:
        freq_short = short_words / total_words
        freq_dot = dot_ending / total_words
        freq_non_russian = non_russian_or_non_alpha / total_words
        freq_upper = all_upper_alpha / total_words
    else:
        freq_short = freq_dot = freq_non_russian = freq_upper = 0.0

    ceil_mean_str_len = math.ceil(mean_str_len)
    ceil_mean_word_count = math.ceil(mean_word_count)
    ceil_mean_word_len = math.ceil(mean_word_len)

    rows_exceed_str_len = sum(1 for x in str_lengths if x > ceil_mean_str_len)
    rows_exceed_word_count = sum(1 for x in word_counts if x > ceil_mean_word_count)
    rows_exceed_word_len = sum(1 for x in avg_word_lengths if x > ceil_mean_word_len)

    freq_exceed_str_len = rows_exceed_str_len / total_rows if total_rows > 0 else 0.0
    freq_exceed_word_count = rows_exceed_word_count / total_rows if total_rows > 0 else 0.0
    freq_exceed_word_len = rows_exceed_word_len / total_rows if total_rows > 0 else 0.0

    return {
        'mean_str_len': mean_str_len,
        'mean_word_count': mean_word_count,
        'mean_word_len': mean_word_len,
        'max_str_len': max_str_len,
        'min_str_len': min_str_len,
        'max_word_count': max_word_count,
        'min_word_count': min_word_count,
        'max_avg_word_len': max_avg_word_len,
        'min_avg_word_len': min_avg_word_len,
        'non_russian_chars': non_russian_chars,
        'total_words': total_words,
        'short_words': short_words,
        'freq_short': freq_short,
        'dot_ending': dot_ending,
        'freq_dot': freq_dot,
        'non_russian_or_non_alpha': non_russian_or_non_alpha,
        'freq_non_russian': freq_non_russian,
        'all_upper_alpha': all_upper_alpha,
        'freq_upper': freq_upper,
        'rows_exceed_str_len': rows_exceed_str_len,
        'freq_exceed_str_len': freq_exceed_str_len,
        'rows_exceed_word_count': rows_exceed_word_count,
        'freq_exceed_word_count': freq_exceed_word_count,
        'rows_exceed_word_len': rows_exceed_word_len,
        'freq_exceed_word_len': freq_exceed_word_len
    }


def print_analysis(results: dict) -> None:
    print(f"=== Анализ столбца ===\n")
    print("Статистика по строкам:")
    print(f"  Средняя длина строки:           {results['mean_str_len']:.2f}")
    print(f"  Среднее количество слов:        {results['mean_word_count']:.2f}")
    print(f"  Средняя длина слова (общая):    {results['mean_word_len']:.2f}")
    print(f"  Макс. длина строки:             {results['max_str_len']}")
    print(f"  Мин. длина строки:              {results['min_str_len']}")
    print(f"  Макс. количество слов:          {results['max_word_count']}")
    print(f"  Мин. количество слов:           {results['min_word_count']}")
    print(f"  Макс. средняя длина слов:       {results['max_avg_word_len']:.2f}")
    print(f"  Мин. средняя длина слов:        {results['min_avg_word_len']:.2f}")
    print()
    print("Строки, превышающие округлённые средние:")
    print(f"  Длина строки > {math.ceil(results['mean_str_len'])}: {results['rows_exceed_str_len']} ({results['freq_exceed_str_len']:.2%})")
    print(f"  Количество слов > {math.ceil(results['mean_word_count'])}: {results['rows_exceed_word_count']} ({results['freq_exceed_word_count']:.2%})")
    print(f"  Средняя длина слова > {math.ceil(results['mean_word_len'])}: {results['rows_exceed_word_len']} ({results['freq_exceed_word_len']:.2%})")
    print()
    print("Символьная статистика (суммарно по всем строкам):")
    print(f"  Количество небуквенных и не русских символов: {results['non_russian_chars']}")
    print()
    print("Статистика по словам (всего слов: {}):".format(results['total_words']))
    print(f"  Слов длиной <= 3:                {results['short_words']}  ({results['freq_short']:.2%})")
    print(f"  Слов, оканчивающихся на точку:   {results['dot_ending']}  ({results['freq_dot']:.2%})")
    print(f"  Слов с небуквенными/не русскими: {results['non_russian_or_non_alpha']}  ({results['freq_non_russian']:.2%})")
    print(f"  Слов только из заглавных букв:   {results['all_upper_alpha']}  ({results['freq_upper']:.2%})")

def get_unique_words_ending_with_dot(df: pd.DataFrame, column_name: str) -> list:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df должен быть pandas.DataFrame")
    if column_name not in df.columns:
        raise ValueError(f"Столбец '{column_name}' не найден в DataFrame")

    series = df[column_name].fillna('').astype(str)
    
    all_words = []
    first_occurrence = {}
    
    for text in series:
        for word in text.split():
            if word.endswith('.'):
                normalized = word.rstrip('.').lower()
                all_words.append(normalized)
                if normalized not in first_occurrence:
                    first_occurrence[normalized] = text
    
    from collections import Counter
    word_counts = Counter(all_words)
    
    sorted_words = sorted(word_counts.keys(), key=lambda w: word_counts[w], reverse=True)
    
    result = [(first_occurrence[w], w) for w in sorted_words]
    return result

def print_list_elements(lst: list) -> None:
    for item in lst:
        print(item)

def interactive_process_terms(
    terms: List[Tuple[str, str]],
    session: Session,
    AbbreviationDict,
    StopPhrase
) -> None:

    for idx, (full_text, token_with_dot) in enumerate(terms, 1):
        token_clean = token_with_dot.rstrip('.').strip()
        if not token_clean:
            token_clean = token_with_dot

        print("\n" + "=" * 60)
        print(f"   Обработка #{idx} из {len(terms)}")
        print(f"   Полная строка: {full_text}")
        print(f"   Слово с точкой: {token_with_dot}")
        print(f"   (очищенное: {token_clean})")

        while True:
            print("\nВыберите действие:")
            print("  1️  Игнорировать (пропустить)")
            print("  2️  Добавить расшифровку (в словарь сокращений, ключ без точки)")
            print("  3️  Добавить шаблон для удаления (regex или literal)")
            print("  4️  Добавить простое удаление подстроки (literal, с точкой или без)")
            print("  5️  Выйти из обработки досрочно")
            choice = input("Ваш выбор (1-5): ").strip()

            if choice == '5':
                print("Обработка прервана.")
                return

            if choice == '1':
                print("Пропущено.")
                break

            if choice == '2':
                expansion = input(f"Введите полную расшифровку для '{token_clean}': ").strip()
                if not expansion:
                    print("Расшифровка не введена.")
                    continue

                existing = session.query(AbbreviationDict).filter_by(abbreviation=token_clean).first()
                if existing:
                    overwrite = input(f"Сокращение '{token_clean}' уже существует (текущее: '{existing.expansion}'). Перезаписать? (y/n): ").strip().lower()
                    if overwrite == 'y':
                        existing.expansion = expansion
                        print("Обновлено.")
                    else:
                        print("Оставлено без изменений.")
                else:
                    new_abbr = AbbreviationDict(
                        abbreviation=token_clean,
                        expansion=expansion,
                        category='unknown',
                        added_by='manual'
                    )
                    session.add(new_abbr)
                    print("Добавлено в словарь сокращений.")
                session.commit()
                break

            if choice == '3':
                pattern = input("Введите шаблон (например, 'района' или r'\\s+\\w+ского района'): ").strip()
                if not pattern:
                    print("Шаблон не введён.")
                    continue

                is_regex = input("Это регулярное выражение? (y/n): ").strip().lower()
                pattern_type = 'regex' if is_regex == 'y' else 'literal'
                comment = input("Комментарий (необязательно): ").strip() or None

                new_stop = StopPhrase(
                    phrase=pattern,
                    pattern_type=pattern_type,
                    action='remove',
                    comment=comment
                )
                session.add(new_stop)
                session.commit()
                print("Шаблон для удаления добавлен.")
                break

            if choice == '4':
                use_clean = input(f"Использовать без точки ('{token_clean}')? (y/n, по умолчанию y): ").strip().lower()
                sub = token_clean if use_clean != 'n' else token_with_dot
                custom = input(f"Введите подстроку (Enter — использовать '{sub}'): ").strip()
                if custom:
                    sub = custom

                existing = session.query(StopPhrase).filter_by(phrase=sub, pattern_type='literal').first()
                if existing:
                    print(f"Фраза '{sub}' уже есть в стоп-фразах.")
                else:
                    new_stop = StopPhrase(
                        phrase=sub,
                        pattern_type='literal',
                        action='remove',
                        comment='добавлено интерактивно'
                    )
                    session.add(new_stop)
                    session.commit()
                    print("Подстрока для удаления добавлена.")
                break

            print("Неверный ввод, попробуйте снова.")

    print("\nОбработка завершена.")

def normalize_profession_llm(text: str, model: str = "llama3") -> str:

    if not isinstance(text, str) or not text.strip():
        return ""
    
    prompt = f"""
Ты — эксперт по нормализации должностей. Приведи следующую должность к стандартному формату на русском языке.
Исправь сокращения, убери лишнию информацию, опечатки, приведи к единому виду (например, "зам. гл. инж." -> "Заместитель главного инженера", "Главный государственный инженер-инспектор  Курского района" -> "Главный государственный инженер-инспектор").
Если должность не распознаётся, верни её как есть выделенной ? с обеих сторон.

Должность: {text}
Нормализованная должность (только ответ из буквенных символов, без пояснений):
"""
    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1, "num_predict": 60}
        )
        result = response["message"]["content"].strip()
        return result if result else text
    except Exception as e:
        print(f"Ошибка при обработке '{text}': {e}")
        return text


def lemmatize(text: str) -> str:

    if not isinstance(text, str) or not text.strip():
        return text
    
    try:
        import pymorphy3
        morph = pymorphy3.MorphAnalyzer()
        words = text.split()
        lemmatized = []
        
        for word in words:
            if not word or len(word) < 2:
                lemmatized.append(word)
                continue
            
            try:
                parsed = morph.parse(word)
                if parsed:
                    lemmatized.append(parsed[0].normal_form)
                else:
                    lemmatized.append(word)
            except Exception:
                lemmatized.append(word)
        
        return ' '.join(lemmatized)
    except ImportError:

        return text


def get_pending_count(session, JobTitle):

    return session.query(JobTitle).filter(
        JobTitle.is_ai_processed == False
    ).count()


def get_processed_count(session, JobTitle):

    return session.query(JobTitle).filter(
        JobTitle.is_ai_processed == True
    ).count()


def normalize_professions(df, column_name, session, AbbreviationDict, StopPhrase, new_column_name):

    result_df = df.copy()

    abbreviations = session.query(AbbreviationDict).filter(
        AbbreviationDict.is_active == True
    ).all()
 
    stop_phrases = session.query(StopPhrase).all()

    def apply_rules(text):
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
    
    result_df[new_column_name] = result_df[column_name].apply(apply_rules)
    
    return result_df

def extract_after_arrow(text: str) -> str:

    if not isinstance(text, str):
        return ''
    
    pos = text.find('->')
    if pos == -1:
        return text
    return text[pos + 2:].strip()

def remove_duplicate_words(text: str) -> str:

    if not isinstance(text, str):
        return ''

    words = text.split()
    seen = set()
    unique_words = []

    for word in words:
        if word not in seen:
            seen.add(word)
            unique_words.append(word)

    return ' '.join(unique_words)

def get_normalized_jobs(
    session: Session,
    only_manual_verified: bool = False,
    only_llm_processed: bool = True,
    exclude_empty: bool = True
) -> pd.DataFrame:
    query = session.query(JobTitle)
    
    if exclude_empty:
        query = query.filter(JobTitle.normalized_title.isnot(None))
        query = query.filter(JobTitle.normalized_title != '')
    
    if only_manual_verified:
        query = query.filter(JobTitle.is_manual_verified == True)
    
    if only_llm_processed:
        query = query.filter(JobTitle.processing_method == 'llm')
    
    jobs = query.all()
    
    data = {
        'id': [j.id for j in jobs],
        'file_number': [j.file_number for j in jobs],
        'line_number': [j.line_number for j in jobs],
        'normalized_title': [j.normalized_title for j in jobs],
        'is_manual_verified': [j.is_manual_verified for j in jobs],
        'processing_method': [j.processing_method for j in jobs]
    }
    
    df = pd.DataFrame(data)

    df = df.drop_duplicates(subset=['normalized_title'])

    df = df[df['normalized_title'].notna() & (df['normalized_title'] != '')]

    df = df[~df['normalized_title'].str.contains(r'[A-Za-z]', na=False)]

    df['normalized_title'] = df['normalized_title'].apply(remove_duplicate_words)

    df = df.drop_duplicates(subset=['normalized_title'])
    
    return df

def apply_db_rules(text, abbreviations, stop_phrases):

    if not isinstance(text, str):
        return text

    for sp in stop_phrases:
        if sp.pattern_type == 'literal':
            text = text.replace(sp.phrase, '')
        elif sp.pattern_type == 'regex':
            try:
                text = re.sub(sp.phrase, '', text, flags=re.IGNORECASE)
            except:
                pass

    for abbr in abbreviations:
        pattern = r'\b' + re.escape(abbr.abbreviation) + r'(\.?)(?=\s|$)'
        text = re.sub(pattern, lambda m: abbr.expansion + ('' if m.group(1) else ''), text, flags=re.IGNORECASE)

    text = re.sub(r'\s+', ' ', text).strip()
    return text