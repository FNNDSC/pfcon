FROM fnndsc/ubuntu-python3:ubuntu20.04-python3.8.5
LABEL version="2.3.1" maintainer="FNNDSC <dev@babyMRI.org>"

# pfurl dependencies
RUN apt-get update                                                                              \
  && apt-get install -y --no-install-recommends libssl-dev libcurl4-openssl-dev bsdmainutils    \
      net-tools inetutils-ping locales                                                          \
  && export LANGUAGE=en_US.UTF-8                                                                \
  && export LANG=en_US.UTF-8                                                                    \
  && export LC_ALL=en_US.UTF-8                                                                  \
  && locale-gen en_US.UTF-8                                                                     \
  && dpkg-reconfigure locales

WORKDIR /usr/local/src
COPY requirements.txt .
RUN ["pip", "install", "-r", "requirements.txt"]
COPY . .
RUN ["pip", "install",  "."]

ENTRYPOINT ["pfcon"]
CMD ["--forever", "--httpResponse"]
EXPOSE 5005
