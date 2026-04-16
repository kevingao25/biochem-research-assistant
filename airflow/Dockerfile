FROM apache/airflow:3.2.0

USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
       poppler-utils \
       tesseract-ocr \
  && apt-get autoremove -yqq --purge \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

USER airflow
COPY --chmod=755 entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
