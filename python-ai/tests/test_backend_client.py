import json
import unittest
from unittest.mock import MagicMock, patch

from app.services.backend_client import build_ticket_payload, dispatch_ticket_to_laravel, _TICKET_ENDPOINTS
from app.config import settings


class TicketPayloadTests(unittest.TestCase):
    def test_channel_and_contact_are_inferred_from_session(self):
        payload = build_ticket_payload("whatsapp-08123", "Butuh petugas")

        self.assertEqual(payload["channel"], "whatsapp")
        self.assertEqual(payload["citizen_contact"], "08123")
        self.assertEqual(payload["issue_summary"], "Butuh petugas")

    def test_explicit_values_override_inference(self):
        payload = build_ticket_payload(
            "telegram-123",
            "Butuh petugas",
            citizen_contact="user@example.test",
            channel="widget",
            issue_summary="Ringkasan eksplisit",
        )

        self.assertEqual(payload["channel"], "widget")
        self.assertEqual(payload["citizen_contact"], "user@example.test")
        self.assertEqual(payload["issue_summary"], "Ringkasan eksplisit")

    def test_issue_summary_is_limited_to_two_hundred_characters_by_default(self):
        payload = build_ticket_payload("web-123", "x" * 250)

        self.assertEqual(len(payload["issue_summary"]), 200)
        self.assertEqual(payload["channel"], "web")


class TicketEndpointTests(unittest.TestCase):
    def test_explicit_laravel_instance_is_exclusive_even_when_unreachable(self):
        with patch.dict("os.environ", {"LARAVEL_BASE_URL": " http://127.0.0.1:18000/ "}), \
                patch("urllib.request.urlopen", side_effect=OSError("unavailable")) as send:
            self.assertIsNone(dispatch_ticket_to_laravel("synthetic", "Test"))
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args.args[0].full_url, "http://127.0.0.1:18000/api/v1/internal/chat-tickets")

    def test_default_discovery_order_is_preserved_without_explicit_instance(self):
        with patch.dict("os.environ", {"LARAVEL_BASE_URL": ""}), \
                patch("urllib.request.urlopen", side_effect=OSError("unavailable")) as send:
            self.assertIsNone(dispatch_ticket_to_laravel("synthetic", "Test"))
        self.assertEqual([call.args[0].full_url for call in send.call_args_list], list(_TICKET_ENDPOINTS))

    def test_configured_instance_success_preserves_internal_auth_and_payload(self):
        response = MagicMock()
        response.__enter__.return_value.status = 201
        response.__enter__.return_value.read.return_value = b'{"success":true}'
        with patch.dict("os.environ", {"LARAVEL_BASE_URL": "http://127.0.0.1:18000"}), \
                patch("urllib.request.urlopen", return_value=response) as send:
            result = dispatch_ticket_to_laravel("synthetic", "Test")
        self.assertEqual(result, {"success": True})
        request = send.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), f"Bearer {settings.INTERNAL_API_TOKEN}")
        self.assertEqual(json.loads(request.data)["session_id"], "synthetic")
        self.assertEqual(json.loads(request.data)["message"], "Test")
        self.assertEqual(send.call_args.kwargs["timeout"], 3.0)
