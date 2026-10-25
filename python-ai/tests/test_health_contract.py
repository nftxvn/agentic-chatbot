"""Kontrak HTTP/cache diagnostik tanpa menghubungi layanan atau hardware nyata."""

import importlib
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, mock_open, patch

from fastapi import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app import main


def owner(function):
    return importlib.import_module(function.__module__)


class HealthHttpContractTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.module = owner(main.health_check)
        self.stack.enter_context(patch.object(self.module, "_health_cache", None))
        self.checks = self.stack.enter_context(patch.object(self.module, "_run_health_checks", return_value={
            name: {"ok": True, "detail": "mock"} for name in ("chromadb", "mysql", "redis", "ollama")
        }))
        # No context manager: startup/lifespan is not run for these HTTP cases.
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def test_public_health_aliases_share_payload_and_cache_without_token(self):
        first = self.client.get("/health")
        second = self.client.get("/api/health")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(first.json()["status"], "healthy")
        self.assertEqual(first.json()["service"], "ai-service")
        self.assertEqual(set(first.json()["checks"]), {"chromadb", "mysql", "redis", "ollama"})
        self.checks.assert_called_once()

    def test_failed_dependency_returns_503_on_both_aliases(self):
        self.checks.return_value = {"mysql": {"ok": False, "detail": "RuntimeError"}}
        for path in ("/health", "/api/health"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["status"], "degraded")

    def test_cache_expires_at_five_seconds_including_degraded_payload(self):
        self.checks.side_effect = [{"redis": {"ok": False}}, {"redis": {"ok": True}}]
        with patch.object(self.module, "time", SimpleNamespace(monotonic=Mock(side_effect=[100, 104.99, 105]))):
            self.assertEqual(main.health_check(Response())["status"], "degraded")
            self.assertEqual(main.health_check(Response())["status"], "degraded")
            self.assertEqual(main.health_check(Response())["status"], "healthy")
        self.assertEqual(self.checks.call_count, 2)

    def test_cors_registration_keeps_current_origin_method_and_header_policy(self):
        middleware = next(item for item in main.app.user_middleware if item.cls is CORSMiddleware)
        self.assertEqual(middleware.kwargs["allow_origins"], main.settings.CORS_ALLOW_ORIGINS)
        self.assertEqual(middleware.kwargs["allow_methods"], ["GET", "POST"])
        self.assertEqual(middleware.kwargs["allow_headers"], ["Authorization", "Content-Type"])
        self.assertTrue(middleware.kwargs["allow_credentials"])


class DependencyProbeContractTest(unittest.TestCase):
    def test_empty_chroma_collection_is_still_healthy(self):
        collection = Mock()
        collection.count.return_value = 0
        with patch("app.services.embedding_service.get_chroma_collection", return_value=collection):
            self.assertEqual(main._check_chromadb(), {"ok": True, "detail": "0 vektor"})

    def test_probe_exception_reports_class_only_and_does_not_stop_other_checks(self):
        module = owner(main._run_health_checks)
        good = Mock(return_value={"ok": True, "detail": "ready"})
        with patch.object(module, "_HEALTH_CHECKS", {"mysql": Mock(side_effect=RuntimeError("synthetic-private-detail")), "redis": good}):
            with self.assertLogs(module.logger, level="WARNING"):
                result = main._run_health_checks()
        self.assertEqual(result["mysql"], {"ok": False, "detail": "RuntimeError"})
        self.assertNotIn("synthetic-private-detail", str(result))
        good.assert_called_once()

    def test_ollama_accepts_latest_tag_and_rejects_missing_configured_model(self):
        module = owner(main._check_ollama)
        response = Mock()
        with patch.object(module.settings, "LLM_MODEL_NAME", "mock-model"), patch("requests.get", return_value=response) as get:
            response.json.return_value = {"models": [{"name": "mock-model:latest"}]}
            self.assertTrue(main._check_ollama()["ok"])
            response.json.return_value = {"models": []}
            self.assertFalse(main._check_ollama()["ok"])
        self.assertEqual(get.call_args.kwargs["timeout"], 3)

    def test_redis_client_is_closed_when_ping_fails(self):
        client = Mock()
        client.ping.side_effect = RuntimeError("mock redis failure")
        with patch("redis.from_url", return_value=client) as connect:
            with self.assertRaises(RuntimeError):
                main._check_redis()
        client.close.assert_called_once()
        self.assertEqual(connect.call_args.kwargs["socket_connect_timeout"], 3)
        self.assertEqual(connect.call_args.kwargs["socket_timeout"], 3)

    def test_mysql_probe_executes_select_one(self):
        from unittest.mock import MagicMock

        engine = MagicMock()
        with patch("app.database.get_engine", return_value=engine):
            self.assertTrue(main._check_mysql()["ok"])
        statement = engine.connect.return_value.__enter__.return_value.execute.call_args.args[0]
        self.assertEqual(str(statement), "SELECT 1")


class HardwareHttpContractTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.module = owner(main.diagnostik_mesin)
        self.stack.enter_context(patch.object(self.module, "_mesin_cache", None))
        self.stack.enter_context(patch.object(self.module.settings, "INTERNAL_API_TOKEN", "expected-token"))
        self.gpu = self.stack.enter_context(patch.object(self.module, "_baca_nvidia_smi", return_value=None))
        self.stack.enter_context(patch.object(self.module, "_baca_system_ram", return_value={"ram_total_mib": 16384, "ram_bebas_mib": 8192}))
        self.stack.enter_context(patch.object(self.module, "_baca_ollama_ps", return_value={"termuat": False}))
        self.stack.enter_context(patch.object(self.module, "_deteksi_os_platform", return_value="Test OS"))
        self.setting = self.stack.enter_context(patch("app.database.get_app_setting", side_effect=lambda key: {"llm_model_name": "db-model", "rag_num_ctx": "8192"}.get(key)))
        self.stack.enter_context(patch("app.services.pdf_processor.resolve_vision_model", return_value="mock-vision"))
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def test_authentication_runs_before_hardware_probes(self):
        self.assertEqual(self.client.get("/api/health/hardware").status_code, 401)
        self.module._mesin_cache = (self.module.time.monotonic(), {"synthetic_private_data": True})
        self.assertEqual(self.client.get("/api/health/hardware", headers={"Authorization": "Bearer wrong"}).status_code, 401)
        self.gpu.assert_not_called()
        self.setting.assert_not_called()

    def test_authorized_response_keeps_schema_and_database_config(self):
        response = self.client.get("/api/health/hardware", headers={"Authorization": "Bearer expected-token"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(set(data), {"konfigurasi", "sistem", "gpu", "ram", "ollama", "rekomendasi", "model_fit"})
        self.assertIsNone(data["gpu"])
        self.assertEqual(data["konfigurasi"]["llm_model"], "db-model")
        self.assertEqual(data["konfigurasi"]["num_ctx"], 8192)
        self.assertEqual(data["konfigurasi"]["vision_model"], "mock-vision")

    def test_hardware_cache_uses_three_seconds_and_nocache_bypasses_it(self):
        with patch.object(self.module, "time", SimpleNamespace(monotonic=Mock(side_effect=[100, 102.99, 103, 103.1]))):
            main.diagnostik_mesin(_token="unused")
            main.diagnostik_mesin(_token="unused")
            main.diagnostik_mesin(_token="unused")
            main.diagnostik_mesin(nocache=True, _token="unused")
        self.assertEqual(self.gpu.call_count, 3)

    def test_cached_model_override_only_recomputes_model_fit(self):
        main.diagnostik_mesin(nocache=True, model="model-a", _token="unused")
        second = main.diagnostik_mesin(model="model-b", _token="unused")
        third = main.diagnostik_mesin(_token="unused")
        self.assertEqual(second["model_fit"]["model_name"], "model-b")
        self.assertEqual(second["konfigurasi"]["llm_model"], "model-a")
        self.assertEqual(second["rekomendasi"]["model_name"], "model-a")
        self.assertEqual(third["model_fit"]["model_name"], "model-a")
        self.gpu.assert_called_once()

    def test_database_failure_uses_settings_defaults(self):
        self.setting.side_effect = RuntimeError("unavailable")
        result = main.diagnostik_mesin(nocache=True, _token="unused")
        self.assertEqual(result["konfigurasi"]["llm_model"], self.module.settings.LLM_MODEL_NAME)
        self.assertEqual(result["konfigurasi"]["num_ctx"], self.module.settings.LLM_NUM_CTX)


class HardwareCalculationContractTest(unittest.TestCase):
    def test_recommendations_keep_model_and_capacity_boundaries(self):
        for gpu, model, expected in [(None, "7b", 4096), ({"nama": "GPU", "vram_total_mib": 5400}, "7b", 6144),
                                     ({"nama": "GPU", "vram_total_mib": 5400}, "3b", 16384),
                                     ({"nama": "GPU", "vram_total_mib": 22000}, "7b", 32768)]:
            with self.subTest(gpu=gpu, model=model):
                result = main._hitung_rekomendasi_hardware(gpu, {"ram_total_mib": 8192}, model)
                self.assertEqual(result["recommended_num_ctx"], expected)
                self.assertEqual(result["preset_options"], [2048, 4096, 6144, 8192, 12288, 16384])

    def test_model_fit_distinguishes_free_total_and_insufficient_vram(self):
        for total, free, expected in [(6000, 5600, "optimal"), (6000, 100, "shared_warning"), (5000, 100, "exceeds_gpu")]:
            with self.subTest(total=total, free=free):
                result = main._hitung_kecocokan_model({"vram_total_mib": total, "vram_bebas_mib": free}, None, "7b", 6144)
                self.assertEqual(result["total_required_mib"], 5520)
                self.assertEqual(result["fit_status"], expected)
        self.assertEqual(main._hitung_kecocokan_model(None, None, "7b")["fit_status"], "cpu_only")

    def test_nvidia_probe_reads_first_gpu_without_running_command(self):
        result = SimpleNamespace(returncode=0, stdout="GPU Test, 6000, 1000, 5000, 20\nSecond, 100, 90, 10, 50")
        with patch("subprocess.run", return_value=result) as run:
            data = main._baca_nvidia_smi()
        self.assertEqual(data["nama"], "GPU Test")
        self.assertEqual(data["vram_bebas_mib"], 5000)
        self.assertEqual(run.call_args.kwargs["timeout"], 3)

    def test_missing_nvidia_and_bad_output_return_none(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            self.assertIsNone(main._baca_nvidia_smi())
        with patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="bad")):
            self.assertIsNone(main._baca_nvidia_smi())

    def test_ram_probe_converts_linux_kilobytes_to_mib(self):
        module = owner(main._baca_system_ram)
        with patch.object(module.os.path, "exists", return_value=True), \
                patch("builtins.open", mock_open(read_data="MemTotal: 8388608 kB\nMemAvailable: 2097152 kB\n")):
            self.assertEqual(main._baca_system_ram(), {"ram_total_mib": 8192, "ram_dipakai_mib": 6144, "ram_bebas_mib": 2048})

    def test_ollama_loaded_model_payload_keeps_units_and_context_fallback(self):
        response = Mock()
        response.json.return_value = {"models": [{"name": "mock", "size": 4194304, "size_vram": 2097152, "details": {"context_length": 8192}}]}
        with patch("requests.get", return_value=response):
            result = main._baca_ollama_ps()
        self.assertEqual(result["ukuran_mib"], 4)
        self.assertEqual(result["di_gpu_mib"], 2)
        self.assertEqual(result["persen_di_gpu"], 50)
        self.assertEqual(result["konteks"], 8192)


if __name__ == "__main__":
    unittest.main()
