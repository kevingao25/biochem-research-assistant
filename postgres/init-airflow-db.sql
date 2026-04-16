-- Airflow needs its own database for metadata (DAG runs, task state, etc.)
-- This runs once when the Postgres container is first created.
CREATE DATABASE airflow;
