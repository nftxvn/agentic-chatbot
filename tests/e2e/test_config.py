"""
Global Test Configuration and HTTP Client Fixtures for E2E Tests.
Provides zero-dependency HTTP, Sanctum, and Internal Service clients using Python standard libraries.
"""

import os
import sys
import json
import uuid
import time
import socket
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
from typing import Any, Dict, Optional, Tuple

# Base Project Paths
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LARAVEL_DIR = os.path.join(WORKSPACE_ROOT, "laravel-admin")
PYTHON_AI_DIR = os.path.join(WORKSPACE_ROOT, "python-ai")
FRONTEND_DIR = os.path.join(WORKSPACE_ROOT, "admin-frontend")

# Service URLs & Ports
LARAVEL_HOST = os.getenv("LARAVEL_HOST", "http://localhost:8000")
AI_HOST = os.getenv("AI_HOST", "http://localhost:8080")
FRONTEND_HOST = os.getenv("FRONTEND_HOST", "http://localhost:5173")
REVERB_PORT = int(os.getenv("REVERB_PORT", "8085"))
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "dev-internal-token-secret-1234567890")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@diskominfotik.go.id")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme123")


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a network port is accepting TCP connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def is_http_endpoint_alive(url: str, timeout: float = 2.0) -> bool:
    """Check if an HTTP endpoint returns a valid response."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "E2ETestRunner/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 204, 301, 302)
    except urllib.error.HTTPError as e:
        return e.code < 500
    except Exception:
        return False


class APIResponse:
    def __init__(self, status_code: int, headers: dict, body: str, json_data: Optional[dict] = None):
        self.status_code = status_code
        self.headers = headers
        self.body = body
        self.json_data = json_data

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict:
        if self.json_data is not None:
            return self.json_data
        try:
            return json.loads(self.body)
        except Exception:
            return {}


class SanctumClient:
    """
    Authenticated HTTP client for Laravel Sanctum session auth.
    Uses standard http.cookiejar and urllib.request.
    """
    def __init__(self, base_url: str = LARAVEL_HOST):
        self.base_url = base_url.rstrip("/")
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.logged_in = False
        self.user_data: Optional[dict] = None

    def _get_xsrf_token(self) -> str:
        for cookie in self.cookie_jar:
            if cookie.name == "XSRF-TOKEN":
                return urllib.parse.unquote(cookie.value)
        return ""

    def init_csrf(self) -> bool:
        try:
            req = urllib.request.Request(
                f"{self.base_url}/sanctum/csrf-cookie",
                headers={
                    "Accept": "application/json",
                    "Referer": self.base_url,
                }
            )
            with self.opener.open(req, timeout=5) as resp:
                return resp.status == 204 or resp.status == 200
        except Exception:
            return False

    def login(self, email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD) -> Tuple[bool, Optional[dict]]:
        self.init_csrf()
        xsrf = self._get_xsrf_token()
        payload = json.dumps({"email": email, "password": password}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/login",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-XSRF-TOKEN": xsrf,
                "Referer": self.base_url,
            },
            method="POST"
        )
        try:
            with self.opener.open(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if resp.status == 200 and data.get("success"):
                    self.logged_in = True
                    self.user_data = data.get("data", {}).get("user")
                    return True, self.user_data
                return False, data
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read().decode("utf-8"))
            except Exception:
                body = {}
            # If invalid credentials, attempt auto-seed if running in Docker/dev
            if e.code == 401 or (isinstance(body, dict) and not body.get("success")):
                try:
                    import subprocess
                    subprocess.run(
                        ["docker", "exec", "agentic-laravel-admin", "php", "artisan", "db:seed", "--class=AdminSeeder"],
                        capture_output=True,
                        timeout=10,
                    )
                    # Retry login once after seeding
                    self.init_csrf()
                    xsrf = self._get_xsrf_token()
                    retry_req = urllib.request.Request(
                        f"{self.base_url}/api/auth/login",
                        data=payload,
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "X-XSRF-TOKEN": xsrf,
                            "Referer": self.base_url,
                        },
                        method="POST"
                    )
                    with self.opener.open(retry_req, timeout=5) as retry_resp:
                        retry_data = json.loads(retry_resp.read().decode("utf-8"))
                        if retry_resp.status == 200 and retry_data.get("success"):
                            self.logged_in = True
                            self.user_data = retry_data.get("data", {}).get("user")
                            return True, self.user_data
                except Exception:
                    pass
            return False, body
        except Exception:
            return False, None

    def request(self, method: str, endpoint: str, data: Optional[dict] = None, params: Optional[dict] = None, headers: Optional[dict] = None) -> APIResponse:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if params:
            query_str = urllib.parse.urlencode(params)
            url = f"{url}?{query_str}"

        req_headers = {
            "Accept": "application/json",
            "Referer": self.base_url,
            "X-Requested-With": "XMLHttpRequest",
        }
        xsrf = self._get_xsrf_token()
        if xsrf:
            req_headers["X-XSRF-TOKEN"] = xsrf

        if headers:
            req_headers.update(headers)

        payload_bytes = None
        if data is not None:
            req_headers["Content-Type"] = "application/json"
            payload_bytes = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(url, data=payload_bytes, headers=req_headers, method=method)

        try:
            with self.opener.open(req, timeout=10) as resp:
                resp_body = resp.read().decode("utf-8")
                try:
                    json_data = json.loads(resp_body)
                except Exception:
                    json_data = None
                return APIResponse(resp.status, dict(resp.headers), resp_body, json_data)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            try:
                json_data = json.loads(err_body)
            except Exception:
                json_data = None
            return APIResponse(e.code, dict(e.headers), err_body, json_data)
        except Exception as e:
            return APIResponse(599, {}, str(e), {"error": str(e)})

    def get(self, endpoint: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> APIResponse:
        return self.request("GET", endpoint, params=params, headers=headers)

    def post(self, endpoint: str, data: Optional[dict] = None, headers: Optional[dict] = None) -> APIResponse:
        return self.request("POST", endpoint, data=data, headers=headers)

    def patch(self, endpoint: str, data: Optional[dict] = None, headers: Optional[dict] = None) -> APIResponse:
        return self.request("PATCH", endpoint, data=data, headers=headers)

    def delete(self, endpoint: str, headers: Optional[dict] = None) -> APIResponse:
        return self.request("DELETE", endpoint, headers=headers)


class InternalServiceClient:
    """
    HTTP client for Python AI -> Laravel Backend internal ingestion.
    Authenticates via Bearer dev-internal-token-secret-1234567890 or X-Internal-Token.
    """
    def __init__(self, base_url: str = LARAVEL_HOST, token: str = INTERNAL_API_TOKEN):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def create_or_update_ticket(self, payload: dict, token_override: Optional[str] = None, use_custom_header: bool = False) -> APIResponse:
        url = f"{self.base_url}/api/v1/internal/chat-tickets"
        tok = self.token if token_override is None else token_override

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if tok is not None:
            if use_custom_header:
                headers["X-Internal-Token"] = tok
            else:
                headers["Authorization"] = f"Bearer {tok}"

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8")
                try:
                    json_data = json.loads(body)
                except Exception:
                    json_data = None
                return APIResponse(resp.status, dict(resp.headers), body, json_data)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                json_data = json.loads(body)
            except Exception:
                json_data = None
            return APIResponse(e.code, dict(e.headers), body, json_data)
        except Exception as e:
            return APIResponse(599, {}, str(e), {"error": str(e)})


def generate_unique_session(prefix: str = "test-session") -> str:
    """Generate a unique session identifier for test isolation."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"
