from unittest.mock import MagicMock

from src.services.langfuse.client import LangfuseTracer


def test_submit_feedback_creates_numeric_score():
    tracer = object.__new__(LangfuseTracer)
    tracer.client = MagicMock()

    assert tracer.submit_feedback(trace_id="trace-123", score=1.0, comment="Helpful") is True

    tracer.client.create_score.assert_called_once_with(
        name="user-feedback",
        value=1.0,
        trace_id="trace-123",
        score_id="trace-123-user-feedback",
        data_type="NUMERIC",
        comment="Helpful",
    )
    tracer.client.flush.assert_called_once()


def test_submit_feedback_returns_false_without_client():
    tracer = object.__new__(LangfuseTracer)
    tracer.client = None

    assert tracer.submit_feedback(trace_id="trace-123", score=1.0) is False
