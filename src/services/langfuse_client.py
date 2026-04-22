import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, Optional

from langfuse import Langfuse

logger = logging.getLogger(__name__)


class LangfuseClient:
    """Wrapper around the Langfuse SDK for tracing RAG pipeline steps.

    If LANGFUSE_PUBLIC_KEY / SECRET_KEY are missing, all methods become
    silent no-ops so tracing failures never affect real requests.
    """

    def __init__(self):
        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
        base_url = os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

        self.client: Optional[Langfuse] = None

        if public_key and secret_key:
            try:
                self.client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    base_url=base_url,
                )
                logger.info("Langfuse tracing enabled")
            except Exception as e:
                logger.warning(f"Langfuse initialization failed, tracing disabled: {e}")
        else:
            logger.info("Langfuse keys not set, tracing disabled")

    @contextmanager
    def trace(self, query: str):
        """Root context manager for a full /ask request."""
        if not self.client:
            yield None
            return

        try:
            with self.client.start_as_current_observation(
                name="rag_request",
                input={"query": query},
            ) as root:
                yield root
            self.client.flush()
        except Exception as e:
            logger.warning(f"Langfuse trace failed: {e}")
            yield None

    @contextmanager
    def span(self, parent, name: str, input_data: Optional[Dict[str, Any]] = None):
        """Child span inside a trace. Yields None if tracing is disabled.

        Only the span initialization is wrapped in try/except. If the caller's
        code raises, the exception propagates normally — we never swallow real errors.
        """
        if not self.client or parent is None:
            yield None
            return

        try:
            obs = parent.start_as_current_observation(name=name, input=input_data or {})
        except Exception as e:
            logger.warning(f"Langfuse span '{name}' failed to start: {e}")
            yield None
            return

        with obs as s:
            yield s

    def shutdown(self):
        """Flush and close the client on app shutdown."""
        if self.client:
            try:
                self.client.flush()
                self.client.shutdown()
            except Exception:
                pass
