# Minimal image for async operation job containers (copy, upload, delete).
# Contains only the worker modules and their storage dependencies.

FROM docker.io/library/python:3.13-alpine

ARG STORAGE_ENV
RUN if [ "$STORAGE_ENV" = "swift" ]; then \
      pip install --no-cache-dir python-swiftclient; \
    fi

COPY pfcon/__init__.py /app/pfcon/__init__.py
COPY pfcon/copy_worker.py /app/pfcon/copy_worker.py
COPY pfcon/upload_worker.py /app/pfcon/upload_worker.py
COPY pfcon/delete_worker.py /app/pfcon/delete_worker.py
COPY pfcon/storage /app/pfcon/storage

WORKDIR /app
