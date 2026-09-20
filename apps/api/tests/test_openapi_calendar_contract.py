"""Regression coverage for the public Calendar API contract."""

from app.main import app


def test_calendar_operation_ids_are_unique():
    """Calendar must be registered once so generated clients remain reliable."""
    paths = app.openapi()["paths"]
    operation_ids = [
        operation["operationId"]
        for path, methods in paths.items()
        if path.startswith("/api/v1/calendar/")
        for operation in methods.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]

    assert operation_ids
    assert len(operation_ids) == len(set(operation_ids))
