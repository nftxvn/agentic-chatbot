#!/usr/bin/env python3
"""Exercise durable cleanup across real Chroma/API outages on disposable services.

Vector batches are synthetic fixtures, not inference-timing tests. Native PDF
extraction, cookie HTTP, shared SQL outbox and the background drainer are real.
"""

import argparse
import signal
import sys
from pathlib import Path
from urllib.parse import unquote

import chromadb
import fitz
import httpx
import pymysql
from celery import Celery

from run_document_pipeline import AI, Run


def exercise(run):
    native = run.root / "cleanup-native.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page()
        content = "PANDUAN PEMULIHAN CLEANUP SINTETIS\n\n" + (
            "Petugas memeriksa berkas registrasi dan tanggal penerimaan. "
            "Dokumen ini hanya menguji pemulihan pada layanan sementara. " * 4
        )
        assert page.insert_textbox(fitz.Rect(45, 60, 550, 780), content, fontsize=15) >= 0
        assert len(page.get_text()) > 300
        pdf.save(native)

    def sql(query, args=()):
        with pymysql.connect(host="127.0.0.1", port=run.ports["mysql"], user="integration",
                             password=run.db_password, database=run.db_name, autocommit=True,
                             cursorclass=pymysql.cursors.DictCursor) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, args)
                return cursor.fetchall() if cursor.description else cursor.rowcount

    def document(document_id):
        rows = sql("SELECT processing_token, cancellation_requested, status FROM documents WHERE id=%s", (document_id,))
        return rows[0] if rows else None

    control = Celery("isolated_cleanup_control", broker=run.env["CELERY_BROKER_URL"])
    try:
        with httpx.Client(base_url=run.laravel_url, trust_env=False, timeout=90,
                          headers={"Accept": "application/json", "Origin": run.laravel_url,
                                   "Referer": run.laravel_url + "/"}) as client:
            def request(method, path, expected=200, **kwargs):
                csrf = client.cookies.get("XSRF-TOKEN")
                response = client.request(method, path, headers={"X-XSRF-TOKEN": unquote(csrf)} if csrf else {}, **kwargs)
                assert response.status_code == expected, f"{method} {path}: HTTP {response.status_code}, expected {expected}"
                return response

            request("GET", "/sanctum/csrf-cookie", 204)
            request("POST", "/api/auth/login", json={"email": "integration@example.test", "password": run.admin_password})
            ids = []
            for name in ("Cancel and resume A", "Replace B", "Delete C", "Unaffected D"):
                with native.open("rb") as file:
                    result = request("POST", "/api/documents", 201, data={"title": name, "category_id": str(run.category_id)},
                                     files={"pdf_file": (native.name, file, "application/pdf")})
                ids.append(result.json()["data"]["document"]["id"])
            def reviewed():
                states = [request("GET", f"/api/documents/{doc}/extraction").json()["data"]["status"] for doc in ids]
                assert "gagal" not in states
                return all(state == "menunggu_koreksi" for state in states)
            run.wait_for(reviewed, 90, "native documents did not reach review")
            replies = control.control.cancel_consumer("celery", reply=True, timeout=10, limit=1)
            assert replies and all("ok" in response for reply in replies for response in reply.values())
            a, b, c, d = ids
            request("POST", f"/api/documents/{a}/embed", 202, json={})
            cancelled_token = document(a)["processing_token"]
            old_b_token = document(b)["processing_token"]
            collection = chromadb.HttpClient(host="127.0.0.1", port=run.ports["chroma"]).get_or_create_collection("documents")
            def vector(key, doc, token=None):
                metadata = {"document_id": doc, "page_number": 1, "chunk_index": 0, "chunk_type": "parent"}
                if token:
                    metadata["operation_token"] = token
                collection.upsert(ids=[key], embeddings=[[0.1, 0.2]], documents=[f"Synthetic cleanup vector {key}"], metadatas=[metadata])
            vector("cancelled-partial", a, cancelled_token)
            vector("reused-id", a, cancelled_token)
            vector("replace-legacy", b)
            vector("delete-legacy", c)
            vector("unaffected", d, document(d)["processing_token"])
            run.check("native_documents_reviewed_and_partial_legacy_vector_fixtures_ready")

            run.stop_owned("chroma")
            request("POST", f"/api/documents/{a}/cancel", json={})
            jobs = sql("SELECT * FROM document_vector_cleanups WHERE document_id=%s", (a,))
            assert len(jobs) == 1 and jobs[0]["operation_token"] == cancelled_token and jobs[0]["attempts"] >= 1
            request("POST", f"/api/documents/{a}/extraction", 202, json={})
            resumed_token = document(a)["processing_token"]
            assert resumed_token != cancelled_token
            assert sql("SELECT COUNT(*) AS n FROM document_vector_cleanups WHERE document_id=%s", (a,))[0]["n"] == 1
            run.check("chroma_outage_persists_cancel_cleanup_across_immediate_resume")

            with native.open("rb") as file:
                request("POST", f"/api/documents/{b}/replace", files={"pdf_file": ("replacement.pdf", file, "application/pdf")})
            assert document(b)["processing_token"] == old_b_token
            assert document(b)["cancellation_requested"] == 1
            assert document(b)["status"] == "pending"
            assert sql("SELECT id FROM document_vector_cleanups WHERE document_id=%s AND operation_token=''", (b,))
            run.check("replacement_start_waits_for_full_cleanup_during_chroma_outage")

            run.stop_owned("fastapi")
            request("DELETE", f"/api/documents/{c}")
            assert document(c) is None
            assert sql("SELECT id FROM document_vector_cleanups WHERE document_id=%s AND operation_token=''", (c,))
            run.check("laravel_delete_retains_cleanup_tombstone_when_python_is_offline")

            run.spawn("fastapi-restarted", [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(run.ports["ai"])], AI)
            def api_up():
                try:
                    return httpx.get(run.ai_url + "/openapi.json", timeout=2, trust_env=False).status_code == 200
                except httpx.RequestError:
                    return False
            run.wait_for(api_up, 45, "restarted API was unavailable")
            run.wait_for(lambda: all(row["attempts"] >= 1 for row in sql("SELECT attempts FROM document_vector_cleanups")),
                         45, "API startup did not retry durable cleanup")
            run.spawn("chroma-restarted", [str(Path(sys.executable).parent / "chroma"), "run", "--path", str(run.root / "chroma"),
                                           "--host", "127.0.0.1", "--port", str(run.ports["chroma"])])
            def chroma_up():
                try:
                    return httpx.get(f"http://127.0.0.1:{run.ports['chroma']}/api/v2/heartbeat", timeout=2, trust_env=False).status_code == 200
                except httpx.RequestError:
                    return False
            run.wait_for(chroma_up, 40, "restarted Chroma was unavailable")
            vector("reused-id", a, resumed_token)
            # Advance only fixture retry deadlines; the actual API loop drains them.
            sql("UPDATE document_vector_cleanups SET available_at=UTC_TIMESTAMP()")
            run.wait_for(lambda: not sql("SELECT id FROM document_vector_cleanups"), 90, "background cleanup did not recover after restart")
            remaining = set(collection.get()["ids"])
            assert remaining == {"reused-id", "unaffected"}, remaining
            assert document(a)["processing_token"] == resumed_token
            run.check("api_restart_and_chroma_recovery_clean_old_scopes_preserving_new_generation_and_other_document")

            request("POST", f"/api/documents/{b}/extraction", 202, json={})
            assert document(b)["processing_token"] != old_b_token
            replies = control.control.add_consumer("celery", reply=True, timeout=10, limit=1)
            assert replies and all("ok" in response for reply in replies for response in reply.values())
            def resumed_review():
                return all(request("GET", f"/api/documents/{doc}/extraction").json()["data"]["status"] == "menunggu_koreksi" for doc in (a, b))
            run.wait_for(resumed_review, 90, "resumed/replacement extraction did not complete after cleanup")
            assert set(collection.get()["ids"]) == remaining
            run.check("replacement_can_resume_after_cleanup_without_deleting_other_vectors")
            request("POST", "/api/auth/logout", json={})
    finally:
        control.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--vision-model", default="qwen2.5vl:7b-q4_K_M")
    parser.add_argument("--chat-model", default="qwen2.5:3b")
    run = Run(parser.parse_args())
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    print(f"Artifacts: {run.root}", flush=True)
    code = 1
    try:
        run.prepare()
        run.start_apps()
        exercise(run)
        run.report["status"] = "passed"
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        message = str(error)
        for secret in run.secrets:
            message = message.replace(secret, "[redacted]")
        run.report.update(status="failed", error={"type": type(error).__name__, "message": message})
        print(f"FAIL {type(error).__name__}: {message}", flush=True)
    finally:
        run.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
