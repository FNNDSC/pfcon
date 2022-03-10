#
# Docker file for pfcon image
#
# Build production image:
#
#   docker build -t <name> .
#
# For example if building a local production image:
#
#   docker build -t local/pfcon .
#
# Build development image:
#
#   docker build --build-arg ENVIRONMENT=local -t <name>:<tag> .
#
# For example if building a local development image:
#
#   docker build --build-arg ENVIRONMENT=local -t local/pfcon:dev .
#
# In the case of a proxy (located at say proxy.tch.harvard.edu:3128), do:
#
#    export PROXY="http://proxy.tch.harvard.edu:3128"
#
# then add to any of the previous build commands:
#
#    --build-arg http_proxy=${PROXY}
#
# For example if building a local development image:
#
# docker build --build-arg http_proxy=${PROXY} --build-arg ENVIRONMENT=local -t local/pfcon:dev .
#

FROM docker.io/library/python:3.8.12-slim-bullseye

LABEL org.opencontainers.image.authors="FNNDSC <dev@babyMRI.org>" \
      org.opencontainers.image.title="pfcon" \
      org.opencontainers.image.description="ChRIS compute resource controller" \
      org.opencontainers.image.url="https://chrisproject.org/" \
      org.opencontainers.image.source="https://github.com/FNNDSC/pfcon" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /usr/local/src/pfcon
COPY ./requirements ./requirements
ARG ENVIRONMENT=production
RUN pip install --no-cache-dir -r /usr/local/src/pfcon/requirements/$ENVIRONMENT.txt

COPY . .
RUN if [ "$ENVIRONMENT" = "local" ]; then pip install -e .; else  pip install .; fi

# Start pfcon production server
EXPOSE 5005
CMD ["gunicorn", "-w", "5", "-b", "0.0.0.0:5005", "-t",  "200", "pfcon.wsgi:application"]
