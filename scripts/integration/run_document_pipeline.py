#!/usr/bin/env python3
"""Exercise real HTTP/SQL/broker/model boundaries on disposable local services.

Run with python-ai/venv/bin/python. No existing database, Redis namespace,
Chroma collection, application configuration or frontend source is modified.
Only the already installed local Ollama service is shared. Logs and synthetic
fixtures remain under the printed temporary directory for inspection.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import traceback
from urllib.parse import unquote, urlparse

import fitz
import httpx
import pymysql


REPO = Path(__file__).resolve().parents[2]
AI = REPO / "python-ai"
LARAVEL = REPO / "laravel-admin"


def unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def fixture_pdf(path: Path) -> str:
    """First page has only raster pixels; second has >300 native characters."""
    scan_text = (
        "PANDUAN LAYANAN ARSIP SINTETIS\n\n"
        "Kode layanan: ARSIP-7429\n"
        "Dokumen ini hanya dipakai untuk pengujian integrasi.\n"
        "Pemohon menyerahkan formulir kepada petugas arsip.\n"
        "Petugas memeriksa nomor registrasi dan kelengkapan berkas.\n"
        "Waktu penyelesaian layanan adalah 25 menit kerja.\n"
        "Tidak ada data warga atau informasi operasional di sini.\n"
    )
    correction = (
        "# Panduan layanan arsip sintetis\n\n"
        "Kode layanan: ARSIP-9631.\n"
        "Waktu penyelesaian pengarsipan berkas ARSIP-9631 adalah 37 menit kerja.\n"
        "Biaya layanan pengarsipan berkas ARSIP-9631 adalah Rp 0.\n"
        "Pemohon menyerahkan formulir kepada petugas arsip. Petugas memeriksa "
        "nomor registrasi serta kelengkapan berkas dan memberikan tanda terima.\n"
        "Angka 37 menit merupakan koreksi manual untuk pengujian, "
        "menggantikan angka 25 menit pada citra awal.\n"
    )
    with fitz.open() as source, fitz.open() as result:
        page = source.new_page()
        assert page.insert_textbox(fitz.Rect(45, 60, 550, 780), scan_text, fontsize=17) >= 0
        scanned = result.new_page()
        scanned.insert_image(scanned.rect, stream=page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).tobytes("png"))
        page = result.new_page()
        native = (
            "INFORMASI TAMBAHAN ARSIP SINTETIS\n\n"
            "Dokumen pengujian integrasi ini memiliki dua halaman. Halaman pertama "
            "berupa citra yang harus dibaca model vision. Halaman kedua memuat teks "
            "native yang dapat diekstrak langsung dari PDF. Petugas menyimpan berkas "
            "sesuai urutan registrasi dan mencatat tanggal penerimaan. Korektor "
            "memeriksa hasil ekstraksi sebelum menyetujui penyimpanan ke korpus. "
            "Seluruh isi dan identitas pada dokumen ini adalah data sintetis."
        )
        assert page.insert_textbox(fitz.Rect(45, 60, 550, 780), native, fontsize=15) >= 0
        result.save(path)
        assert not result[0].get_text().strip()
        assert len(result[1].get_text()) > 300
    return correction


class Run:
    def __init__(self, args):
        self.args = args
        self.root = Path(tempfile.mkdtemp(prefix="agentic-integration-"))
        self.root.chmod(0o700)
        (self.root / ".agentic-integration-run").write_text("disposable integration run\n")
        self.processes = []
        self.expected_stops = set()
        self.logs = []
        self.started = time.monotonic()
        self.report = {"status": "running", "checks": [], "models": {
            "vision": args.vision_model, "chat": args.chat_model,
        }, "artifact_directory": str(self.root)}
        self.env = os.environ.copy()
        self.secrets = [secrets.token_urlsafe(32) for _ in range(4)]
        self.db_password, self.token, self.admin_password, self.api_key = self.secrets
        self.db_name = "agentic_integration_" + secrets.token_hex(6)
        self.ports = dict(zip(("mysql", "redis", "chroma", "ai", "laravel"), [unused_port() for _ in range(5)]))
        assert len(set(self.ports.values())) == 5
        self.ai_url = f"http://127.0.0.1:{self.ports['ai']}"
        self.laravel_url = f"http://127.0.0.1:{self.ports['laravel']}"
        self.ollama_url = args.ollama_url.rstrip("/")
        self.report["ports"] = self.ports
        self.report["vector_store_mode"] = "http_single_server"

    def check(self, name, detail=None):
        item = {"name": name, "status": "passed", "elapsed_seconds": round(time.monotonic() - self.started, 2)}
        if detail is not None:
            item["detail"] = detail
        self.report["checks"].append(item)
        print(f"PASS {name}", flush=True)
        self.save()

    def save(self):
        (self.root / "report.json").write_text(json.dumps(self.report, indent=2, ensure_ascii=False) + "\n")

    def spawn(self, name, command, cwd=None):
        log = (self.root / f"{name}.log").open("w")
        self.logs.append(log)
        process = subprocess.Popen(command, cwd=cwd, env=self.env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        self.processes.append((name, process))
        return process

    def wait_for(self, callback, timeout, description):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for name, process in self.processes:
                if process.poll() is not None and process.pid not in self.expected_stops:
                    raise RuntimeError(f"{name} exited with code {process.returncode}; inspect its isolated log")
            result = callback()
            if result:
                return result
            time.sleep(0.3)
        raise TimeoutError(description)

    def stop_owned(self, name):
        """Stop a service for an outage scenario while retaining its shutdown audit."""
        for service, process in reversed(self.processes):
            if service != name or process.poll() is not None:
                continue
            self.expected_stops.add(process.pid)
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            return
        raise RuntimeError(f"No running owned service named {name}")

    def prepare(self):
        if urlparse(self.ollama_url).hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("Ollama must be local for this runner")
        for name in ("mysqld", "redis-server", "php"):
            if not shutil.which(name):
                raise RuntimeError(f"required binary missing: {name}")
        with httpx.Client(trust_env=False, timeout=5) as client:
            response = client.get(self.ollama_url + "/api/tags")
            response.raise_for_status()
            installed = {item["name"] for item in response.json()["models"]}
            for model in (self.args.vision_model, self.args.chat_model, "bge-m3:latest"):
                if model not in installed:
                    raise RuntimeError(f"required installed model missing: {model}; runner never downloads models")
            response = client.get(self.ollama_url + "/api/ps")
            response.raise_for_status()
            self.report["initially_loaded_models"] = [item["name"] for item in response.json().get("models", [])]

        for relative in ("mysql", "redis", "bootstrap-cache", "storage/framework/cache/data", "storage/framework/sessions", "storage/framework/views", "storage/logs"):
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        cache = self.root / "bootstrap-cache"
        self.env.update({
            "AGENTIC_INTEGRATION_RUN": "1", "INTEGRATION_RUN_DIR": str(self.root),
            "INTEGRATION_ADMIN_EMAIL": "integration@example.test", "INTEGRATION_ADMIN_PASSWORD": self.admin_password,
            "INTEGRATION_API_KEY": self.api_key, "INTEGRATION_VISION_MODEL": self.args.vision_model,
            "LARAVEL_STORAGE_PATH": str(self.root / "storage"),
            "APP_ENV": "local", "APP_DEBUG": "false", "APP_URL": self.laravel_url,
            "APP_KEY": "base64:" + base64.b64encode(secrets.token_bytes(32)).decode(),
            "DB_CONNECTION": "mysql", "DB_HOST": "127.0.0.1", "DB_PORT": str(self.ports["mysql"]),
            "DB_DATABASE": self.db_name, "DB_USERNAME": "integration", "DB_PASSWORD": self.db_password,
            "DB_URL": "", "DB_SOCKET": "", "MYSQL_HOST": "127.0.0.1", "MYSQL_PORT": str(self.ports["mysql"]),
            "MYSQL_DATABASE": self.db_name, "MYSQL_USER": "integration", "MYSQL_PASSWORD": self.db_password,
            "REDIS_HOST": "127.0.0.1", "REDIS_PORT": str(self.ports["redis"]), "REDIS_PASSWORD": "null",
            "REDIS_URL": "", "CHAT_REDIS_URL": f"redis://127.0.0.1:{self.ports['redis']}/2",
            "CELERY_BROKER_URL": f"redis://127.0.0.1:{self.ports['redis']}/0",
            "CELERY_RESULT_BACKEND": f"redis://127.0.0.1:{self.ports['redis']}/1",
            "AI_SERVICE_URL": self.ai_url, "AI_SERVICE_TOKEN": self.token, "INTERNAL_API_TOKEN": self.token,
            "LARAVEL_BASE_URL": self.laravel_url,
            "OLLAMA_BASE_URL": self.ollama_url, "OLLAMA_URL": self.ollama_url,
            "VISION_MODEL_NAME": self.args.vision_model, "LLM_MODEL_NAME": self.args.chat_model,
            "VISION_TIMEOUT": "300", "LLM_NUM_CTX": "4096", "LLM_NUM_GPU": "0",
            "EMBEDDING_MODEL_NAME": "BAAI/bge-m3", "EMBEDDING_DEVICE": "cpu", "RERANKER_ENABLED": "false",
            "CHROMA_PERSIST_DIR": str(self.root / "chroma"), "DEBUG_DUMP_CONTEXT": "false",
            "CHROMA_HTTP_HOST": "127.0.0.1", "CHROMA_HTTP_PORT": str(self.ports["chroma"]), "CHROMA_HTTP_SSL": "false",
            "ANONYMIZED_TELEMETRY": "False",
            "CHAT_STREAM_REQUIRE_AUTH": "true", "CORS_ALLOW_ORIGINS": self.laravel_url,
            "SANCTUM_STATEFUL_DOMAINS": f"127.0.0.1:{self.ports['laravel']}",
            "SESSION_DRIVER": "file", "SESSION_DOMAIN": "null", "SESSION_SECURE_COOKIE": "false",
            "SESSION_COOKIE": "integration_session", "CACHE_STORE": "array", "QUEUE_CONNECTION": "sync",
            "BROADCAST_CONNECTION": "null", "MAIL_MAILER": "array", "BCRYPT_ROUNDS": "4",
            "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false",
            "LOG_CHANNEL": "single", "LOG_LEVEL": "info",
        })
        for name in ("CONFIG", "ROUTES", "SERVICES", "PACKAGES", "EVENTS"):
            self.env[f"APP_{name}_CACHE"] = str(cache / f"{name.lower()}.php")
        init = subprocess.run([
            "mysqld", "--no-defaults", "--initialize-insecure", f"--datadir={self.root / 'mysql'}",
            f"--log-error={self.root / 'mysql-initialize.log'}", "--innodb-buffer-pool-size=32M",
        ], env=self.env, capture_output=True, timeout=90)
        if init.returncode:
            raise RuntimeError("isolated MySQL initialization failed; inspect mysql-initialize.log")
        self.spawn("mysql", [
            "mysqld", "--no-defaults", f"--datadir={self.root / 'mysql'}", f"--socket={self.root / 'mysql.sock'}",
            f"--pid-file={self.root / 'mysql.pid'}", "--bind-address=127.0.0.1", f"--port={self.ports['mysql']}",
            "--mysqlx=0", "--performance-schema=OFF", "--innodb-buffer-pool-size=32M", "--innodb-redo-log-capacity=32M",
            f"--log-error={self.root / 'mysql-error.log'}",
        ])

        def connect_root():
            try:
                return pymysql.connect(unix_socket=str(self.root / "mysql.sock"), user="root", connect_timeout=1, autocommit=True)
            except pymysql.err.OperationalError:
                return None

        with self.wait_for(connect_root, 40, "isolated MySQL did not become ready") as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE `{self.db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                for host in ("localhost", "127.0.0.1"):
                    cursor.execute("CREATE USER %s@%s IDENTIFIED BY %s", ("integration", host, self.db_password))
                    cursor.execute(f"GRANT ALL ON `{self.db_name}`.* TO %s@%s", ("integration", host))
        self.spawn("redis", ["redis-server", "--bind", "127.0.0.1", "--port", str(self.ports["redis"]), "--save", "", "--appendonly", "no", "--dir", str(self.root / "redis")])
        prepared = subprocess.run(["php", "scripts/integration/prepare.php"], cwd=LARAVEL, env=self.env, capture_output=True, text=True, timeout=90)
        (self.root / "laravel-prepare.log").write_text(prepared.stdout + prepared.stderr)
        if prepared.returncode:
            raise RuntimeError("isolated Laravel migration/fixtures failed; inspect laravel-prepare.log")
        self.category_id = json.loads(prepared.stdout)["category_id"]
        self.correction = fixture_pdf(self.root / "fixture.pdf")
        self.check("disposable_mysql_redis_migrations_and_fixtures", {"database": self.db_name})

    def start_apps(self):
        self.spawn("chroma", [str(Path(sys.executable).parent / "chroma"), "run", "--path", str(self.root / "chroma"), "--host", "127.0.0.1", "--port", str(self.ports["chroma"])])

        def chroma_up():
            try:
                return httpx.get(f"http://127.0.0.1:{self.ports['chroma']}/api/v2/heartbeat", timeout=2, trust_env=False).status_code == 200
            except httpx.RequestError:
                return False

        self.wait_for(chroma_up, 40, "isolated Chroma server did not become ready")
        self.check("single_chroma_server_for_api_and_worker")
        self.spawn("fastapi", [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(self.ports["ai"])], AI)

        def healthy():
            try:
                response = httpx.get(self.ai_url + "/health", timeout=4, trust_env=False)
                return response.status_code == 200
            except httpx.RequestError:
                return False

        self.wait_for(healthy, 120, "isolated FastAPI health did not become healthy")
        self.spawn("celery", [sys.executable, "-m", "celery", "-A", "app.tasks.process_document.celery_app", "worker", "--pool=solo", "--concurrency=1", "--without-gossip", "--without-mingle", "--without-heartbeat", "--loglevel=info"], AI)
        self.spawn("laravel", ["php", "artisan", "serve", "--host=127.0.0.1", f"--port={self.ports['laravel']}", "--no-reload"], LARAVEL)

        def up():
            try:
                return httpx.get(self.laravel_url + "/up", timeout=2, trust_env=False).status_code == 200
            except httpx.RequestError:
                return False

        self.wait_for(up, 30, "isolated Laravel did not become ready")
        self.check("actual_fastapi_laravel_health")

    def pipeline(self):
        with httpx.Client(base_url=self.laravel_url, timeout=150, trust_env=False,
                          headers={"Accept": "application/json", "Origin": self.laravel_url, "Referer": self.laravel_url + "/"}) as client:
            def request(method, path, expected=200, **kwargs):
                csrf = client.cookies.get("XSRF-TOKEN")
                headers = {"X-XSRF-TOKEN": unquote(csrf)} if csrf else {}
                response = client.request(method, path, headers=headers, **kwargs)
                if response.status_code != expected:
                    raise AssertionError(f"{method} {path}: expected HTTP {expected}, received {response.status_code}")
                return response

            request("GET", "/api/auth/user", 401)
            request("GET", "/sanctum/csrf-cookie", 204)
            response = client.post("/api/auth/login", json={"email": "integration@example.test", "password": self.admin_password})
            assert response.status_code == 419, "missing CSRF token was accepted"
            request("POST", "/api/auth/login", 401, json={"email": "integration@example.test", "password": "wrong-password"})
            request("POST", "/api/auth/login", json={"email": "integration@example.test", "password": self.admin_password})
            assert request("GET", "/api/auth/user").json()["data"]["user"]["email"] == "integration@example.test"
            self.check("real_cookie_login_csrf_419_and_unauthenticated_401")
            assert httpx.get(self.ai_url + "/api/docs", trust_env=False).status_code == 401
            with (self.root / "fixture.pdf").open("rb") as fixture:
                uploaded = request("POST", "/api/documents", 201, data={"title": "Synthetic Archive Integration", "category_id": str(self.category_id)}, files={"pdf_file": ("synthetic.pdf", fixture, "application/pdf")}).json()
            document_id = uploaded["data"]["document"]["id"]
            self.report["document_id"] = document_id
            path = f"/api/documents/{document_id}"

            def status():
                return request("GET", path + "/extraction").json()["data"]

            def running_ocr():
                state = status()
                if state["status"] in ("gagal", "menunggu_koreksi", "selesai"):
                    raise AssertionError(f"could not pause during OCR: {state['status']}")
                return state["status"] == "berjalan"

            self.wait_for(running_ocr, 90, "worker did not start real OCR")
            request("POST", path + "/extraction/pause", 202, json={})
            paused = self.wait_for(lambda: (state if (state := status())["status"] == "jeda" else None), 360, "worker did not pause after OCR")
            assert paused["halaman_selesai"] == 1 and paused["halaman_total"] == 2, paused
            pages = request("GET", path + "/pages").json()["data"]["halaman"]
            assert len(pages) == 1 and "arsip" in pages[0]["text"].lower()
            self.report["ocr_text"] = pages[0]["text"]
            self.check("upload_real_vision_ocr_and_pause_after_saved_page", {"pages_saved": 1, "total_pages": 2})

            request("POST", path + "/extraction", 202, json={})
            reviewed = self.wait_for(lambda: (state if (state := status())["status"] == "menunggu_koreksi" else None), 90, "resume did not reach human review")
            assert reviewed["halaman_selesai"] == 2 and reviewed["halaman_total"] == 2
            pages = request("GET", path + "/pages").json()["data"]["halaman"]
            assert [page["page_number"] for page in pages] == [1, 2]
            assert pages[0]["text"] == self.report["ocr_text"], "resume rewrote saved page"
            vector_snapshot = request("GET", path + "/chunks").json()
            assert vector_snapshot["total_chunks"] == 0 and vector_snapshot["chunks"] == [], "review gate already wrote vectors"
            self.check("resume_skips_saved_page_and_stops_for_human_review")
            request("PUT", path + "/pages/1", json={"text": self.correction})
            pages = request("GET", path + "/pages").json()["data"]["halaman"]
            self.report["corrected_pages"] = pages
            assert pages[0]["text"] == self.correction, "correction whitespace/content changed across Laravel/Python/MySQL"
            dims = request("GET", path + "/pages/dimensions").json()["data"]
            assert dims["halaman_total"] == 2, "page dimensions count changed"
            preview = request("POST", path + "/chunks/preview", json={"parent_chunk_overlap": 0, "child_chunk_overlap": 0}).json()["data"]
            assert preview["siap"] and "ARSIP-9631" in json.dumps(preview["induk"]), "preview omitted the manual correction"
            assert preview["parent_chunk_overlap"] == 0 and preview["child_chunk_overlap"] == 0, "preview lost explicit zero overlap"
            self.check("manual_correction_dimensions_and_actual_chunk_preview")
            request("POST", path + "/embed", 202, json={})
            completed = self.wait_for(lambda: (state if (state := status())["status"] == "selesai" else None), 180, "embedding did not complete")
            assert completed["halaman_total"] == 2 and completed["halaman_selesai"] == 2
            vector_snapshot = request("GET", path + "/chunks").json()
            chunks = vector_snapshot["chunks"]
            assert chunks and "ARSIP-9631" in json.dumps(chunks)
            detail = request("GET", path).json()["data"]["document"]
            assert detail["status"] == "completed" and detail["total_chunks"] > 0
            self.check("real_celery_embedding_chroma_and_laravel_status", {"vector_count": detail["total_chunks"]})

            self.chat(document_id)
            request("POST", "/api/auth/logout", json={})
            request("GET", "/api/auth/user", 401)
            self.check("real_cookie_logout")

    def chat(self, document_id):
        query = "Berapa lama waktu penyelesaian pengarsipan berkas ARSIP-9631?"
        # Warm the already installed small chat model outside the gateway's 60s timeout.
        with httpx.Client(timeout=180, trust_env=False) as client:
            response = client.post(self.ollama_url + "/api/generate", json={"model": self.args.chat_model, "prompt": "", "stream": False, "options": {"num_ctx": 4096}})
            response.raise_for_status()
            headers = {"Authorization": "Bearer " + self.api_key, "Accept": "application/json"}
            response = client.post(self.laravel_url + "/api/v1/chat", headers=headers, json={"query": query, "session_id": "integration-json", "document_ids": [document_id]})
            response.raise_for_status()
            body = response.json()
            self.report["json_chat"] = body
            assert not body["is_fallback"] and "37" in body["answer"], "JSON answer did not use the manual correction"
            assert any(source.get("document_id") == document_id for source in body["sources"]), "missing document citation"
            self.check("real_gateway_json_retrieval_answer_and_document_citation")
            events = []
            with client.stream("POST", self.laravel_url + "/api/v1/chat/stream", headers=headers, json={"query": query, "session_id": "integration-sse", "document_ids": [document_id]}) as stream:
                stream.raise_for_status()
                assert stream.headers["content-type"].startswith("text/event-stream")
                for line in stream.iter_lines():
                    if line.startswith("data:"):
                        value = line[5:].strip()
                        if value:
                            events.append(json.loads(value))
            self.report["sse_events"] = events
            assert not any(event.get("type") == "error" for event in events)
            assert any(event.get("type") == "done" for event in events)
            text = "".join(event.get("content", "") for event in events if event.get("type") == "chunk")
            assert "37" in text, "SSE answer did not use the manual correction"
            self.check("real_gateway_sse_chunks_and_done")

            narrative_events = []
            with client.stream("POST", self.ai_url + "/api/chat/stream", headers={"Authorization": "Bearer " + self.token}, json={
                "query": "Apa tugas petugas arsip sesudah menerima formulir pada layanan ARSIP-9631?",
                "session_id": "integration-narrative", "document_ids": [document_id], "include_debug": True,
            }) as stream:
                stream.raise_for_status()
                for line in stream.iter_lines():
                    if line.startswith("data:") and (value := line[5:].strip()):
                        narrative_events.append(json.loads(value))
            self.report["narrative_events"] = narrative_events
            assert not any(event.get("type") == "error" for event in narrative_events), "narrative stream failed"
            assert any(event.get("type") == "done" for event in narrative_events), "narrative stream did not finish"
            assert any(event.get("type") == "trace" and event.get("stage") == "generation" for event in narrative_events), "narrative answer did not reach LLM generation"
            narrative = "".join(event.get("content", "") for event in narrative_events if event.get("type") == "chunk")
            assert "registrasi" in narrative.lower() or "kelengkapan" in narrative.lower(), "narrative answer did not use document facts"
            self.check("actual_narrative_llm_generation_with_retrieved_facts")

    def close(self):
        # Stop only process groups this runner created; never invoke shared launchers/purge.
        for name, process in reversed(self.processes):
            if process.poll() is not None:
                continue
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                continue
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        for log in self.logs:
            log.close()
        self.report["owned_processes_stopped"] = all(process.poll() is not None for _, process in self.processes)
        self.report["elapsed_seconds"] = round(time.monotonic() - self.started, 2)
        self.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--vision-model", default="qwen2.5vl:7b-q4_K_M")
    parser.add_argument("--chat-model", default="qwen2.5:3b")
    parser.add_argument("--cancellation", action="store_true", help="Also exercise queued/active cancellation and immediate resume on the disposable services")
    args = parser.parse_args()
    run = Run(args)
    def interrupted(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    print(f"Artifacts: {run.root}", flush=True)
    code = 1
    try:
        run.prepare()
        run.start_apps()
        run.pipeline()
        if args.cancellation:
            from cancellation_scenarios import run_cancellation_cases
            run_cancellation_cases(run)
        run.report["status"] = "passed"
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        message = str(error)
        for secret in run.secrets:
            message = message.replace(secret, "[redacted]")
        run.report["status"] = "failed"
        run.report["error"] = {"type": type(error).__name__, "message": message}
        frames = traceback.extract_tb(error.__traceback__)
        if frames:
            last = frames[-1]
            run.report["error"]["location"] = {"file": Path(last.filename).name, "line": last.lineno, "function": last.name}
        print(f"FAIL {type(error).__name__}: {message}", flush=True)
    finally:
        run.close()
    print(f"Report: {run.root / 'report.json'}", flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
