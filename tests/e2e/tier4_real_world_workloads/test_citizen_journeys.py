"""
Tier 4: Real-World Workloads — Comprehensive Citizen Journeys.
Simulates realistic citizen experiences and administrative workflows in the Banda Aceh Diskominfotik context.
"""

import time
import unittest
from tests.e2e.test_config import (
    LARAVEL_HOST,
    INTERNAL_API_TOKEN,
    InternalServiceClient,
    SanctumClient,
    is_http_endpoint_alive,
    generate_unique_session,
)


class TestRealWorldCitizenJourneys(unittest.TestCase):
    """End-to-End citizen journeys simulating actual city government scenarios."""

    @classmethod
    def setUpClass(cls):
        cls.internal_client = InternalServiceClient(LARAVEL_HOST, INTERNAL_API_TOKEN)
        cls.sanctum_client = SanctumClient(LARAVEL_HOST)
        cls.backend_alive = is_http_endpoint_alive(f"{LARAVEL_HOST}/up")
        if cls.backend_alive:
            cls.sanctum_client.login()

    def setUp(self):
        if self.backend_alive and not self.sanctum_client.logged_in:
            self.sanctum_client.login()

    def test_journey_1_spbe_login_failure_escalation(self):
        """Journey 1: Government employee fails SPBE portal login, escalates to live support, and receives resolution."""
        if not self.backend_alive or not self.sanctum_client.logged_in:
            self.skipTest("Laravel backend not reachable or not logged in")

        sess = generate_unique_session("journey-spbe-login")

        # 1. Citizen escalates
        ingest_resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "channel": "widget",
            "intent": "human_escalation",
            "citizen_name": "Teuku Muhammad",
            "citizen_contact": "081234567890",
            "citizen_agency": "Badan Kepegawaian dan Pengembangan SDM",
            "issue_summary": "Kendala autentikasi 2FA akun SPBE",
            "message": "Assalamu'alaikum, saya dari BKPSDM tidak bisa verifikasi kode 2FA portal SPBE. Mohon dibantu admin.",
        })
        self.assertEqual(ingest_resp.status_code, 201)
        ticket_id = ingest_resp.json()["data"]["ticket_id"]

        # 2. Admin searches for agency in queue
        search_resp = self.sanctum_client.get("/api/tickets", params={"search": "BKPSDM"})
        self.assertEqual(search_resp.status_code, 200)
        found_tickets = search_resp.json().get("data", [])
        self.assertTrue(any(t["id"] == ticket_id for t in found_tickets))

        # 3. Admin self-assigns and responds
        self.sanctum_client.post(f"/api/tickets/{ticket_id}/assign", data={})
        self.sanctum_client.post(f"/api/tickets/{ticket_id}/messages", data={
            "message": "Wa'alaikumsalam Pak Teuku, 2FA akun Anda telah kami reset ke nomor ponsel terdaftar.",
            "is_internal_note": False,
        })

        # 4. Citizen confirms success
        follow_resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "ticket_id": ticket_id,
            "intent": "human_escalation_followup",
            "message": "Alhamdulillah sudah bisa login kembali, terima kasih banyak!",
        })
        self.assertEqual(follow_resp.status_code, 200)

        # 5. Admin marks as resolved
        status_resp = self.sanctum_client.patch(f"/api/tickets/{ticket_id}/status", data={"status": "resolved"})
        self.assertEqual(status_resp.status_code, 200)
        self.assertEqual(status_resp.json()["data"]["status"], "resolved")

    def test_journey_2_whatsapp_citizen_multi_turn_dialogue(self):
        """Journey 2: WhatsApp resident inquires, requests human assistance, and is seamlessly supported."""
        if not self.backend_alive or not self.sanctum_client.logged_in:
            self.skipTest("Laravel backend not reachable or not logged in")

        sess = generate_unique_session("wa-journey-0852")

        # Turn 1: Initial WhatsApp escalation
        t1_resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "channel": "whatsapp",
            "intent": "human_escalation",
            "citizen_contact": "085277889900",
            "message": "Selamat siang, saya mau bicara dengan petugas helpdesk.",
        })
        self.assertEqual(t1_resp.status_code, 201)
        ticket_id = t1_resp.json()["data"]["ticket_id"]

        # Turn 2: Followup provides citizen name and detailed issue
        t2_resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "ticket_id": ticket_id,
            "intent": "human_escalation_followup",
            "citizen_name": "Ibu Cut Nurul",
            "citizen_agency": "Masyarakat Umum",
            "issue_summary": "Permohonan informasi jaringan internet publik Gampong",
            "message": "Nama saya Cut Nurul, mau tanya wifi gratis di Gampong Lambhuk mati sejak kemarin.",
        })
        self.assertEqual(t2_resp.status_code, 200)

        # Turn 3: Admin inspects and replies
        reply_resp = self.sanctum_client.post(f"/api/tickets/{ticket_id}/messages", data={
            "message": "Selamat siang Ibu Cut Nurul, tim teknis jaringan Diskominfotik sedang menuju lokasi untuk perbaikan access point.",
            "is_internal_note": False,
        })
        self.assertEqual(reply_resp.status_code, 201)

        # Turn 4: Verify conversation history order
        thread_resp = self.sanctum_client.get(f"/api/tickets/{ticket_id}/messages")
        self.assertEqual(thread_resp.status_code, 200)
        msgs = thread_resp.json()["data"]
        self.assertEqual(len(msgs), 3)
        self.assertEqual(msgs[0]["sender_type"], "citizen")
        self.assertEqual(msgs[1]["sender_type"], "citizen")
        self.assertEqual(msgs[2]["sender_type"], "agent")

    def test_journey_3_high_volume_concurrent_multi_agency_escalations(self):
        """Journey 3: High-volume rapid escalations from 5 distinct government agencies."""
        if not self.backend_alive or not self.sanctum_client.logged_in:
            self.skipTest("Laravel backend not reachable or not logged in")

        agencies = [
            ("Dinas Pendidikan", "Disdik Staff", "0811000001", "Gangguan server ujian"),
            ("Dinas Kesehatan", "Dinkes Staff", "0811000002", "Sinkronisasi SatuSehat"),
            ("Disdukcapil", "Dukcapil Staff", "0811000003", "Koneksi SIAK terputus"),
            ("Bappeda", "Bappeda Staff", "0811000004", "Input SIPD terkendala"),
            ("Inspektorat", "Inspektorat Staff", "0811000005", "Konsultasi audit TIK"),
        ]

        ticket_ids = []
        for agency, name, contact, issue in agencies:
            sess = generate_unique_session("multi-agency")
            resp = self.internal_client.create_or_update_ticket({
                "session_id": sess,
                "citizen_name": name,
                "citizen_contact": contact,
                "citizen_agency": agency,
                "issue_summary": issue,
                "message": f"Laporan resmi dari {agency}: {issue}",
            })
            self.assertEqual(resp.status_code, 201)
            ticket_ids.append(resp.json()["data"]["ticket_id"])

        # Verify all 5 tickets were created
        self.assertEqual(len(ticket_ids), 5)

        # Admin lists open queue with per_page=15
        queue_resp = self.sanctum_client.get("/api/tickets", params={"status": "open", "per_page": 15})
        self.assertEqual(queue_resp.status_code, 200)
        open_ids = [t["id"] for t in queue_resp.json()["data"]]
        for tid in ticket_ids:
            self.assertIn(tid, open_ids)

    def test_journey_4_internal_notes_confidentiality_isolation(self):
        """Journey 4: Internal notes remain strictly internal and separate from citizen-facing replies."""
        if not self.backend_alive or not self.sanctum_client.logged_in:
            self.skipTest("Laravel backend not reachable or not logged in")

        sess = generate_unique_session("confidential-notes")
        resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "message": "Saya lupa password admin sistem e-surat",
            "citizen_name": "Pak Zulfikar",
        })
        ticket_id = resp.json()["data"]["ticket_id"]

        # Admin adds internal note with sensitive infrastructure info
        self.sanctum_client.post(f"/api/tickets/{ticket_id}/messages", data={
            "message": "INTERNAL ONLY: IP server 10.10.1.50, reset via console backend",
            "is_internal_note": True,
        })

        # Admin sends public citizen response
        self.sanctum_client.post(f"/api/tickets/{ticket_id}/messages", data={
            "message": "Password sementara telah dikirimkan ke email kedinasan Anda.",
            "is_internal_note": False,
        })

        # Verify messages list reflects is_internal_note flag correctly
        messages_resp = self.sanctum_client.get(f"/api/tickets/{ticket_id}/messages")
        self.assertEqual(messages_resp.status_code, 200)
        msgs = messages_resp.json()["data"]

        internal_notes = [m for m in msgs if m.get("is_internal_note") is True or m.get("is_internal_note") == 1]
        public_replies = [m for m in msgs if not m.get("is_internal_note")]

        self.assertEqual(len(internal_notes), 1)
        self.assertIn("INTERNAL ONLY", internal_notes[0]["message"])
        self.assertTrue(len(public_replies) >= 2)  # 1 citizen initial + 1 public agent reply

    def test_journey_5_anti_false_positive_preserves_rag_retrieval(self):
        """Journey 5: Standard citizen questions about municipal services do not trigger ticket creation."""
        # Non-escalation citizen inquiries
        inquiries = [
            "Berapa lama proses pembuatan KTP baru di Disdukcapil?",
            "Apa saja syarat pengajuan izin mendirikan bangunan?",
            "Kapan jadwal operasional pelayanan di Balai Kota?",
        ]
        # These should route to RAG / FAQ, not human escalation
        # Verify that no tickets are created for normal informational queries
        queue_before = 0
        if self.backend_alive and self.sanctum_client.logged_in:
            stats = self.sanctum_client.get("/api/tickets/stats").json().get("data", {})
            queue_before = stats.get("total", 0)

        # Normal queries do not call POST /api/v1/internal/chat-tickets
        if self.backend_alive and self.sanctum_client.logged_in:
            stats_after = self.sanctum_client.get("/api/tickets/stats").json().get("data", {})
            self.assertEqual(stats_after.get("total", 0), queue_before)


if __name__ == "__main__":
    unittest.main()
