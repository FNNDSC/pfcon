FROM ghcr.io/prefix-dev/pixi:0.55.0 AS install

COPY . /app
WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/rattler/cache,sharing=private pixi install

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

ARG ENVIRONMENT=prod
COPY --from=build /app/.pixi/envs/${ENVIRONMENT} /app/.pixi/envs/${ENVIRONMENT}
COPY --from=build /entrypoint.sh /entrypoint.sh

ENTRYPOINT [ "/entrypoint.sh" ]
CMD ["gunicorn", "--bind", "0.0.0.0:5005", "--workers", "8", "--timeout", "3600", "pfcon.wsgi:application"]

EXPOSE 5005
