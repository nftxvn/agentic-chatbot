"""Cancellation scenarios using only the disposable services owned by the runner."""

import base64
import json
from urllib.parse import unquote

import chromadb
import fitz
import httpx
import pymysql
import redis
from celery import Celery


def run_cancellation_cases(run):
    broker = redis.Redis.from_url(run.env["CELERY_BROKER_URL"])
    results = redis.Redis.from_url(run.env["CELERY_RESULT_BACKEND"])
    control = Celery("isolated_cancellation_control", broker=run.env["CELERY_BROKER_URL"])

    def consumption(enabled):
        # Stop consumption, rather than SIGSTOP: a blocked Redis pop can reserve
        # one message in a stopped process's socket before it reads the reply.
        command = control.control.add_consumer if enabled else control.control.cancel_consumer
        replies = command("celery", reply=True, timeout=10, limit=1)
        assert replies and all("ok" in response for reply in replies for response in reply.values()), "owned worker did not acknowledge queue consumption change"
        def applied():
            queues = control.control.inspect(timeout=3, limit=1).active_queues()
            return queues and all(any(queue["name"] == "celery" for queue in values) == enabled for values in queues.values())
        # A solo worker can start OCR immediately after add_consumer, so it
        # cannot answer inspection RPC until that inference ends. SQL progress
        # below proves reception. Only inspect the idle disabled consumer.
        if not enabled:
            run.wait_for(applied, 15, "owned worker did not apply queue consumption change")
    native = run.root / "native-cancellation.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page()
        content = (
            "DOKUMEN SINTETIS PENGUJIAN PEMBATALAN\n\n"
            "Dokumen ini hanya digunakan untuk menguji isolasi antrean. "
            "Petugas memeriksa nomor registrasi, mencatat kelengkapan berkas "
            "dan memberikan tanda terima kepada pemohon. Seluruh identitas "
            "serta isi merupakan data sintetis. Halaman teks native ini dapat "
            "diproses tanpa panggilan vision. Pembatalan dokumen lain tidak "
            "boleh menghilangkan tugas dokumen ini dari antrean worker."
        )
        assert page.insert_textbox(fitz.Rect(45, 60, 550, 780), content, fontsize=15) >= 0
        assert len(page.get_text()) > 300
        pdf.save(native)

    def document(document_id):
        with pymysql.connect(host="127.0.0.1", port=run.ports["mysql"], user="integration",
                             password=run.db_password, database=run.db_name,
                             cursorclass=pymysql.cursors.DictCursor) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT processing_token, cancellation_requested, status FROM documents WHERE id=%s", (document_id,))
                return cursor.fetchone()

    def queued_task(document_id):
        for raw in broker.lrange("celery", 0, -1):
            message = json.loads(raw)
            args, kwargs, _options = json.loads(base64.b64decode(message["body"]))
            if args and args[0] == document_id:
                return {"id": message["headers"]["id"], "token": kwargs.get("_operation_token")}
        raise AssertionError("document task missing from owned broker")

    def cancelled_result(task):
        raw = results.get("celery-task-meta-" + task["id"])
        if raw:
            result = json.loads(raw)
            assert result["status"] == "SUCCESS", "cancelled work retried/failed instead of being discarded"
            assert result["result"]["status"] == "dibatalkan", "obsolete task persisted a successful result"
            return result
        return None

    try:
        with httpx.Client(base_url=run.laravel_url, trust_env=False, timeout=60,
                          headers={"Accept": "application/json", "Origin": run.laravel_url,
                                   "Referer": run.laravel_url + "/"}) as client:
            def request(method, path, expected=200, **kwargs):
                csrf = client.cookies.get("XSRF-TOKEN")
                headers = {"X-XSRF-TOKEN": unquote(csrf)} if csrf else {}
                response = client.request(method, path, headers=headers, **kwargs)
                assert response.status_code == expected, f"{method} {path}: HTTP {response.status_code}, expected {expected}"
                return response

            request("GET", "/sanctum/csrf-cookie", 204)
            request("POST", "/api/auth/login", json={"email": "integration@example.test", "password": run.admin_password})

            def upload(path, title):
                with path.open("rb") as fixture:
                    response = request("POST", "/api/documents", 201,
                                       data={"title": title, "category_id": str(run.category_id)},
                                       files={"pdf_file": (path.name, fixture, "application/pdf")})
                return response.json()["data"]["document"]["id"]

            def state(document_id):
                return request("GET", f"/api/documents/{document_id}/extraction").json()["data"]

            def until_review(document_id):
                value = state(document_id)
                assert value["status"] != "gagal", f"unrelated/resumed document {document_id} failed"
                return value if value["status"] == "menunggu_koreksi" else None

            consumption(False)
            cancelled = upload(native, "Queued cancellation A")
            unaffected = upload(native, "Unaffected document B")
            old_task = queued_task(cancelled)
            other_task = queued_task(unaffected)
            assert broker.llen("celery") == 2
            request("POST", f"/api/documents/{cancelled}/cancel", json={})
            assert broker.llen("celery") == 2, "cancellation removed messages from the shared queue"
            assert queued_task(unaffected) == other_task
            assert document(cancelled)["cancellation_requested"] == 1
            consumption(True)
            run.wait_for(lambda: until_review(unaffected), 90, "unrelated queued document did not finish")
            run.wait_for(lambda: cancelled_result(old_task), 30, "cancelled queued task was not discarded")
            assert request("GET", f"/api/documents/{cancelled}/pages").json()["data"]["halaman"] == []
            assert state(cancelled)["status"] == "gagal"
            run.check("cancel_queued_A_keeps_B_message_and_B_finishes_without_A_writes")

            consumption(False)
            active = upload(run.root / "fixture.pdf", "Active OCR cancellation C")
            active_task = queued_task(active)
            consumption(True)
            run.wait_for(lambda: state(active)["status"] == "berjalan", 60, "OCR task never became active")
            next_document = upload(native, "Queued behind active OCR D")
            request("POST", f"/api/documents/{active}/cancel", json={})
            assert document(active)["cancellation_requested"] == 1
            request("POST", f"/api/documents/{active}/extraction", 202, json={})
            resumed_token = document(active)["processing_token"]
            assert resumed_token != active_task["token"]
            run.wait_for(lambda: until_review(next_document), 360, "document behind cancelled OCR did not finish")
            run.wait_for(lambda: cancelled_result(active_task), 30, "active obsolete OCR task was not discarded")
            assert request("GET", f"/api/documents/{active}/pages").json()["data"]["halaman"] == [], "old OCR result survived immediate resume"
            run.check("active_OCR_cancel_then_immediate_resume_discards_old_result_and_keeps_D")
            run.wait_for(lambda: until_review(active), 360, "new OCR generation did not finish")
            pages = request("GET", f"/api/documents/{active}/pages").json()["data"]["halaman"]
            assert [page["page_number"] for page in pages] == [1, 2]
            assert document(active)["processing_token"] == resumed_token
            run.check("resumed_generation_finishes_with_two_pages_and_no_duplicate_old_writes")

            # The standard smoke run completed this corpus. Re-embedding starts
            # a new generation; a synthetic partial vector exercises cleanup
            # without timing a model batch or altering any production index.
            completed = run.report["document_id"]
            before = request("GET", f"/api/documents/{completed}/chunks").json()["chunks"]
            assert before
            request("POST", f"/api/documents/{completed}/cancel", json={})
            assert request("GET", f"/api/documents/{completed}/chunks").json()["chunks"] == before, "cancel after completion removed a committed corpus"
            consumption(False)
            request("POST", f"/api/documents/{completed}/embed", 202, json={})
            embedding_task = queued_task(completed)
            token = document(completed)["processing_token"]
            collection = chromadb.HttpClient(host="127.0.0.1", port=run.ports["chroma"]).get_collection("documents")
            existing = collection.get(ids=[before[0]["id"]], include=["embeddings"])
            partial_id = f"doc_{completed}_parent_999999"
            collection.upsert(ids=[partial_id], embeddings=[existing["embeddings"][0]],
                              documents=["Synthetic partially written generation"],
                              metadatas=[{"document_id": completed, "operation_token": token,
                                          "chunk_type": "parent", "chunk_index": 999999, "page_number": 1}])
            request("POST", f"/api/documents/{completed}/cancel", json={})
            assert collection.get(ids=[partial_id])["ids"] == []
            assert request("GET", f"/api/documents/{completed}/chunks").json()["chunks"] == before
            consumption(True)
            run.wait_for(lambda: cancelled_result(embedding_task), 30, "queued cancelled embedding was not discarded")
            assert state(completed)["status"] == "gagal"
            run.check("cancel_embedding_cleans_only_current_partial_vectors_and_preserves_committed_corpus")
            request("POST", "/api/auth/logout", json={})
    finally:
        control.close()
        broker.close()
        results.close()
