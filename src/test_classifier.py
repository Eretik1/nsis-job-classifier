import os
import sys
import random
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from tqdm import tqdm

from classify_job import classify, normalize_input, vectorizer_main, vectorizer_first, X_ref, weight_first
from models import JobTitle

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

print("ТЕСТИРОВАНИЕ КЛАССИФИКАТОРА")
print("=" * 60)

print("Загрузка тестовых записей из БД...")
test_jobs = session.query(JobTitle).filter(
    JobTitle.reference_id.isnot(None)
).all()
print(f"Найдено {len(test_jobs)} записей с reference_id.")

if not test_jobs:
    print("Нет записей с reference_id. Сначала запустите build_reference.py.")
    sys.exit(1)

sample_size = min(200, len(test_jobs))
test_sample = random.sample(test_jobs, sample_size)
print(f"Выбрано {sample_size} записей для тестирования.")

correct = 0
incorrect = 0
low_confidence = 0  

results = []

print("\nТестирование...")
for job in tqdm(test_sample, desc="Классификация"):
    original = job.original_title
    true_ref_id = job.reference_id

    pred_ref_id, confidence, ref_title = classify(original, threshold=0.6)

    if pred_ref_id is None:

        low_confidence += 1

        if true_ref_id is not None:
            incorrect += 1
        continue

    if pred_ref_id == true_ref_id:
        correct += 1
    else:
        incorrect += 1

        results.append({
            'original': original,
            'true_ref': true_ref_id,
            'pred_ref': pred_ref_id,
            'confidence': confidence,
            'true_title': job.normalized_title,
            'pred_title': ref_title
        })

print("\n" + "=" * 60)
print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
print("=" * 60)
total = correct + incorrect
accuracy = correct / total * 100 if total > 0 else 0
print(f"Всего протестировано: {total}")
print(f"Правильно: {correct}")
print(f"Неправильно: {incorrect}")
print(f"Точность (accuracy): {accuracy:.2f}%")
print(f"Классификаций с низкой уверенностью (< 0.6): {low_confidence}")

if results:
    print("\nПримеры ошибок (первые 5):")
    for i, err in enumerate(results[:5]):
        print(f"\n{i+1}. '{err['original']}'")
        print(f"   Ожидаемый эталон ID: {err['true_ref']} ('{err['true_title']}')")
        print(f"   Предсказанный эталон ID: {err['pred_ref']} ('{err['pred_title']}')")
        print(f"   Уверенность: {err['confidence']:.3f}")

print("\nАнализ влияния порога уверенности:")
thresholds = [0.5, 0.6, 0.7, 0.8, 0.9]
for th in thresholds:

    corr = 0
    total_candidates = 0
    for job in test_sample:
        pred_ref_id, conf, _ = classify(job.original_title, threshold=th)
        if pred_ref_id is not None:
            total_candidates += 1
            if pred_ref_id == job.reference_id:
                corr += 1

    if total_candidates > 0:
        acc_th = corr / total_candidates * 100
        coverage = total_candidates / len(test_sample) * 100
        print(f"  Порог {th}: принято {total_candidates}/{len(test_sample)} ({coverage:.1f}%), "
              f"точность среди принятых = {acc_th:.2f}%")
    else:
        print(f"  Порог {th}: принято 0 записей")

session.close()