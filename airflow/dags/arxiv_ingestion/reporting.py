import logging

logger = logging.getLogger(__name__)


def log_ingestion_stats(**context) -> None:
    """Pull results from upstream tasks and emit a single summary log line."""
    ti = context.get("ti")
    if ti is None:
        logger.info("log_ingestion_stats called outside Airflow context — nothing to report")
        return

    fetch_result = ti.xcom_pull(task_ids="fetch_papers") or {}
    index_result = ti.xcom_pull(task_ids="process_and_index") or {}

    inserted = fetch_result.get("inserted", "n/a")
    skipped = fetch_result.get("skipped", "n/a")
    processed = index_result.get("processed", "n/a")
    failed = index_result.get("failed", "n/a")

    logger.info(
        f"Ingestion run complete — "
        f"fetched: inserted={inserted}, skipped={skipped} | "
        f"indexed: processed={processed}, failed={failed}"
    )
