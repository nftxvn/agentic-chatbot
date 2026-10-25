import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app import security


class BearerAuthenticationTests(unittest.IsolatedAsyncioTestCase):
    def test_accepts_matching_bearer_token(self):
        with patch.object(security.settings, "INTERNAL_API_TOKEN", "expected"):
            self.assertEqual(security.assert_valid_bearer("Bearer expected"), "expected")

    def test_rejects_missing_or_malformed_header(self):
        for authorization in (None, "expected", "Bearer"):
            with self.subTest(authorization=authorization):
                with self.assertRaises(HTTPException) as raised:
                    security.assert_valid_bearer(authorization)
                self.assertEqual(raised.exception.status_code, 401)

    def test_rejects_wrong_token(self):
        with patch.object(security.settings, "INTERNAL_API_TOKEN", "expected"):
            with self.assertRaises(HTTPException) as raised:
                security.assert_valid_bearer("Bearer incorrect")
        self.assertEqual(raised.exception.status_code, 401)

    async def test_stream_auth_can_be_disabled_for_local_development(self):
        with patch.object(security.settings, "CHAT_STREAM_REQUIRE_AUTH", False):
            self.assertIsNone(await security.verify_chat_stream_token(None))

    async def test_stream_auth_requires_token_when_enabled(self):
        with (
            patch.object(security.settings, "CHAT_STREAM_REQUIRE_AUTH", True),
            patch.object(security.settings, "INTERNAL_API_TOKEN", "expected"),
        ):
            self.assertEqual(
                await security.verify_chat_stream_token("Bearer expected"), "expected"
            )
