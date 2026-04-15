FROM python:3.12-slim

ENV AIRFLOW_HOME=/opt/airflow
ENV AIRFLOW_VERSION=3.2.0
ENV PYTHON_VERSION=3.12
ENV CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

# System dependencies
# - build-essential: needed to compile some Python packages
# - libpq-dev: PostgreSQL client library (required by psycopg2)
# - curl: used in healthchecks
# - poppler-utils + tesseract-ocr: PDF text extraction (used later for paper processing)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq-dev \
        poppler-utils \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for Airflow
# Running as root inside containers is a security risk
RUN groupadd -r -g 50000 airflow && \
    useradd -r -u 50000 -g airflow -d ${AIRFLOW_HOME} -s /bin/bash airflow

# Create directories Airflow needs and set ownership
RUN mkdir -p ${AIRFLOW_HOME}/dags ${AIRFLOW_HOME}/logs ${AIRFLOW_HOME}/plugins && \
    chown -R 50000:50000 ${AIRFLOW_HOME}

# Install Airflow with PostgreSQL support
# The constraint file pins all transitive dependencies to known-compatible versions
# Without it, pip might install incompatible package combinations
RUN pip install --no-cache-dir \
    "apache-airflow[postgres]==${AIRFLOW_VERSION}" \
    --constraint "${CONSTRAINT_URL}"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER airflow
WORKDIR ${AIRFLOW_HOME}

EXPOSE 8080

CMD ["/entrypoint.sh"]
