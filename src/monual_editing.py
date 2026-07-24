import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
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

print("\nРУЧНОЙ ПРОСМОТР И РЕДАКТИРОВАНИЕ ДОЛЖНОСТЕЙ")
print("-" * 50)

show_only_unverified = input("Показывать только непроверенные записи (is_manual_verified=False)? (y/n): ").strip().lower() == 'y'

query = session.query(JobTitle)
if show_only_unverified:
    query = query.filter(JobTitle.is_manual_verified == False)

jobs = query.order_by(JobTitle.id).all()
total = len(jobs)
print(f"Найдено записей: {total}")

if total == 0:
    print("Нет записей для просмотра.")
    session.close()
    exit()

current_index = 0

while current_index < total:
    job = jobs[current_index]

    print("\n" + "=" * 60)
    print(f"Запись {current_index + 1}/{total} (ID: {job.id})")
    print(f"original_title:   {job.original_title}")
    print(f"cleaned_title:    {job.cleaned_title}")
    print(f"normalized_title: {job.normalized_title}")
    print(f"is_ai_processed:  {job.is_ai_processed}")
    print(f"processing_method:{job.processing_method}")
    print(f"is_manual_verified: {job.is_manual_verified}")
    print("=" * 60)

    print("\nДействия:")
    print("  1 – Редактировать normalized_title")
    print("  2 – Переключить is_manual_verified")
    print("  3 – Удалить запись")
    print("  4 – Перейти к следующей (без изменений)")
    print("  5 – Выйти")

    choice = input("\nВаш выбор (1-5): ").strip()

    if choice == '1':
        new_title = input("Введите новое значение normalized_title (Enter для отмены): ").strip()
        if new_title:
            job.normalized_title = new_title
            session.commit()
            print("normalized_title обновлён.")
        else:
            print("Отмена.")
        current_index += 1

    elif choice == '2':
        job.is_manual_verified = not job.is_manual_verified
        session.commit()
        print(f"is_manual_verified переключён на {job.is_manual_verified}")
        current_index += 1

    elif choice == '3':
        confirm = input("Вы уверены, что хотите удалить запись? (y/n): ").strip().lower()
        if confirm == 'y':
            session.delete(job)
            session.commit()
            print("Запись удалена.")
            jobs.pop(current_index)
            total -= 1
            if current_index >= total:
                break
        else:
            print("Удаление отменено.")
            current_index += 1

    elif choice == '4':
        current_index += 1

    elif choice == '5':
        print("Выход.")
        break

    else:
        print("Неверный ввод, попробуйте снова.")

print("\nПросмотр завершён.")
session.close()