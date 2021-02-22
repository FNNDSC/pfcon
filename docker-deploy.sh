#!/bin/bash

G_SYNOPSIS="

 NAME

	docker-deploy.sh

 SYNOPSIS

	docker-deploy.sh [up|down]

 ARGS

	[up|down]
	Denotes whether to fire up or tear down the production set of services.

 DESCRIPTION

	docker-deploy.sh script will depending on the argument deploy the pfcon set
    of services in production or tear down the system.

"

if [[ "$#" -eq 0 ]] || [[ "$#" -gt 1 ]]; then
    echo "$G_SYNOPSIS"
    exit 1
fi

source ./decorate.sh

declare -i STEP=0


if [[ "$1" == 'up' ]]; then

    title -d 1 "Stopping and restarting docker swarm cluster... "
    docker swarm leave --force
    docker swarm init --advertise-addr 127.0.0.1
    windowBottom

    title -d 1 "Checking required FS directory tree for remote services in host filesystem..."
    mkdir -p FS/remote
    chmod -R 777 FS
    export STOREBASE=$(pwd)/FS/remote
    windowBottom

    title -d 1 "Starting containerized production environment using " " ./docker-compose.yml"
    declare -a A_CONTAINER=(
    "fnndsc/pfcon"
    "fnndsc/pfioh"
    "fnndsc/pman"
    )
    echo "Pulling latest version of all service containers..."
    for CONTAINER in ${A_CONTAINER[@]} ; do
        echo ""
        CMD="docker pull $CONTAINER"
        echo -e "\t\t\t${White}$CMD${NC}"
        echo $sep
        echo $CMD | sh
        echo $sep
    done
    echo "docker-compose up -d"
    docker-compose up -d
    windowBottom
fi

if [[ "$1" == 'down' ]]; then

    export STOREBASE=${STOREBASE}

    title -d 1 "Destroying containerized production environment" "from ./docker-compose.yml"
    docker-compose --no-ansi down >& dc.out >/dev/null
    cat dc.out                                                              | ./boxes.sh
    echo "Removing ./FS tree"                                               | ./boxes.sh
    rm -fr ./FS
    windowBottom

    title -d 1 "Stopping swarm cluster..."
    docker swarm leave --force
    windowBottom
fi
