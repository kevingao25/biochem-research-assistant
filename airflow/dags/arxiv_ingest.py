import pendulum
from arxiv_ingestion.fetching import fetch_papers
from arxiv_ingestion.indexing import process_and_index_papers
from arxiv_ingestion.reporting import log_ingestion_stats

from airflow.sdk import dag, task


@dag(
    dag_id="arxiv_ingest",
    description="Daily pipeline: fetch q-bio papers → store in PostgreSQL → parse PDFs → index chunks in Qdrant",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    schedule="0 6 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["arxiv", "biochem", "ingestion"],
)
def arxiv_ingest():

    @task
    def fetch_and_store(ds: str | None = None):
        return fetch_papers(ds=ds)

    @task
    def index_papers():
        return process_and_index_papers()

    @task
    def report(**context):
        log_ingestion_stats(**context)

    t1 = fetch_and_store()
    t2 = index_papers()
    t3 = report()
    t1 >> t2 >> t3


arxiv_ingest()
