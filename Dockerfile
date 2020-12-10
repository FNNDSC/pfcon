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

FROM fnndsc/ubuntu-python3:latest
MAINTAINER fnndsc "dev@babymri.org"

# Pass a UID on build command line (see above) to set internal UID
ARG UID=1001
ENV UID=$UID DEBIAN_FRONTEND=noninteractive APPLICATION_MODE="production" APPROOT="/home/localuser/pfcon"

RUN apt-get update                                                                              \
  && apt-get install -y libssl-dev libcurl4-openssl-dev bsdmainutils net-tools inetutils-ping   \
  && apt-get install -y locales                                                                 \
  && export LANGUAGE=en_US.UTF-8                                                                \
  && export LANG=en_US.UTF-8                                                                    \
  && export LC_ALL=en_US.UTF-8                                                                  \
  && locale-gen en_US.UTF-8                                                                     \
  && dpkg-reconfigure locales                                                                   \
  && apt-get install -y apache2 apache2-dev                                                     \
  && pip install --upgrade pip                                                                  \
  && useradd -u $UID -ms /bin/bash localuser

# Copy source code and make localuser the owner
COPY --chown=localuser ./bin ${APPROOT}/bin
COPY --chown=localuser ./pfcon ${APPROOT}/pfcon
COPY --chown=localuser ./setup.cfg ./setup.py README.rst  ${APPROOT}/

RUN pip3 install ${APPROOT}

# Start as user localuser
USER localuser

WORKDIR ${APPROOT}
ENTRYPOINT ["mod_wsgi-express"]
EXPOSE 5005

# Start pfon production server
CMD ["start-server", "pfcon/wsgi.py", "--host", "0.0.0.0", "--port", "5005", "--processes", "8", "--limit-request-body", "10632560640", "--server-root", "/home/localuser/mod_wsgi-0.0.0.0:5005"]
#mod_wsgi-express setup-server config/wsgi.py --host 0.0.0.0 --port 5005 --processes 8 --server-name localhost --server-root /home/localuser/mod_wsgi-0.0.0.0:5005
#to start daemon:
#/home/localuser/mod_wsgi-0.0.0.0:5005/apachectl start
#to stop deamon
#/home/localuser/mod_wsgi-0.0.0.0:5005/apachectl stop
