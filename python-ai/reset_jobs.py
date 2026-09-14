"""Setel ulang status ekstraksi yang tertahan dari sesi sebelumnya."""
from app.tasks.process_document import celery_app  # noqa: F401
from app.services.ekstraksi_bertahap import PenyimpananMySQL

p = PenyimpananMySQL()
with p._engine.begin() as conn:
    from sqlalchemy import text
    r = conn.execute(text(
        "UPDATE ekstraksi_job SET status = 'jeda', jeda_diminta = 0 "
        "WHERE status IN ('berjalan', 'antre')"
    ))
    if r.rowcount:
        print(f"  {r.rowcount} tugas disetel ke 'jeda'.")
    else:
        print("  Tidak ada tugas yang perlu disetel ulang.")
