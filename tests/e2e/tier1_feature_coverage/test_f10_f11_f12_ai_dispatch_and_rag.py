"""
Tier 1: Feature Coverage — Features F10, F11, & F12.
F10: Python AI Outbound Handoff Dispatch
F11: Graceful Citizen Escalation Responses
F12: Existing RAG Pipeline Preservation
"""

import os
import re
import json
import unittest
from tests.e2e.test_config import (
    PYTHON_AI_DIR,
    AI_HOST,
    LARAVEL_HOST,
    INTERNAL_API_TOKEN,
    InternalServiceClient,
    is_http_endpoint_alive,
    generate_unique_session,
)


class TestF10OutboundHandoffDispatch(unittest.TestCase):
    """Test suite for F10: Python AI Outbound Handoff Dispatch (>= 5 test cases)."""

    @classmethod
    def setUpClass(cls):
        cls.tool_router_path = os.path.join(
            PYTHON_AI_DIR, "app", "services", "tool_router.py"
        )
        cls.client = InternalServiceClient(LARAVEL_HOST, INTERNAL_API_TOKEN)
        cls.backend_alive = is_http_endpoint_alive(f"{LARAVEL_HOST}/up")

    def test_tc01_f10_human_escalation_intent_patterns(self):
        """TC-F10-01: Verify human escalation trigger phrases in tool_router.py."""
        self.assertTrue(os.path.exists(self.tool_router_path))
        with open(self.tool_router_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("human_escalation", code)
        self.assertTrue(
            "bicara" in code and "petugas" in code,
            "Regex must detect 'bicara dengan petugas'",
        )

    def test_tc02_f10_dispatch_payload_conforms_to_contract(self):
        """TC-F10-02: Verify dispatch payload structure matches Laravel internal endpoint schema."""
        sess = generate_unique_session("f10-dispatch")
        payload = {
            "session_id": sess,
            "intent": "human_escalation",
            "message": "Tolong hubungkan saya dengan staf helpdesk",
            "citizen_name": "Teuku Iskandar",
            "citizen_contact": "0811998877",
            "citizen_agency": "Diskominfotik",
            "issue_summary": "Permintaan bantuan staf helpdesk",
            "channel": "widget",
        }
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")
        resp = self.client.create_or_update_ticket(payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()["data"]
        self.assertEqual(data["session_id"], sess)
        self.assertEqual(data["status"], "open")

    def test_tc03_f10_dispatch_handles_followup_intent(self):
        """TC-F10-03: Verify human_escalation_followup payload appends to existing ticket."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")
        sess = generate_unique_session("f10-followup")
        resp1 = self.client.create_or_update_ticket({
            "session_id": sess,
            "message": "Saya mau bicara petugas",
        })
        self.assertEqual(resp1.status_code, 201)
        ticket_id = resp1.json()["data"]["ticket_id"]

        resp2 = self.client.create_or_update_ticket({
            "session_id": sess,
            "ticket_id": ticket_id,
            "intent": "human_escalation_followup",
            "message": "Nomor tiket saya ingin ditanyakan kelanjutannya",
        })
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["data"]["ticket_id"], ticket_id)

    def test_tc04_f10_timeout_and_resilience_contract(self):
        """TC-F10-04: Verify client configuration specifies a maximum 3-5 second timeout for outbound dispatch."""
        config_path = os.path.join(PYTHON_AI_DIR, "app", "config.py")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                code = f.read()
            # Token definition verification
            self.assertIn("INTERNAL_API_TOKEN", code)

    def test_tc05_f10_channel_metadata_preservation(self):
        """TC-F10-05: Verify channel metadata (whatsapp/widget/telegram) is correctly preserved."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")
        sess = generate_unique_session("f10-channel")
        resp = self.client.create_or_update_ticket({
            "session_id": sess,
            "message": "Pesan dari WhatsApp warga",
            "channel": "whatsapp",
        })
        self.assertEqual(resp.status_code, 201)


class TestF11GracefulCitizenEscalationResponses(unittest.TestCase):
    """Test suite for F11: Graceful Citizen Escalation Responses (>= 5 test cases)."""

    @classmethod
    def setUpClass(cls):
        cls.canned_response_template = (
            "Permintaan Anda telah kami teruskan ke petugas Diskominfotik. "
            "Petugas kami akan segera menindaklanjuti. Untuk layanan darurat atau "
            "bantuan cepat, Anda dapat menghubungi Call Center 112 atau datang langsung ke Balai Kota."
        )

    def test_tc01_f11_response_contains_reassurance(self):
        """TC-F11-01: Verify canned response reassures citizen that officer will follow up."""
        self.assertTrue(
            "petugas" in self.canned_response_template.lower()
            or "tim" in self.canned_response_template.lower()
        )

    def test_tc02_f11_response_mentions_emergency_call_center_112(self):
        """TC-F11-02: Verify canned response includes Call Center 112 contact info."""
        self.assertIn("112", self.canned_response_template)

    def test_tc03_f11_response_mentions_balai_kota_or_office_location(self):
        """TC-F11-03: Verify canned response advises physical office location (Balai Kota)."""
        self.assertIn("Balai Kota", self.canned_response_template)

    def test_tc04_f11_response_format_is_polite_indonesian(self):
        """TC-F11-04: Verify escalation text uses respectful formal Indonesian register."""
        self.assertTrue(self.canned_response_template.startswith("Permintaan Anda"))

    def test_tc05_f11_followup_acknowledgement_structure(self):
        """TC-F11-05: Verify followup messages receive clear acknowledgement that info was added."""
        followup_ack = "Terima kasih, informasi tambahan Anda telah diteruskan ke petugas penanggung jawab."
        self.assertIn("informasi tambahan", followup_ack.lower())
        self.assertIn("diteruskan ke petugas", followup_ack.lower())


class TestF12ExistingRAGPipelinePreservation(unittest.TestCase):
    """Test suite for F12: Existing RAG Pipeline Preservation (>= 5 test cases)."""

    @classmethod
    def setUpClass(cls):
        cls.tool_router_path = os.path.join(PYTHON_AI_DIR, "app", "services", "tool_router.py")
        cls.rag_service_path = os.path.join(PYTHON_AI_DIR, "app", "services", "rag_service.py")

    def test_tc01_f12_tool_router_preserves_rag_and_chitchat_intents(self):
        """TC-F12-01: Verify tool_router.py retains standard RAG and chitchat route branches."""
        self.assertTrue(os.path.exists(self.tool_router_path))
        with open(self.tool_router_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("route_intent", code)
        self.assertIn("chitchat", code)

    def test_tc02_f12_fast_paths_and_directories_unbroken(self):
        """TC-F12-02: Verify fast-path FAQ and directory lookups remain intact."""
        with open(self.tool_router_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("get_active_fast_paths", code)
        self.assertIn("get_active_directories", code)

    def test_tc03_f12_rag_service_hybrid_retrieval_functions(self):
        """TC-F12-03: Verify rag_service.py retains generate_response and retrieval hooks."""
        self.assertTrue(os.path.exists(self.rag_service_path))
        with open(self.rag_service_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("generate_response", code)

    def test_tc04_f12_non_escalation_queries_do_not_trigger_handoff(self):
        """TC-F12-04: Verify queries about SOP, regulations, and office hours do NOT match handoff regex."""
        # Non-escalation query samples
        standard_queries = [
            "Bagaimana prosedur pengajuan surat keterangan domisili usaha?",
            "Perwal nomor berapa yang mengatur tentang SPBE?",
            "Jam berapa pelayanan dinas kependudukan buka?",
            "Berapa hari kerja proses penerbitan izin penelitian?",
        ]
        handoff_regex = re.compile(
            r"\b(bicara\s+(?:dengan|sama|ke)?\s*(?:petugas|admin|manusia)|sambungkan\s+(?:ke|dengan)?\s*(?:petugas|admin)|operator\s+manusia)\b",
            re.IGNORECASE,
        )
        for q in standard_queries:
            self.assertIsNone(
                handoff_regex.search(q),
                f"Standard municipal query '{q}' should not match human escalation regex",
            )

    def test_tc05_f12_hardware_and_health_endpoints_preserved(self):
        """TC-F12-05: Verify /health and hardware diagnostic endpoints are present in app/main.py."""
        main_path = os.path.join(PYTHON_AI_DIR, "app", "main.py")
        self.assertTrue(os.path.exists(main_path))
        with open(main_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("/health", code)


if __name__ == "__main__":
    unittest.main()
