# Dockerfile for multi-arch "production" images.
# Before building this image, the conda environment and pfcon wheel must be built on-the-metal.

FROM docker.io/library/debian:bookworm-slim

ARG TARGETPLATFORM
COPY ./envs/${TARGETPLATFORM} /opt/conda-env
ENV PATH=/opt/conda-env/bin:$PATH

RUN --mount=type=bind,source=./dist,target=/dist pip install --no-deps --no-cache-dir /dist/pfcon-*.whl

CMD ["gunicorn", "--bind", "0.0.0.0:5005", "--workers", "8", "--timeout", "3600", "pfcon.wsgi:application"]

