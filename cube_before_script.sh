#!/bin/bash
set -ev
cd ..
git clone https://github.com/FNNDSC/ChRIS_ultron_backEnd.git
pushd pfcon/
docker build -t fnndsc/pfcon:latest .
popd
pushd ChRIS_ultron_backEnd/
docker pull fnndsc/swarm
docker build -t fnndsc/chris:dev -f Dockerfile_dev .
docker swarm init --advertise-addr 127.0.0.1
chmod -R 755 $(pwd)
mkdir -p FS/local
mkdir -p FS/remote
mkdir -p FS/data
chmod -R 777 FS
export STOREBASE=$(pwd)/FS/remote
docker-compose -f docker-compose_dev.yml up -d
docker-compose -f docker-compose_dev.yml exec chris_dev_db sh -c 'while ! mysqladmin -uroot -prootp status 2> /dev/null; do sleep 5; done;'
docker-compose -f docker-compose_dev.yml exec chris_dev_db mysql -uroot -prootp -e 'GRANT ALL PRIVILEGES ON *.* TO "chris"@"%"'
