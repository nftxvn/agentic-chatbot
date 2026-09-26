# Dispatch for Worker M1: Laravel Backend Implementation

## Task Assignment
- Working Directory: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_worker_m1
- Authoritative Request: D:/magang/agentic/agentic-chatbot/.agents/teamwork/ORIGINAL_REQUEST.md
- Project Scope Document: D:/magang/agentic/agentic-chatbot/PROJECT.md
- Explorer Findings: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_explorer_survey_1/handoff.md
- Project Root: D:/magang/agentic/agentic-chatbot

## Exclusive File Ownership
You exclusively own and may edit files in `laravel-admin/`:
- `laravel-admin/database/migrations/*` (new migration for chat_tickets & chat_ticket_messages)
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

## Objective & Scope (Milestone 1: F1 - F7)
1. **Migrations & Models**:
   - Create migration for `chat_tickets` and `chat_ticket_messages` tables.
   - `chat_tickets`: id, ticket_number, session_id (indexed), citizen_name, citizen_contact, citizen_agency, channel, status ('open', 'in_progress', 'resolved', 'closed'), priority ('low', 'medium', 'high', 'urgent'), issue_summary, assigned_admin_id (nullable, fk to users.id), metadata (json nullable), last_message_at, resolved_at, closed_at, timestamps.
   - `chat_ticket_messages`: id, ticket_id (fk to chat_tickets.id cascade delete), sender_type ('citizen', 'agent', 'bot', 'system'), sender_id (nullable, fk to users.id), sender_name, message, attachments (json nullable), is_internal_note (bool default false), timestamps.
   - Eloquent models `ChatTicket` and `ChatTicketMessage` with relationships (`messages`, `ticket`, `assignedAdmin`), scopes (`open`, `inProgress`, `resolved`), and status helpers.
2. **Admin REST API (`TicketController.php`)**:
   - `GET /api/tickets`: List tickets with status filter, search, pagination.
   - `GET /api/tickets/stats`: Total, open, in_progress, resolved counts.
   - `GET /api/tickets/{id}`: Single ticket details with message thread.
   - `POST /api/tickets/{id}/assign`: Assign ticket to admin.
   - `PATCH /api/tickets/{id}/status`: Update ticket status.
   - `GET /api/tickets/{id}/messages`: Message thread.
   - `POST /api/tickets/{id}/messages`: Agent reply. Persists message, updates ticket last_message_at, dispatches `TicketMessageSent` and `TicketUpdated`.
3. **Internal Handoff API (`InternalTicketController.php`)**:
   - `POST /api/v1/internal/chat-tickets`: Creates or updates ticket from Python AI.
   - Protected by `AuthenticateInternalService` (`auth.internal`) validating `INTERNAL_API_TOKEN` / `AI_SERVICE_TOKEN` (`dev-internal-token-secret-1234567890`).
   - If `ticket_id` is supplied, append message and update ticket. Otherwise create new `ChatTicket` with status `open`, create initial citizen message, and dispatch `TicketCreated`.
4. **Broadcasting & Reverb/Pusher**:
   - Create `config/broadcasting.php` supporting `reverb`, `pusher`, `log`, `null`.
   - Register `channels: __DIR__.'/../routes/channels.php'` in `bootstrap/app.php`.
   - Create `routes/channels.php` authorizing channels.
   - Event classes `TicketCreated`, `TicketMessageSent`, `TicketUpdated` implementing `ShouldBroadcastNow`.
   - Channels: public channel `tickets` and `ticket.{ticketId}`.
5. **Testing & Verification**:
   - Create `tests/Feature/TicketManagementTest.php` testing all admin endpoints, internal endpoint, validation, and broadcasting event assertions using `Event::fake()`.
   - Run tests using `php artisan test --filter=TicketManagementTest` (or docker equivalent if needed) to ensure 100% pass.
   - Document commands and results in `handoff.md`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.


## 2026-09-26T10:13:34Z
You are Worker M1: Laravel Backend Implementation Worker.
Your working directory is: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_worker_m1
You MUST read the authoritative user request at: D:/magang/agentic/agentic-chatbot/.agents/teamwork/ORIGINAL_REQUEST.md
Also read PROJECT.md at: D:/magang/agentic/agentic-chatbot/PROJECT.md
Read your assignment at: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_worker_m1/DISPATCH.md
Read the backend explorer findings at: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_explorer_survey_1/handoff.md

Your exclusive file boundaries:
You own files in `laravel-admin/`:
- database/migrations/*create_chat_tickets*
- app/Models/ChatTicket.php
- app/Models/ChatTicketMessage.php
- app/Http/Controllers/Api/TicketController.php
- app/Http/Controllers/Api/InternalTicketController.php
- app/Http/Middleware/AuthenticateInternalService.php
- app/Events/TicketCreated.php
- app/Events/TicketMessageSent.php
- app/Events/TicketUpdated.php
- routes/channels.php
- routes/api.php
- config/broadcasting.php
- config/reverb.php
- bootstrap/app.php
- tests/Feature/TicketManagementTest.php

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Execute the implementation of Milestone 1 (F1 through F7 per PROJECT.md).
Run tests (via php artisan test or vendor/bin/phpunit) to verify all migrations, models, endpoints, and event broadcasting assertions pass 100%.
Write your comprehensive completion report following the Handoff Protocol to:
D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_worker_m1/handoff.md
Send a message to parent when done.
