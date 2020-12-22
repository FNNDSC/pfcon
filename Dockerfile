#
# Dockerfile for pfcon production.
#
# Build with
#
#   docker build -t <name> .
#
# For example if building a local version, you could do:
#
#   docker build -t local/pfcon .
#
# In the case of a proxy (located at say 10.41.13.4:3128), do:
#
#    export PROXY="http://10.41.13.4:3128"
#    docker build --build-arg http_proxy=${PROXY} --build-arg UID=$UID -t local/pfcon .
#
# To run an interactive shell inside this container, do:
#
#   docker run -ti --rm --entrypoint /bin/bash local/pfcon
#
# To pass an env var HOST_IP to container, do:
#
#   docker run -ti --rm -e HOST_IP=$(ip route | grep -v docker | awk '{if(NF==11) print $9}') --entrypoint /bin/bash local/pfcon
#

FROM python:3.8.6-buster AS build
  LABEL version="3.0.0.0" maintainer="FNNDSC <dev@babyMRI.org>"

  # Pass a UID on build command line (see above) to set internal UID
  ARG UID=1001
  ENV UID=$UID DEBIAN_FRONTEND=noninteractive APPROOT="/home/localuser/pfcon"

  RUN apt-get update                                                                              \
    && apt-get install -y --no-install-recommends libssl-dev libcurl4-openssl-dev bsdmainutils    \
       net-tools inetutils-ping locales                                                           \
    && export LANGUAGE=en_US.UTF-8                                                                \
    && export LANG=en_US.UTF-8                                                                    \
    && export LC_ALL=en_US.UTF-8                                                                  \
    && locale-gen en_US.UTF-8                                                                     \
    && dpkg-reconfigure locales                                                                   \
    && useradd -u $UID -ms /bin/bash localuser                                                    \
    && pip3 install --upgrade pip pytest                

  # Copy source code
  COPY --chown=localuser ./setup.py README.rst ./requirements.txt ${APPROOT}/
  RUN pip3 install -r ${APPROOT}/requirements.txt

  COPY --chown=localuser ./bin ${APPROOT}/bin
  COPY --chown=localuser ./pfcon ${APPROOT}/pfcon

  RUN pip3 install --no-dependencies ${APPROOT}  

FROM build as tests

  RUN pytest ${APPROOT}/pfcon/tests/*.py
  RUN rm -fr ${APPROOT}

FROM build as runtime

  WORKDIR "/home/localuser"
  ENTRYPOINT ["pfcon"]
  EXPOSE 5005
