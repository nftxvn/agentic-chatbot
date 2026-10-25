"""One cancellation boundary for the registered document task entry points."""

from app.services import document_operations as operations


def run_guarded(document_id, operation_token, workflow, *args, **kwargs):
    """Discard obsolete work without retrying or interrupting other documents."""
    guard = operations.OperationGuard(document_id, operation_token)
    try:
        guard.checkpoint()
        return workflow(
            *args,
            operation_token=operation_token,
            operation_guard=guard,
            **kwargs,
        )
    except operations.DocumentOperationCancelled as error:
        return {"status": "dibatalkan", "pesan": str(error)}
