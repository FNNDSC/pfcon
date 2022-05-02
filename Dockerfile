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

FROM fnndsc/conda:python3.10.4

LABEL org.opencontainers.image.authors="FNNDSC <dev@babyMRI.org>" \
      org.opencontainers.image.title="pfcon" \
      org.opencontainers.image.description="ChRIS compute resource controller" \
      org.opencontainers.image.url="https://chrisproject.org/" \
      org.opencontainers.image.source="https://github.com/FNNDSC/pfcon" \
      org.opencontainers.image.licenses="MIT"


WORKDIR /usr/local/src/pfcon
COPY ./requirements ./requirements
ENV PATH=/opt/conda/bin:$PATH
RUN conda env update -n base -f /usr/local/src/pfcon/requirements/env.yml
ARG ENVIRONMENT=production
RUN pip install --no-cache-dir -r /usr/local/src/pfcon/requirements/$ENVIRONMENT.txt
COPY . .
RUN if [ "$ENVIRONMENT" = "local" ]; then pip install -e .; else pip install .; fi

EXPOSE 5005
CMD ["gunicorn", "--bind", "0.0.0.0:5005", "--workers", "8", "--timeout", "3600", "pfcon.wsgi:application"]
