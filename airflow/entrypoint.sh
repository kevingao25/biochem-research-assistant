#!/bin/bash
set -e

echo "Writing admin password from AIRFLOW_ADMIN_PASSWORD..."
# Airflow 3.x simple_auth_manager stores passwords in this JSON file.
# Writing it before db migrate prevents Airflow from auto-generating a random password.
printf '{"admin": "%s"}\n' "${AIRFLOW_ADMIN_PASSWORD}" \
  > /opt/airflow/simple_auth_manager_passwords.json.generated

echo "Initializing Airflow database..."
airflow db migrate

echo "Starting Airflow API server..."
airflow api-server --port 8080 &

echo "Starting Airflow scheduler..."
exec airflow scheduler
