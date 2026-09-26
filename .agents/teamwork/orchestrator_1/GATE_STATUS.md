# Gate Status

## Milestone Status Summary
- M1 (Laravel Backend): REWORK_REQUIRED (Iteration 1 Gate Failed on Reviewer REQUEST_CHANGES)
- M2 (Python AI Service): PLANNED
- M3 (React Admin Frontend): PLANNED
- M4 (E2E Integration & Verification): PLANNED
- E2E Testing Track: COMPLETED (TEST_READY.md published)

---

## Gate — Milestone 1 (Iteration 1)
| Agent | Role | Verdict | Source |
|-------|------|---------|--------|
| worker_m1 | teamwork_preview_worker | DONE (build passed, 21/21 tests pass) | handoff.md |
| reviewer_m1_1 | teamwork_preview_reviewer | REQUEST_CHANGES | handoff.md |
| reviewer_m1_2 | teamwork_preview_reviewer | REQUEST_CHANGES | handoff.md |
| challenger_m1_1 | teamwork_preview_challenger | APPROVE | handoff.md |
| challenger_m1_2 | teamwork_preview_challenger | APPROVE | handoff.md |
| auditor_m1 | teamwork_preview_auditor | CLEAN | handoff.md |

Gate Result: **FAIL** (reviewer_m1_1 and reviewer_m1_2 REQUEST_CHANGES)

### Required Remediation for Iteration 2:
1. **Prevent Leaking Internal Staff Notes**: In `TicketMessageSent.php`, do not broadcast on public citizen channels when `is_internal_note = true`. Only broadcast internal notes on `PrivateChannel('admin-tickets')` or suppress public broadcast.
2. **Prevent Cross-Session Ticket Hijacking**: In `InternalTicketController.php`, validate that incoming `ticket_id` belongs to the supplied `session_id`. If mismatched, reject with 403 or fall back to the active session ticket.
3. **Reopen Resolved/Closed Tickets on Citizen Followup**: If a citizen followup message arrives for a ticket whose status is `resolved` or `closed`, transition status back to `open` (or `in_progress`), clearing `resolved_at` / `closed_at`.
4. **Eliminate N+1 Query Storm**: Remove `unread_messages_count` from `ChatTicket::$appends` and load it via subquery / `withCount` or compute it efficiently during `index()` to ensure constant query count regardless of pagination size.
5. **Fix Unread Count Reset on Staff Notes**: Filter `where('is_internal_note', false)` when computing the latest agent response in `unread_messages_count`.
6. **Validation Alignment**: Ensure `session_id` validation rule is `max:100` to match database column width.
7. **Test Database Isolation**: Add `force="true"` to `phpunit.xml` environment variables (`DB_CONNECTION`, `DB_DATABASE`) to ensure SQLite `:memory:` is strictly enforced during unit testing.
