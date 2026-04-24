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
        try:
            trace = self.client.trace(
                name="rag_request",
                input={"query": query},
                metadata=metadata or {},
                user_id=user_id,
                session_id=session_id,
            )
            yield trace
        except Exception as e:
            logger.error(f"Error creating Langfuse trace: {e}")
            yield None

    def create_span(self, trace, name: str, input_data: dict[str, Any] | None = None):
        if not trace or not self.client:
            return None
        try:
            return self.client.span(trace_id=trace.trace_id, name=name, input=input_data)
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

    def shutdown(self):
        if self.client:
            try:
                self.client.flush()
                self.client.shutdown()
            except Exception as e:
                logger.error(f"Langfuse shutdown error: {e}")
