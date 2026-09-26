# Dispatch for Worker M1 (Iteration 2 Remediation)

## 2026-09-26T10:35:51Z

## Task Assignment
- Working Directory: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_worker_m1_r2
- Authoritative Request: D:/magang/agentic/agentic-chatbot/.agents/teamwork/ORIGINAL_REQUEST.md
- Project Scope Document: D:/magang/agentic/agentic-chatbot/PROJECT.md
- Gate Status & Feedback: D:/magang/agentic/agentic-chatbot/.agents/teamwork/orchestrator_1/GATE_STATUS.md
- Reviewer 1 Handoff: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_reviewer_m1_1/handoff.md
- Reviewer 2 Handoff: D:/magang/agentic/agentic-chatbot/.agents/teamwork/teamwork_preview_reviewer_m1_2/handoff.md
- Project Root: D:/magang/agentic/agentic-chatbot

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Remediation Requirements (Milestone 1, Iteration 2)
Implement the fixes requested by Reviewers and Challengers:
1. **Public/Private Channel Segregation & Internal Notes**:
   - In `app/Events/TicketMessageSent.php`: If `$this->message->is_internal_note` is true, do NOT broadcast to public channels (`ticket.{id}` or `tickets`). Instead, broadcast only to `PrivateChannel('admin-tickets')` or suppress broadcast to non-staff.
   - In `routes/channels.php`: Ensure channel authorizations genuinely check `$user !== null` for `admin-tickets` and `admin-ticket.{id}`. For public channels (`ticket.{id}` and `tickets`), define them appropriately as public channels.
2. **Prevent Cross-Session Ticket Hijacking**:
   - In `app/Http/Controllers/Api/InternalTicketController.php`: When `$request->filled('ticket_id')`, verify that the ticket exists AND belongs to the incoming `session_id`. If it does not match, either reject with 403 or fall back to finding/creating by `session_id`.
3. **Reopen Resolved/Closed Tickets on Citizen Follow-up**:
   - In `InternalTicketController.php`: When a citizen followup arrives for a ticket that is `resolved` or `closed`, update the ticket status back to `open` (or `in_progress`) and clear `resolved_at` / `closed_at`.
4. **Eliminate N+1 Query Storm on Queue Listing**:
   - In `app/Models/ChatTicket.php`: Remove `unread_messages_count` from protected `$appends`.
   - In `app/Http/Controllers/Api/TicketController.php`: In `index()`, compute or eager-load unread counts using a single grouped subquery or `withCount` so that fetching 50 tickets generates a constant number of queries (<= 3 queries total), eliminating the N+1 problem.
5. **Fix Unread Messages Count Reset Bug**:
   - In `ChatTicket::getUnreadMessagesCountAttribute`: Ensure that staff internal notes (`is_internal_note = true`) do NOT reset the unread citizen message count. Only non-internal agent messages (`is_internal_note = false` and `sender_type = 'agent'`) reset the count.
6. **Validation Alignment**:
   - Align `session_id` validation in `InternalTicketController` and `TicketController` to `max:100` (matching migration column).
7. **Test Database Isolation**:
   - In `laravel-admin/phpunit.xml`: Add `force="true"` to `DB_CONNECTION` and `DB_DATABASE` so tests always run against in-memory SQLite and never collide with MySQL.
8. **Test Execution**:
   - Run the full test suite (`phpunit` and `TicketManagementTest`) and confirm 100% pass with new tests verifying all remediations.
   - Document commands and results in your handoff report.
