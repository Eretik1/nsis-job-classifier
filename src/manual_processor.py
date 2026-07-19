import os
import re
import normalize_utils as nu
from models import AbbreviationDict, StopPhrase
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

print("\nРУЧНАЯ ОБРАБОТКА ДАННЫХ")
print("-" * 50)

print("\n1. Загрузка данных...")
DATA_PATH = os.getenv("DATA_PATH", "data")
df = nu.get_data(DATA_PATH)
print(f"   Загружено {len(df)} записей")

print("\n2. Первичная обработка...")
combined_df = df.copy()

print("   Применение step_1...")
combined_df['должность'] = combined_df['должность'].apply(nu.step_1)

print("   Применение clean...")
combined_df = nu.clean(combined_df, 'должность')
print("   Первичная обработка завершена")

print("\n3. Подключение к базе данных...")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()
print(f"   Подключение к БД {DB_NAME} на {DB_HOST}:{DB_PORT}")

abbreviations = session.query(AbbreviationDict).filter(
    AbbreviationDict.is_active == True
).all()
stop_phrases = session.query(StopPhrase).all()

print("\n4. Применение правил из БД...")
print("   Проход 1: замена сокращений и удаление стоп-фраз...")
combined_df['должность'] = combined_df['должность'].apply(lambda x: nu.apply_db_rules(x, abbreviations, stop_phrases))

print("   Приведение к нижнему регистру...")
combined_df['должность'] = combined_df['должность'].str.lower()

print("   Проход 2: повторное применение правил...")
combined_df['должность'] = combined_df['должность'].apply(lambda x: nu.apply_db_rules(x, abbreviations, stop_phrases))

print("   Нормализация завершена")

print("\n5. Ручная обработка терминов...")
terms = nu.get_unique_words_ending_with_dot(combined_df, 'должность')
print(f"   Найдено {len(terms)} уникальных терминов с точкой")

if len(terms) == 0:
    print("   Нет терминов для обработки")
else:
    print("   Запуск интерактивного режима...")
    print("   Следуйте инструкциям в консоли\n")
    nu.interactive_process_terms(terms, session, AbbreviationDict, StopPhrase)

print("\n" + "-" * 50)
print("РУЧНАЯ ОБРАБОТКА ЗАВЕРШЕНА")
print("-" * 50)
print(f"Обработано записей: {len(combined_df)}")
print(f"Найдено терминов с точкой: {len(terms)}")
print("Обновленные словари сохранены в БД")
print("-" * 50 + "\n")

session.close()