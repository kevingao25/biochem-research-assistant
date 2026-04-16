#!/bin/bash
set -e

echo "Initializing Airflow database..."
airflow db migrate

echo "Starting Airflow API server..."
airflow api-server --port 8080 &

echo "Starting Airflow scheduler..."
exec airflow scheduler
