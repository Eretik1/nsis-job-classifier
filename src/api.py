import sys
import os
from pathlib import Path
from typing import List, Optional

# Добавляем корневую папку проекта в sys.path
root_dir = Path(__file__).parent.parent  # папка practice
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

import classify_job
from models import JobTitle, ReferenceTitle

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

app = FastAPI(
    title="Классификатор должностей",
    description="API для классификации должностей по эталонному справочнику НСИ",
    version="1.0.0"
)

class ClassifyRequest(BaseModel):
    titles: List[str]

class ClassifyResponseItem(BaseModel):
    original: str
    normalized: str
    reference_id: Optional[int]
    reference_title: Optional[str]
    confidence: float
    success: bool
    message: Optional[str] = None

class ClassifyResponse(BaseModel):
    results: List[ClassifyResponseItem]

class ReferenceItem(BaseModel):
    id: int
    canonical_title: str
    cluster_id: int
    cluster_size: int

class StatsResponse(BaseModel):
    total_records: int
    with_reference: int
    llm_processed: int
    algorithm_processed: int
    manual_verified: int

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def root():
    return {
        "message": "API классификатора должностей",
        "endpoints": {
            "/docs": "Swagger документация",
            "/classify": "POST - классификация списка должностей",
            "/reference": "GET - эталонный справочник",
            "/stats": "GET - статистика"
        }
    }

@app.post("/classify", response_model=ClassifyResponse)
async def classify_titles(request: ClassifyRequest):
    results = []
    for title in request.titles:
        try:
            ref_id, confidence, ref_title = classify_job.classify(title, threshold=0.6)
            if ref_id is not None:
                results.append(
                    ClassifyResponseItem(
                        original=title,
                        normalized=classify_job.normalize_input(title),
                        reference_id=ref_id,
                        reference_title=ref_title,
                        confidence=confidence,
                        success=True
                    )
                )
            else:
                results.append(
                    ClassifyResponseItem(
                        original=title,
                        normalized=classify_job.normalize_input(title),
                        reference_id=None,
                        reference_title=None,
                        confidence=confidence,
                        success=False,
                        message="Уверенность ниже порога"
                    )
                )
        except Exception as e:
            results.append(
                ClassifyResponseItem(
                    original=title,
                    normalized="",
                    reference_id=None,
                    reference_title=None,
                    confidence=0.0,
                    success=False,
                    message=f"Ошибка классификации: {str(e)}"
                )
            )
    return ClassifyResponse(results=results)

@app.get("/reference", response_model=List[ReferenceItem])
async def get_reference():
    db = next(get_db())
    refs = db.query(ReferenceTitle).all()
    return [
        ReferenceItem(
            id=r.id,
            canonical_title=r.canonical_title,
            cluster_id=r.cluster_id,
            cluster_size=r.cluster_size
        )
        for r in refs
    ]

@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    db = next(get_db())
    total = db.query(JobTitle).count()
    with_ref = db.query(JobTitle).filter(JobTitle.reference_id.isnot(None)).count()
    llm = db.query(JobTitle).filter(JobTitle.processing_method == 'llm').count()
    algo = db.query(JobTitle).filter(JobTitle.processing_method == 'algorithm').count()
    manual = db.query(JobTitle).filter(JobTitle.is_manual_verified == True).count()

    return StatsResponse(
        total_records=total,
        with_reference=with_ref,
        llm_processed=llm,
        algorithm_processed=algo,
        manual_verified=manual
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api:app", host="0.0.0.0", port=8000, reload=True)