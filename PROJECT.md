# Project: Live Chat & Helpdesk Ticket Management System (Human Handoff)

## Architecture
The system integrates three core components to provide real-time human handoff and live chat capabilities:
1. **Laravel Backend (`laravel-admin`)**:
   - Primary data store for tickets (`chat_tickets`) and messages (`chat_ticket_messages`).
   - Authenticated Admin REST API endpoints under Sanctum cookie auth for ticket queue management, status transition, assignment, and replies.
   - Secure internal REST endpoint under `auth.internal` (`dev-internal-token-secret-1234567890`) for automated ticket creation and update from Python AI.
   - Event Broadcasting infrastructure supporting Laravel Reverb and Pusher protocol on dedicated port `8085` (avoiding conflict with Python AI on port `8080`). Dispatches `TicketCreated`, `TicketMessageSent`, and `TicketUpdated`.
2. **Python AI Service (`python-ai`)**:
   - Detects `human_escalation` and `human_escalation_followup` intents via regex & session history in `tool_router.py`.
   - Extracts citizen contact information (name, phone, email, agency, issue summary).
   - Manages citizen session memory with active ticket ID tracking.
   - Dispatches internal HTTP payload to Laravel Backend (`POST /api/v1/internal/chat-tickets`) while returning a graceful citizen-facing handoff message.
   - Preserves 100% of existing RAG hybrid retrieval, document extraction, and FAQ fast-path capabilities.
3. **React Admin Dashboard (`admin-frontend`)**:
   - Adds "Live Chat / Helpdesk" menu item in `AdminLayout.jsx` and route in `App.jsx`.
   - Split-panel interface:
     - Left panel: Searchable ticket list with status filter tabs (All, Open, In Progress, Resolved) and real-time updates.
     - Right panel: Active conversation thread, citizen info header, assign-to-me button, status dropdown, reply input box with canned responses.
   - Real-time WebSocket connection via `laravel-echo` / `pusher-js` configured for Reverb on port `8085` with automatic polling fallback.

```
Citizen (Web Widget / WhatsApp)
            │
            ▼
    [Python AI Service] (port 8080)
      • tool_router.py (intent detection: human_escalation, followup)
      • contact extractor (name, phone, email, issue)
      • session_memory (tracks ticket_id)
            │ (Internal HTTP POST /api/v1/internal/chat-tickets with Bearer token)
            ▼
    [Laravel Backend] (port 8000)
      • chat_tickets & chat_ticket_messages
      • Api/TicketController & Api/InternalTicketController
      • Events: TicketCreated, TicketMessageSent, TicketUpdated
            │ (WebSocket broadcast on port 8085 - Reverb/Pusher protocol)
            ▼
    [React Admin Dashboard] (port 5173)
      • LiveChatPage (Split-panel UI)
      • laravel-echo / pusher-js listener on 'tickets' & 'ticket.{id}'
      • REST client (ticketsApi) for replies, status changes, assignments
```

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | `chat_tickets` Migration & Model | Schema tracking session ID, ticket number, citizen name/contact/agency, issue summary, status (open/in_progress/resolved/closed), priority, assigned admin, timestamps | M1 | R1, survey_1 |
| F2 | `chat_ticket_messages` Migration & Model | Schema tracking ticket ID, sender type (citizen/agent/bot/system), sender ID, sender name, message body, attachments, internal notes flag, timestamps | M1 | R1, survey_1 |
| F3 | Admin REST API: Queue Listing & Stats | `GET /api/tickets` with search, status filters (open/in_progress/resolved/closed), pagination; and `GET /api/tickets/stats` | M1 | R1, survey_1 |
| F4 | Admin REST API: Detail, Assign & Status | `GET /api/tickets/{id}`, `POST /api/tickets/{id}/assign`, `PATCH /api/tickets/{id}/status` | M1 | R1, survey_1 |
| F5 | Admin REST API: Message Thread & Reply | `GET /api/tickets/{id}/messages`, `POST /api/tickets/{id}/messages` (persisting reply and triggering real-time broadcast) | M1 | R1, survey_1 |
| F6 | Internal Handoff Ingestion Endpoint | `POST /api/v1/internal/chat-tickets` protected by `auth.internal` middleware validating `INTERNAL_API_TOKEN` | M1 | R1, R2, survey_1, survey_2 |
| F7 | Laravel WebSocket Broadcasting Setup | `config/broadcasting.php`, `routes/channels.php`, Reverb/Pusher configuration on port 8085, and event classes `TicketCreated`, `TicketMessageSent`, `TicketUpdated` | M1 | R1, survey_1, survey_3 |
| F8 | Citizen Contact & Issue Extractor | Regex parser extracting citizen name, Indonesian phone (08xx/+62xx), email, agency/instansi, and issue summary from chat messages | M2 | R2, survey_2 |
| F9 | Session Ticket ID State Management | Cache ticket ID in `session_memory.py` across conversation turns to correlate follow-up messages to the same ticket | M2 | R2, survey_2 |
| F10 | Python AI Outbound Handoff Dispatch | Resilient HTTP client dispatching escalation payload to Laravel internal endpoint on `human_escalation` and `human_escalation_followup` | M2 | R2, survey_2 |
| F11 | Graceful Citizen Escalation Responses | Contextual canned responses confirming handoff and advising Call Center 112 / Balai Kota contact details | M2 | R2, survey_2 |
| F12 | Existing RAG Pipeline Preservation | Maintain 100% functionality of RAG hybrid retrieval, document extraction, and FAQ fast-path without regression | M2 | R2, survey_2 |
| F13 | Echo & WebSocket Client Infrastructure | Install `laravel-echo` & `pusher-js`, configure `src/lib/echo.js` pointing to Reverb port 8085 with resilient polling fallback | M3 | R3, survey_3 |
| F14 | Navigation & Route Integration | Register `/live-chat` in `App.jsx`, add "Live Chat / Helpdesk" item to sidebar `NAV_ITEMS` and `QUICK_FEATURES` in `AdminLayout.jsx` | M3 | R3, survey_3 |
| F15 | Split-Panel Ticket List UI (Left Panel) | Search bar, unread counts, GSAP status filter tabs (All, Open, In Progress, Resolved), ticket cards with status badges and relative times | M3 | R3, survey_3 |
| F16 | Split-Panel Conversation Thread UI (Right Panel) | Citizen details header, status dropdown, assign button, auto-scrolling message bubbles (citizen left, admin right, system center), reply input bar | M3 | R3, survey_3 |
| F17 | Real-Time UI Synchronization | Auto-insert incoming tickets and new citizen messages via WebSocket events without page refresh | M3 | R3, survey_3 |
| F18 | E2E Integration & Verification | Multi-tier test suite verifying handoff query -> ticket creation -> WebSocket broadcast -> admin reply -> status update -> RAG regression testing | M4 | Acceptance Criteria |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Laravel Backend Ticket & Live Chat Data Model, API, & Broadcasting | F1, F2, F3, F4, F5, F6, F7 | none | PLANNED |
| M2 | Python AI Service Handoff Dispatch & Intent Integration | F8, F9, F10, F11, F12 | M1 Contract | PLANNED |
| M3 | React Admin Dashboard Live Chat UI & WebSocket Listener | F13, F14, F15, F16, F17 | M1 Contract | PLANNED |
| M4 | Dual-Track E2E Integration & Adversarial Verification | F18, Tier 1-5 validation | M1, M2, M3 | PLANNED |

---

## Interface Contracts

### 1. Python AI (`python-ai`) ↔ Laravel Backend (`laravel-admin`)
- **Endpoint**: `POST /api/v1/internal/chat-tickets`
- **Authentication**: `Authorization: Bearer <INTERNAL_API_TOKEN>` (token: `dev-internal-token-secret-1234567890`)
- **Request Body**:
  ```json
  {
    "session_id": "string (e.g. 'web-session-uuid' or 'wa-08123456789')",
    "ticket_id": "integer|null (optional, if continuing an existing ticket)",
    "intent": "human_escalation | human_escalation_followup",
    "message": "string (citizen query/message)",
    "citizen_name": "string|null",
    "citizen_contact": "string|null (phone or email)",
    "citizen_agency": "string|null",
    "issue_summary": "string",
    "channel": "widget | whatsapp | telegram"
  }
  ```
- **Response Body (200 / 201)**:
  ```json
  {
    "success": true,
    "message": "Ticket created or updated successfully",
    "data": {
      "ticket_id": 12,
      "ticket_number": "TICK-2026-00012",
      "status": "open",
      "session_id": "web-session-uuid",
      "created_at": "2026-09-26T10:15:00Z"
    }
  }
  ```
- **Error Handling**:
  - `401 Unauthorized`: Invalid internal token.
  - `422 Unprocessable Content`: Missing required fields (`session_id`, `message`).
  - Python AI must catch connection errors and timeouts (3s) gracefully without breaking citizen chat streaming.

### 2. Laravel Backend (`laravel-admin`) ↔ React Admin Frontend (`admin-frontend`)
- **Base URL**: `/api/tickets`
- **Authentication**: Laravel Sanctum cookie session (`withCredentials: true`, `X-Requested-With: XMLHttpRequest`).

#### Endpoints:
1. `GET /api/tickets`
   - Query params: `status` (`all`|`open`|`in_progress`|`resolved`|`closed`), `search` (keyword), `page`, `per_page`.
   - Response:
     ```json
     {
       "success": true,
       "data": [
         {
           "id": 12,
           "ticket_number": "TICK-2026-00012",
           "session_id": "web-session-uuid",
           "citizen_name": "Budi Santoso",
           "citizen_contact": "08123456789",
           "citizen_agency": "Dinas Pendidikan",
           "issue_summary": "Kendala login portal SPBE",
           "status": "open",
           "priority": "medium",
           "assigned_admin": { "id": 1, "name": "Admin Diskominfotik" },
           "unread_messages_count": 1,
           "last_message_at": "2026-09-26T10:15:00Z",
           "created_at": "2026-09-26T10:15:00Z"
         }
       ],
       "pagination": { "current_page": 1, "last_page": 1, "per_page": 15, "total": 1 }
     }
     ```
2. `GET /api/tickets/stats`
   - Response: `{"success": true, "data": {"total": 10, "open": 3, "in_progress": 4, "resolved": 3}}`
3. `GET /api/tickets/{id}`
   - Response: Full ticket details including message history and assigned admin object.
4. `POST /api/tickets/{id}/messages`
   - Request: `{"message": "Halo Budi, kendala sedang kami telusuri.", "is_internal_note": false}`
   - Response: `{"success": true, "data": { "id": 45, "ticket_id": 12, "sender_type": "agent", "sender_name": "Admin", "message": "...", "created_at": "..." }}`
5. `PATCH /api/tickets/{id}/status`
   - Request: `{"status": "in_progress" | "resolved" | "closed"}`
   - Response: `{"success": true, "data": { "id": 12, "status": "resolved" }}`
6. `POST /api/tickets/{id}/assign`
   - Request: `{"admin_id": 1}` (or empty for self-assign)
   - Response: `{"success": true, "data": { "id": 12, "assigned_admin_id": 1 }}`

### 3. Laravel Broadcasting ↔ React WebSocket Listener (`laravel-echo`)
- **Broadcasting Driver**: `reverb` / `pusher` protocol
- **Host**: `window.location.hostname`
- **Port**: `8085` (configured via `VITE_REVERB_PORT=8085` or `VITE_PUSHER_PORT=8085`)
- **Scheme**: `http` (local) / `https` (production)
- **Channels & Events**:
  - Channel `tickets`:
    - Event `.ticket.created` (`TicketCreated`): `{ "ticket": { ...ticket data... } }`
    - Event `.ticket.updated` (`TicketUpdated`): `{ "ticket": { ...ticket data... } }`
  - Channel `ticket.{ticketId}`:
    - Event `.message.sent` (`TicketMessageSent`): `{ "message": { ...message data... }, "ticket_id": 12 }`

---

## Code Layout & Exclusive File Boundaries
To prevent concurrency conflicts during implementation:
- **Milestone 1 (Laravel Backend)** owns:
  - `laravel-admin/database/migrations/*create_chat_tickets*`
  - `laravel-admin/app/Models/ChatTicket.php`
  - `laravel-admin/app/Models/ChatTicketMessage.php`
  - `laravel-admin/app/Http/Controllers/Api/TicketController.php`
  - `laravel-admin/app/Http/Controllers/Api/InternalTicketController.php`
  - `laravel-admin/app/Http/Middleware/AuthenticateInternalService.php`
  - `laravel-admin/app/Events/TicketCreated.php`
  - `laravel-admin/app/Events/TicketMessageSent.php`
  - `laravel-admin/app/Events/TicketUpdated.php`
  - `laravel-admin/routes/channels.php`
  - `laravel-admin/routes/api.php`
  - `laravel-admin/config/broadcasting.php`
  - `laravel-admin/config/reverb.php`
  - `laravel-admin/bootstrap/app.php`
  - `laravel-admin/tests/Feature/TicketManagementTest.php`
- **Milestone 2 (Python AI Service)** owns:
  - `python-ai/app/config.py`
  - `python-ai/app/services/tool_router.py`
  - `python-ai/app/services/session_memory.py`
  - `python-ai/app/services/rag_service.py`
  - `python-ai/app/services/backend_client.py`
  - `python-ai/test_rag_audit_fixes.py`
- **Milestone 3 (React Admin Frontend)** owns:
  - `admin-frontend/package.json`
  - `admin-frontend/src/lib/echo.js`
  - `admin-frontend/src/api/tickets.js`
  - `admin-frontend/src/pages/LiveChatPage.jsx`
  - `admin-frontend/src/components/Layout/AdminLayout.jsx`
  - `admin-frontend/src/App.jsx`
- **Milestone 4 (E2E Integration Track)** owns:
  - `tests/e2e/*` or root integration test scripts
  - `TEST_INFRA.md`
  - `TEST_READY.md`
