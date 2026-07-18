import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import pdist
import normalize_utils as nu
from models import JobTitle, ReferenceTitle


try:
    import plotly.express as px
    import plotly.graph_objects as go
    USE_PLOTLY = True
except ImportError:
    USE_PLOTLY = False
    print("Plotly не установлен, будут использоваться статические графики matplotlib.")

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


print("1. Загрузка данных...")

jobs = session.query(JobTitle).filter(
    JobTitle.normalized_title.isnot(None),
    JobTitle.reference_id.isnot(None)
).all()

if not jobs:
    print("Нет записей с reference_id. Сначала запустите build_reference.py")
    sys.exit(1)


data = {
    'id': [j.id for j in jobs],
    'normalized_title': [j.normalized_title for j in jobs],
    'reference_id': [j.reference_id for j in jobs]
}
df = pd.DataFrame(data)


refs = session.query(ReferenceTitle).all()
ref_map = {r.id: r for r in refs}
df['cluster'] = df['reference_id'].map(lambda x: ref_map[x].cluster_id if x in ref_map else None)
df['canonical'] = df['reference_id'].map(lambda x: ref_map[x].canonical_title if x in ref_map else None)


df = df.dropna(subset=['cluster'])
print(f"Загружено {len(df)} записей с кластерами.")


print("2. Векторизация...")
unique_titles = df['normalized_title'].tolist()

vectorizer = TfidfVectorizer(
    analyzer='char_wb',
    ngram_range=(2, 4),
    min_df=1
)
X = vectorizer.fit_transform(unique_titles)
print(f"   Матрица размером {X.shape}")


print("3. Проекция на 2D с помощью t-SNE... (может занять время)")

pca = PCA(n_components=50, random_state=42)
X_pca = pca.fit_transform(X.toarray())
tsne = TSNE(n_components=2, random_state=42, perplexity=30, max_iter=1000)
X_tsne = tsne.fit_transform(X_pca)
print("   t-SNE завершён.")

df['tsne_x'] = X_tsne[:, 0]
df['tsne_y'] = X_tsne[:, 1]


print("4. Построение графиков...")

if USE_PLOTLY:

    fig = px.scatter(
        df, x='tsne_x', y='tsne_y',
        color='cluster', hover_data=['normalized_title', 'canonical'],
        title='t-SNE проекция кластеров должностей',
        labels={'tsne_x': 't-SNE 1', 'tsne_y': 't-SNE 2'}
    )
    fig.write_html('clusters_tsne_plotly.html')
    print("   Интерактивный график сохранён в clusters_tsne_plotly.html")
else:

    plt.figure(figsize=(12, 8))
    scatter = plt.scatter(df['tsne_x'], df['tsne_y'], c=df['cluster'], cmap='tab20', alpha=0.6, s=10)
    plt.title('t-SNE проекция кластеров должностей')
    plt.xlabel('t-SNE 1')
    plt.ylabel('t-SNE 2')
    plt.colorbar(scatter, label='Кластер')
    plt.tight_layout()
    plt.savefig('clusters_tsne_matplotlib.png', dpi=150)
    print("   График сохранён в clusters_tsne_matplotlib.png")
    plt.show()


print("5. Построение дендрограммы (на основе 100 случайных записей)...")
sample_df = df.sample(min(100, len(df)), random_state=42)
sample_titles = sample_df['normalized_title'].tolist()
vectorizer_sample = TfidfVectorizer(
    analyzer='char_wb',
    ngram_range=(2, 4),
    min_df=1
)
X_sample = vectorizer_sample.fit_transform(sample_titles)
dist_sample = pdist(X_sample.toarray(), metric='cosine')
Z = linkage(dist_sample, method='average')

plt.figure(figsize=(15, 6))
dendrogram(Z, labels=sample_titles, leaf_rotation=90, leaf_font_size=8)
plt.title('Дендрограмма (выборка)')
plt.xlabel('Должность')
plt.ylabel('Расстояние')
plt.tight_layout()
plt.savefig('dendrogram_sample.png', dpi=150)
print("   Дендрограмма сохранена в dendrogram_sample.png")
plt.show()

print("\nВизуализация завершена.")
session.close()