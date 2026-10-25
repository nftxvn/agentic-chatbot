"""HTTP adapter for internal calls from Python AI to the Laravel backend."""

import json
import logging
import os
import urllib.request
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_TICKET_ENDPOINTS = (
    "http://laravel-backend:8000/api/v1/internal/chat-tickets",
    "http://agentic-laravel-admin:8000/api/v1/internal/chat-tickets",
    "http://localhost:8000/api/v1/internal/chat-tickets",
    "http://host.docker.internal:8000/api/v1/internal/chat-tickets",
)


def _infer_channel(session_id: str) -> str:
    if session_id.startswith("telegram-"):
        return "telegram"
    if session_id.startswith(("wa-", "whatsapp-")):
        return "whatsapp"
    return "web"


def build_ticket_payload(
    session_id: str,
    message: str,
    intent: str = "human_escalation",
    citizen_name: str | None = None,
    citizen_contact: str | None = None,
    citizen_agency: str | None = None,
    issue_summary: str | None = None,
    channel: str | None = None,
) -> dict[str, Any]:
    """Build the stable payload expected by Laravel's internal ticket endpoint."""
    return {
        "session_id": session_id,
        "message": message,
        "intent": intent,
        "citizen_name": citizen_name,
        "citizen_contact": citizen_contact or session_id.replace("telegram-", "").replace("wa-", "").replace("whatsapp-", ""),
        "citizen_agency": citizen_agency,
        "issue_summary": issue_summary or message[:200],
        "channel": channel or _infer_channel(session_id),
    }


def dispatch_ticket_to_laravel(
    session_id: str,
    message: str,
    intent: str = "human_escalation",
    citizen_name: str | None = None,
    citizen_contact: str | None = None,
    citizen_agency: str | None = None,
    issue_summary: str | None = None,
    channel: str | None = None,
) -> dict[str, Any] | None:
    """Send a ticket to the configured Laravel base URL or legacy discovery list.

    An explicit base URL is exclusive: a failed configured deployment must not
    fall through to another Laravel instance on a default hostname or port.
    """
    payload = build_ticket_payload(
        session_id=session_id,
        message=message,
        intent=intent,
        citizen_name=citizen_name,
        citizen_contact=citizen_contact,
        citizen_agency=citizen_agency,
        issue_summary=issue_summary,
        channel=channel,
    )
    req_data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {settings.INTERNAL_API_TOKEN}",
        "X-Internal-Token": settings.INTERNAL_API_TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    base_url = os.getenv("LARAVEL_BASE_URL", "").strip().rstrip("/")
    endpoints = (f"{base_url}/api/v1/internal/chat-tickets",) if base_url else _TICKET_ENDPOINTS
    for url in endpoints:
        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status in (200, 201):
                    res_body = json.loads(resp.read().decode("utf-8"))
                    logger.info("Berhasil dispatch tiket ke Laravel (%s): %s", url, res_body.get("message"))
                    return res_body
        except Exception as exc:
            logger.debug("Gagal dispatch tiket ke %s: %s", url, exc)

    logger.warning("Gagal mengirim dispatch tiket ke seluruh endpoint Laravel.")
    return None
