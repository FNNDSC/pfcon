FROM ghcr.io/prefix-dev/pixi:0.27.1 AS install

COPY . /app
WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/rattler/cache,sharing=locked pixi install

# development stage
FROM install AS dev

CMD ["pixi", "run", "python", "-m", "pfcon"]
EXPOSE 5005

# production build stage
FROM install AS build

RUN pixi run build

ARG ENVIRONMENT=prod
RUN printf '#!/bin/sh\n%s\nexec "$@"' "$(pixi shell-hook -e ${ENVIRONMENT})" > /entrypoint.sh
RUN chmod +x /entrypoint.sh
# must be the last command of this stage, or else pixi will overwrite the installed package.
RUN pixi run postinstall-production

# production minimal image
FROM docker.io/library/debian:bookworm-slim

COPY --from=build /app/.pixi/envs/${ENVIRONMENT} /app/.pixi/envs/${ENVIRONMENT}
COPY --from=build /entrypoint.sh /entrypoint.sh

ENTRYPOINT [ "/entrypoint.sh" ]
CMD ["gunicorn", "--bind", "0.0.0.0:5005", "--workers", "8", "--timeout", "3600", "pfcon.wsgi:application"]

EXPOSE 5005

LABEL org.opencontainers.image.authors="FNNDSC <dev@babyMRI.org>" \
      org.opencontainers.image.title="pfcon" \
      org.opencontainers.image.description="ChRIS compute resource controller" \
      org.opencontainers.image.url="https://chrisproject.org/" \
      org.opencontainers.image.source="https://github.com/FNNDSC/pfcon" \
      org.opencontainers.image.licenses="MIT"
