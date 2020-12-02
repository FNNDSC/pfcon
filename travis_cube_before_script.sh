#!/bin/bash
set -ev
cd ..
git clone https://github.com/FNNDSC/ChRIS_ultron_backEnd.git
pushd pfcon/
docker build -t fnndsc/pfcon:latest .
popd
pushd ChRIS_ultron_backEnd/
docker pull fnndsc/pfdcm
docker build -t fnndsc/chris:dev -f Dockerfile_dev .
chmod -R 755 $(pwd)
mkdir -p FS/remote
chmod -R 777 FS
export STOREBASE=$(pwd)/FS/remote
docker-compose -f docker-compose_dev.yml up -d
docker-compose -f docker-compose_dev.yml exec chris_dev_db sh -c 'while ! mysqladmin -uroot -prootp status 2> /dev/null; do sleep 5; done;'
docker-compose -f docker-compose_dev.yml exec chris_dev_db mysql -uroot -prootp -e 'GRANT ALL PRIVILEGES ON *.* TO "chris"@"%"'
