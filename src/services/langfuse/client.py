import logging
from contextlib import contextmanager
from typing import Any

from langfuse import Langfuse

from src.config import Settings

logger = logging.getLogger(__name__)


class LangfuseTracer:
    def __init__(self, settings: Settings):
        self.settings = settings.langfuse
        self.client: Langfuse | None = None

        if self.settings.enabled and self.settings.public_key and self.settings.secret_key:
            try:
                self.client = Langfuse(
                    public_key=self.settings.public_key,
                    secret_key=self.settings.secret_key,
                    host=self.settings.host,
                    flush_at=self.settings.flush_at,
                    flush_interval=self.settings.flush_interval,
                    debug=self.settings.debug,
                )
                logger.info(f"Langfuse tracing initialized (host: {self.settings.host})")
            except Exception as e:
                logger.error(f"Failed to initialize Langfuse: {e}")
        else:
            logger.info("Langfuse tracing disabled or missing credentials")

    @contextmanager
    def trace_rag_request(
        self,
        query: str,
        user_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        if not self.client:
            yield None
            return
        trace_metadata = dict(metadata or {})
        if user_id:
            trace_metadata["user_id"] = user_id
        if session_id:
            trace_metadata["session_id"] = session_id
        try:
            trace_context = self.client.start_as_current_observation(
                name="rag_request",
                as_type="span",
                input={"query": query},
                metadata=trace_metadata,
            )
        except Exception as e:
            logger.error(f"Error creating Langfuse trace: {e}")
            yield None
            return

        with trace_context as trace:
            yield trace

    def create_span(self, trace, name: str, input_data: dict[str, Any] | None = None):
        if not trace or not self.client:
            return None
        try:
            return trace.start_observation(name=name, as_type="span", input=input_data)
        except Exception as e:
            logger.error(f"Error creating span {name}: {e}")
            return None

    def update_span(self, span, output: Any | None = None, metadata: dict[str, Any] | None = None):
        if not span:
            return
        try:
            if output is not None:
                span.update(output=output)
            if metadata:
                span.update(metadata=metadata)
        except Exception as e:
            logger.error(f"Error updating span: {e}")

    def flush(self):
        if self.client:
            try:
                self.client.flush()
            except Exception as e:
                logger.error(f"Langfuse flush error: {e}")

    def get_trace_id(self, trace=None) -> str | None:
        if not self.client:
            return None
        try:
            trace_id = self.client.get_current_trace_id()
            if trace_id:
                return trace_id
        except Exception as e:
            logger.debug(f"Could not read current Langfuse trace id: {e}")

        for attr in ("trace_id", "id"):
            value = getattr(trace, attr, None)
            if isinstance(value, str):
                return value
        return None

    def submit_feedback(self, trace_id: str, score: float, comment: str | None = None) -> bool:
        if not self.client:
            logger.warning("Cannot submit feedback: Langfuse is disabled")
            return False
        try:
            self.client.create_score(
                name="user-feedback",
                value=float(score),
                trace_id=trace_id,
                score_id=f"{trace_id}-user-feedback",
                data_type="NUMERIC",
                comment=comment,
            )
            self.flush()
            return True
        except Exception as e:
            logger.error(f"Langfuse feedback error: {e}")
            return False

    def shutdown(self):
        if self.client:
            try:
                self.client.flush()
                self.client.shutdown()
            except Exception as e:
                logger.error(f"Langfuse shutdown error: {e}")
