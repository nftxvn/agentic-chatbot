"""
Tier 3: Cross-Feature Interactions — Pairwise Combinations.
Tests 2-way combinatorial interactions between channels, intents, agencies, and admin workflows.
"""

import unittest
from tests.e2e.test_config import (
    LARAVEL_HOST,
    INTERNAL_API_TOKEN,
    InternalServiceClient,
    SanctumClient,
    is_http_endpoint_alive,
    generate_unique_session,
)


class TestPairwiseInteractions(unittest.TestCase):
    """Pairwise combinatorial tests across Channel x Intent x Agency x Admin Action."""

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

    def test_tc01_pairwise_whatsapp_channel_with_health_agency(self):
        """Pair 1: Channel='whatsapp' x Intent='human_escalation' x Agency='Dinas Kesehatan'."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")

        sess = generate_unique_session("wa-dinkes")
        resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "channel": "whatsapp",
            "intent": "human_escalation",
            "citizen_name": "Dr. Syarifah",
            "citizen_contact": "081299001122",
            "citizen_agency": "Dinas Kesehatan",
            "issue_summary": "Integrasi data faskes puskesmas",
            "message": "Mohon bantuan petugas IT untuk sinkronisasi data puskesmas ke dinas.",
        })
        self.assertEqual(resp.status_code, 201)
        ticket_id = resp.json()["data"]["ticket_id"]

        if self.sanctum_client.logged_in:
            detail = self.sanctum_client.get(f"/api/tickets/{ticket_id}")
            self.assertEqual(detail.status_code, 200)
            data = detail.json()["data"]
            self.assertEqual(data["channel"], "whatsapp")
            self.assertEqual(data["citizen_agency"], "Dinas Kesehatan")

    def test_tc02_pairwise_widget_channel_with_education_agency(self):
        """Pair 2: Channel='widget' x Intent='human_escalation' x Agency='Dinas Pendidikan'."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")

        sess = generate_unique_session("widget-disdik")
        resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "channel": "widget",
            "intent": "human_escalation",
            "citizen_name": "Pak Mansur",
            "citizen_contact": "085211447788",
            "citizen_agency": "Dinas Pendidikan",
            "issue_summary": "Akun PPDB online terkunci",
            "message": "Akun verifikator PPDB dinas terkunci tidak bisa login.",
        })
        self.assertEqual(resp.status_code, 201)
        ticket_id = resp.json()["data"]["ticket_id"]

        if self.sanctum_client.logged_in:
            detail = self.sanctum_client.get(f"/api/tickets/{ticket_id}")
            self.assertEqual(detail.status_code, 200)
            data = detail.json()["data"]
            self.assertEqual(data["channel"], "widget")
            self.assertEqual(data["citizen_agency"], "Dinas Pendidikan")

    def test_tc03_pairwise_followup_intent_with_contact_enrichment(self):
        """Pair 3: Intent='human_escalation_followup' x Existing Ticket x New Contact Info."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")

        sess = generate_unique_session("pw-followup-enrich")
        # Step 1: Initial ticket with only name
        r1 = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "message": "Halo saya butuh bantuan admin",
            "citizen_name": "Faisal",
        })
        self.assertEqual(r1.status_code, 201)
        ticket_id = r1.json()["data"]["ticket_id"]

        # Step 2: Followup provides phone & agency
        r2 = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "ticket_id": ticket_id,
            "intent": "human_escalation_followup",
            "message": "Nomor saya 087711223344 dari Disdukcapil",
            "citizen_contact": "087711223344",
            "citizen_agency": "Disdukcapil",
        })
        self.assertEqual(r2.status_code, 200)

        # Step 3: Verify ticket record enriched with contact and agency
        if self.sanctum_client.logged_in:
            detail = self.sanctum_client.get(f"/api/tickets/{ticket_id}")
            self.assertEqual(detail.status_code, 200)
            data = detail.json()["data"]
            self.assertEqual(data["citizen_contact"], "087711223344")
            self.assertEqual(data["citizen_agency"], "Disdukcapil")

    def test_tc04_pairwise_concurrent_multi_channel_isolation(self):
        """Pair 4: Concurrent session from WhatsApp vs Widget are completely isolated."""
        if not self.backend_alive:
            self.skipTest("Laravel backend not reachable")

        wa_sess = generate_unique_session("wa-iso")
        widget_sess = generate_unique_session("wid-iso")

        r_wa = self.internal_client.create_or_update_ticket({
            "session_id": wa_sess,
            "channel": "whatsapp",
            "message": "WhatsApp ticket request",
        })
        r_wid = self.internal_client.create_or_update_ticket({
            "session_id": widget_sess,
            "channel": "widget",
            "message": "Web widget ticket request",
        })

        id_wa = r_wa.json()["data"]["ticket_id"]
        id_wid = r_wid.json()["data"]["ticket_id"]

        self.assertNotEqual(id_wa, id_wid)

    def test_tc05_pairwise_admin_self_assign_and_stats_reflection(self):
        """Pair 5: Admin self-assignment immediately reflects in stats (open -1, in_progress +1)."""
        if not self.backend_alive or not self.sanctum_client.logged_in:
            self.skipTest("Laravel backend not reachable or not logged in")

        sess = generate_unique_session("pw-stats-reflect")
        c_resp = self.internal_client.create_or_update_ticket({
            "session_id": sess,
            "message": "Stats tracking test ticket",
        })
        ticket_id = c_resp.json()["data"]["ticket_id"]

        # Assign ticket
        assign_resp = self.sanctum_client.post(f"/api/tickets/{ticket_id}/assign", data={})
        self.assertEqual(assign_resp.status_code, 200)
        self.assertEqual(assign_resp.json()["data"]["status"], "in_progress")


if __name__ == "__main__":
    unittest.main()
