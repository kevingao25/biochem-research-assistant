#!/bin/bash
set -e

echo "Initializing Airflow database..."
airflow db migrate

# Airflow 3.x SimpleAuthManager creates an admin user automatically.
# Credentials are written to: $AIRFLOW_HOME/simple_auth_manager_passwords.json.generated
# You can also set a password via the AIRFLOW_ADMIN_PASSWORD env var.
echo "Setting up admin credentials..."
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password "${AIRFLOW_ADMIN_PASSWORD:-admin}" 2>/dev/null || echo "Admin user already exists"

echo "Starting Airflow webserver..."
airflow webserver --port 8080 --daemon &

echo "Starting Airflow scheduler..."
exec airflow scheduler
