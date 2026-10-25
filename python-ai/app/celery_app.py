"""Satu instance Celery untuk seluruh task dokumen.

Registrasi task tetap dilakukan oleh app.tasks.process_document; path worker
lama dan alias app.tasks.celery tetap memakai instance yang dibuat di sini.
"""

from celery import Celery

from app.config import settings

# Inisialisasi Celery app
celery_app = Celery(
    "ai_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Konfigurasi tambahan Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Jakarta",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # Acknowledge setelah task selesai (lebih aman)
    worker_prefetch_multiplier=1,  # Proses satu task pada satu waktu
    worker_concurrency=1,  # Kunci 1 worker eksklusif untuk inferensi GPU stabil
)

