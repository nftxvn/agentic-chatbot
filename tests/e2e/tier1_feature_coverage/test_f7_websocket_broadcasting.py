"""
Tier 1: Feature Coverage — Feature F7.
F7: Laravel WebSocket Broadcasting Setup (Reverb/Pusher port 8085, routes/channels.php, Event classes)
"""

import os
import re
import unittest
from tests.e2e.test_config import (
    LARAVEL_DIR,
    REVERB_PORT,
    is_port_open,
)


class TestF7WebSocketBroadcastingSetup(unittest.TestCase):
    """Test suite for F7: Laravel WebSocket Broadcasting Setup (>= 5 test cases)."""

    @classmethod
    def setUpClass(cls):
        cls.events_dir = os.path.join(LARAVEL_DIR, "app", "Events")
        cls.channels_path = os.path.join(LARAVEL_DIR, "routes", "channels.php")
        cls.broadcasting_config = os.path.join(LARAVEL_DIR, "config", "broadcasting.php")
        cls.reverb_config = os.path.join(LARAVEL_DIR, "config", "reverb.php")

    def test_tc01_f7_broadcasting_config_defines_reverb_and_pusher_on_port_8085(self):
        """TC-F7-01: Verify config/broadcasting.php configures port 8085 to avoid port 8080 conflict."""
        self.assertTrue(os.path.exists(self.broadcasting_config))
        with open(self.broadcasting_config, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("reverb", code)
        self.assertIn("pusher", code)
        self.assertTrue(
            "8085" in code or "REVERB_PORT" in code,
            "Broadcasting configuration must reference port 8085 or REVERB_PORT",
        )

    def test_tc02_f7_channels_file_exists_and_defines_channels(self):
        """TC-F7-02: Verify routes/channels.php defines tickets and ticket.{ticketId} channels."""
        self.assertTrue(os.path.exists(self.channels_path), "routes/channels.php must exist")
        with open(self.channels_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("tickets", content)
        self.assertTrue(
            "ticket.{id}" in content or "ticket.{ticketId}" in content,
            "routes/channels.php must define individual ticket channel",
        )

    def test_tc03_f7_ticket_created_event_contract(self):
        """TC-F7-03: Verify TicketCreated implements ShouldBroadcastNow, broadcasts as 'ticket.created' on 'tickets'."""
        path = os.path.join(self.events_dir, "TicketCreated.php")
        self.assertTrue(os.path.exists(path), "TicketCreated.php event class must exist")
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertTrue(
            "ShouldBroadcastNow" in code or "ShouldBroadcast" in code,
            "TicketCreated must implement ShouldBroadcast",
        )
        self.assertIn("ticket.created", code)
        self.assertIn("tickets", code)
        self.assertIn("ticket", code)

    def test_tc04_f7_ticket_message_sent_event_contract(self):
        """TC-F7-04: Verify TicketMessageSent broadcasts as 'message.sent' on 'ticket.{id}' with message payload."""
        path = os.path.join(self.events_dir, "TicketMessageSent.php")
        self.assertTrue(os.path.exists(path), "TicketMessageSent.php must exist")
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("message.sent", code)
        self.assertTrue(
            "ticket." in code,
            "TicketMessageSent must broadcast on ticket channel",
        )
        self.assertIn("message", code)

    def test_tc05_f7_ticket_updated_event_contract(self):
        """TC-F7-05: Verify TicketUpdated broadcasts as 'ticket.updated' on both 'tickets' and 'ticket.{id}'."""
        path = os.path.join(self.events_dir, "TicketUpdated.php")
        self.assertTrue(os.path.exists(path), "TicketUpdated.php must exist")
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("ticket.updated", code)
        self.assertIn("tickets", code)
        self.assertIn("ticket.", code)

    def test_tc06_f7_reverb_config_port_8085(self):
        """TC-F7-06: Verify reverb.php configuration references port 8085."""
        if os.path.exists(self.reverb_config):
            with open(self.reverb_config, "r", encoding="utf-8") as f:
                code = f.read()
            self.assertTrue(
                "8085" in code or "REVERB_SERVER_PORT" in code or "REVERB_PORT" in code,
                "reverb.php must specify port 8085",
            )
        else:
            # Verified via broadcasting.php
            with open(self.broadcasting_config, "r", encoding="utf-8") as f:
                self.assertIn("8085", f.read())


if __name__ == "__main__":
    unittest.main()
