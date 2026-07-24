import os
import time
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.spatial.distance import pdist
from scipy.cluster.hierarchy import linkage, fcluster
from tqdm import tqdm

import normalize_utils as nu
from models import JobTitle, ReferenceTitle

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

print("\nПОСТРОЕНИЕ ЭТАЛОННОЙ НСИ")
print("-" * 60)

print("1. Загрузка нормализованных должностей...")
print("Выберите какие записи использовать для построения эталона:")
print("  1 - только обработанные LLM (рекомендуется)")
print("  2 - только проверенные вручную (наиболее качественные)")
print("  3 - все записи (включая алгоритмически обработанные)")
print("  4 - только обработанные LLM и проверенные вручную")
choice = input("Ваш выбор (1-4): ").strip()

if choice == '1':
    only_llm_processed = True
    only_manual_verified = False
    mode_desc = "только LLM"
elif choice == '2':
    only_llm_processed = False
    only_manual_verified = True
    mode_desc = "только проверенные вручную"
elif choice == '3':
    only_llm_processed = False
    only_manual_verified = False
    mode_desc = "все записи"
elif choice == '4':
    only_llm_processed = True
    only_manual_verified = True
    mode_desc = "LLM и проверенные вручную"
else:
    print("Неверный выбор, используется вариант 1 (только LLM)")
    only_llm_processed = True
    only_manual_verified = False
    mode_desc = "только LLM (по умолчанию)"

print(f"   Режим: {mode_desc}")
df = nu.get_normalized_jobs(
    session=session,
    only_manual_verified=only_manual_verified,
    only_llm_processed=only_llm_processed,
    exclude_empty=True
)
print(f"   Загружено {len(df)} записей.")

if df.empty:
    print("   Нет данных для построения эталона. Завершение.")
    exit(0)


print("2. Группировка дубликатов...")
freq = df['normalized_title'].value_counts()
unique_df = pd.DataFrame({
    'normalized_title': freq.index,
    'frequency': freq.values
})
unique_titles = unique_df['normalized_title'].tolist()
print(f"   Уникальных названий: {len(unique_titles)}")

if len(unique_titles) < 2:
    print("   Слишком мало уникальных названий для кластеризации. Завершение.")
    exit(0)


print("3. Векторизация уникальных названий...")

def get_first_words(text, n=2):
    words = text.split()
    return ' '.join(words[:n]) if len(words) >= n else text

vectorizer_main = TfidfVectorizer(
    analyzer='char_wb',
    ngram_range=(2, 4),
    min_df=1
)
X_main = vectorizer_main.fit_transform(unique_titles)

vectorizer_first = TfidfVectorizer(
    analyzer='word',
    ngram_range=(1, 2),
    min_df=1
)
first_words = [get_first_words(t, 2) for t in unique_titles]
X_first = vectorizer_first.fit_transform(first_words)

from scipy.sparse import hstack
weight_first = 2.0
X_combined = hstack([X_main, weight_first * X_first])
print(f"   Размер объединённой матрицы: {X_combined.shape}")


print("4. Расчёт расстояний... (может занять время)")
start_time = time.time()
dist_vector = pdist(X_combined.toarray(), metric='cosine')
print(f"   Время вычисления расстояний: {time.time() - start_time:.2f} сек.")


print("5. Кластеризация (автоматический подбор порога)...")
Z = linkage(dist_vector, method='average')
dists = Z[:, 2]
sorted_dists = np.sort(dists)

gaps = np.diff(sorted_dists)

max_gap_idx = np.argmax(gaps)

threshold = (sorted_dists[max_gap_idx] + sorted_dists[max_gap_idx + 1]) / 2

clusters = fcluster(Z, t=threshold, criterion='distance')
num_clusters = len(set(clusters))

print(f"   Автоматически выбран порог: {threshold:.4f}")
print(f"   Получено {num_clusters} кластеров")


print("6. Присвоение кластеров...")
cluster_map = dict(zip(unique_titles, clusters))
df['cluster'] = df['normalized_title'].map(cluster_map)
print("   Кластеры присвоены.")


print("7. Формирование эталонных названий...")
reference_list = []
for cluster_id in sorted(df['cluster'].unique()):
    cluster_df = df[df['cluster'] == cluster_id]

    canonical = cluster_df['normalized_title'].mode()[0]
    canonical = ' '.join(canonical.split())
    reference_list.append({
        'cluster_id': int(cluster_id),
        'canonical_title': canonical,
        'cluster_size': len(cluster_df)
    })
print(f"   Сформировано {len(reference_list)} эталонов.")


print("8. Сохранение эталона в БД...")
try:
    session.query(ReferenceTitle).delete()
    session.commit()
    print("   Старые эталоны удалены.")

    for ref in tqdm(reference_list, desc="Сохранение эталонов"):
        new_ref = ReferenceTitle(
            canonical_title=ref['canonical_title'],
            cluster_id=ref['cluster_id'],
            cluster_size=ref['cluster_size']
        )
        session.add(new_ref)
    session.commit()
    print(f"   Добавлено {len(reference_list)} эталонов.")

except Exception as e:
    print(f"   ОШИБКА при сохранении эталонов: {e}")
    session.rollback()
    exit(1)


print("9. Привязка эталонов к записям...")

ref_dict = {r.canonical_title: r.id for r in session.query(ReferenceTitle).all()}

jobs_to_update = session.query(JobTitle).filter(
    JobTitle.normalized_title.isnot(None),
    JobTitle.normalized_title != ''
).all()

updated = 0
for job in tqdm(jobs_to_update, desc="Обновление reference_id"):
    key = ' '.join(job.normalized_title.split())
    if key in ref_dict:
        job.reference_id = ref_dict[key]
        updated += 1

session.commit()
print(f"   Обновлено {updated} записей.")


print("\n10. Оценка качества эталона...")
print("-" * 50)

cluster_sizes = df['cluster'].value_counts().sort_index()
print(f"   Всего кластеров: {len(cluster_sizes)}")
print(f"   Средний размер кластера: {cluster_sizes.mean():.1f}")
print(f"   Минимальный размер кластера: {cluster_sizes.min()}")
print(f"   Максимальный размер кластера: {cluster_sizes.max()}")

singletons = cluster_sizes[cluster_sizes == 1].count()
print(f"   Кластеров-одиночек: {singletons} ({singletons/len(cluster_sizes)*100:.1f}%)")

print("\n   Топ-10 самых больших кластеров:")
top_clusters = cluster_sizes.nlargest(10)
for cluster_id, size in top_clusters.items():
    canonical = session.query(ReferenceTitle).filter_by(cluster_id=cluster_id).first()
    if canonical:
        print(f"      Кластер {cluster_id}: {size} записей -> '{canonical.canonical_title}'")

print("\n   Примеры кластеров (случайные 5):")
sample_clusters = cluster_sizes.sample(min(5, len(cluster_sizes))).index
for cluster_id in sample_clusters:
    titles = df[df['cluster'] == cluster_id]['normalized_title'].tolist()
    print(f"\n   Кластер {cluster_id} ({len(titles)} записей):")
    for t in titles[:5]:
        print(f"      - {t}")
    if len(titles) > 5:
        print(f"      ... и ещё {len(titles)-5}")

print("\n11. Сохранение отчёта...")
df[['id', 'normalized_title', 'cluster']].to_csv('clusters_report.csv', index=False)
print("   Отчёт сохранён в clusters_report.csv")

print("\nПОСТРОЕНИЕ ЭТАЛОНА ЗАВЕРШЕНО.")
session.close()