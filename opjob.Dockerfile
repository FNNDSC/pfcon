# Minimal image for async operation job containers (copy, upload, delete).
# Contains only the worker modules and their storage dependencies.

FROM docker.io/library/python:3.13-alpine

RUN pip install --no-cache-dir python-swiftclient

COPY pfcon/__init__.py /app/pfcon/__init__.py
COPY pfcon/copy_worker.py /app/pfcon/copy_worker.py
COPY pfcon/upload_worker.py /app/pfcon/upload_worker.py
COPY pfcon/delete_worker.py /app/pfcon/delete_worker.py
COPY pfcon/storage /app/pfcon/storage

WORKDIR /app
