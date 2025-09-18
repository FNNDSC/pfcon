#!/bin/bash
#
# NAME
#
#   unmake.sh
#
# SYNPOSIS
#
#   unmake.sh                     [-h] [-N] \
#                                 [-F <swift|filesystem|fslink|zipfile>]   \
#                                 [-O <docker|swarm|kubernetes>]  \
#                                 [-S <storeBase>]
#
#
# DESC
#
#   'unmake.sh' destroys a pfcon development instance running on Docker, Swarm or Kubernetes.
#
# TYPICAL CASES:
#
#   Destroy pfcon dev instance on Docker:
#
#       unmake.sh
#
#   Destroy pfcon dev instance operating in-network on Docker using Swift storage:
#
#       unmake.sh -N -F swift
#
#   Destroy pfcon dev instance operating in-network on Docker using mounted filesystem
#   with ChRIS links storage:
#
#       unmake.sh -N -F fslink
#
#   Destroy pfcon dev instance operating in-network on Docker using mounted filesystem storage:
#
#       unmake.sh -N -F filesystem
#
#   Destroy pfcon dev instance on Swarm:
#
#       unmake.sh -O swarm
#
#   Destroy pfcon dev instance on Kubernetes:
#
#       unmake.sh -O kubernetes
#
# ARGS
#
#
#   -h
#
#   -N
#
#       Explicitly set pfcon to operate in-network mode (using a swift storage instead of
#       a zip file).
#
#       Optional print usage help.
#
#   -F <swift|filesystem|fslink|zipfile>
#
#       Explicitly set the storage environment. This option must be swift, filesystem of
#       fslink for pfcon operating in-network mode. For pfcon operating in out-of-network
#       mode it must be set to zipfile (default).
#
#   -O <docker|swarm|kubernetes>
#
#       Explicitly set the orchestrator. Default is docker.
#
#   -S <storeBase>
#
#       Explicitly set the STOREBASE dir to <storeBase>. This is the remote ChRIS
#       filesystem where pfcon and plugins share data.
#
#

source ./decorate.sh

declare -i STEP=0
CONTAINER_ENV=docker
STORAGE_ENV=zipfile

print_usage () {
    echo "Usage: ./unmake.sh [-h] [-N] [-F <swift|filesystem|fslink|zipfile>] [-O <docker|swarm|kubernetes>] [-S <storeBase>]"
    exit 1
}

while getopts ":hNF:O:S:" opt; do
    case $opt in
        h) print_usage
           ;;
        N) b_pfconInNetwork=1
          ;;
        F) STORAGE_ENV=$OPTARG
           if ! [[ "$STORAGE_ENV" =~ ^(swift|filesystem|fslink|zipfile)$ ]]; then
              echo "Invalid value for option -- F"
              print_usage
           fi
           ;;
        O) CONTAINER_ENV=$OPTARG
           if ! [[ "$CONTAINER_ENV" =~ ^(docker|swarm|kubernetes)$ ]]; then
              echo "Invalid value for option -- O"
              print_usage
           fi
           ;;
        S) STOREBASE=$OPTARG
           ;;
        \?) echo "Invalid option -- $OPTARG"
            print_usage
            ;;
        :) echo "Option requires an argument -- $OPTARG"
           print_usage
           ;;
    esac
done
shift $(($OPTIND - 1))

title -d 1 "Setting global exports..."
    if [ -z ${STOREBASE+x} ]; then
        STOREBASE=$(pwd)/CHRIS_REMOTE_FS
    fi
    if (( b_pfconInNetwork )) ; then
        echo -e "PFCON_INNETWORK=True"                             | ./boxes.sh
        if [[ $STORAGE_ENV == 'zipfile' ]]; then
            echo -e "Need to pass '-F <swift|filesystem|fslink|>' when PFCON_INNETWORK=True"  | ./boxes.sh
            exit 1
        fi
    else
        echo -e "PFCON_INNETWORK=False"                            | ./boxes.sh
    fi
    echo -e "exporting CONTAINER_ENV=$CONTAINER_ENV "               | ./boxes.sh
    export CONTAINER_ENV=$CONTAINER_ENV
    echo -e "exporting STORAGE_ENV=$STORAGE_ENV "               | ./boxes.sh
    export STORAGE_ENV=$STORAGE_ENV
    echo -e "exporting STOREBASE=$STOREBASE "           | ./boxes.sh
    export STOREBASE=$STOREBASE
    export SOURCEDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
    echo -e "exporting SOURCEDIR=$SOURCEDIR "                           | ./boxes.sh
windowBottom

title -d 1 "Destroying pfcon containerized dev environment on $CONTAINER_ENV"
    if [[ $CONTAINER_ENV == docker ]]; then
        if (( b_pfconInNetwork )) ; then
            if [[ $STORAGE_ENV == 'swift' ]]; then
                echo "docker compose -f swarm/docker-compose_dev_innetwork.yml down -v" | ./boxes.sh ${LightCyan}
                docker compose -f swarm/docker-compose_dev_innetwork.yml down -v
            elif [[ "$STORAGE_ENV" =~ ^(filesystem|fslink)$ ]]; then
                echo "docker compose -f swarm/docker-compose_dev_innetwork_fs.yml down -v" | ./boxes.sh ${LightCyan}
                docker compose -f swarm/docker-compose_dev_innetwork_fs.yml down -v
            fi
        else
            echo "docker compose -f swarm/docker-compose_dev.yml down -v" | ./boxes.sh ${LightCyan}
            docker compose -f swarm/docker-compose_dev.yml down -v
        fi
    elif [[ $CONTAINER_ENV == swarm ]]; then
        echo "docker stack rm pfcon_dev_stack"                               | ./boxes.sh ${LightCyan}
        docker stack rm pfcon_dev_stack
        if (( b_pfconInNetwork )) ; then
            if [[ $STORAGE_ENV == 'swift' ]]; then
                echo "docker volume rm -f pfcon_dev_stack_swift_storage_dev"
                sleep 15
                docker volume rm pfcon_dev_stack_swift_storage_dev
            fi
        fi
    elif [[ $CONTAINER_ENV == kubernetes ]]; then
        if (( b_pfconInNetwork )) ; then
            if [[ $STORAGE_ENV == 'swift' ]]; then
                echo "kubectl delete -f kubernetes/pfcon_dev_innetwork.yaml"     | ./boxes.sh ${LightCyan}
                kubectl delete -f kubernetes/pfcon_dev_innetwork.yaml
                echo "Removing swift_storage folder $SOURCEDIR/swift_storage"  | ./boxes.sh
                rm -fr $SOURCEDIR/swift_storage
            else
                echo "kubectl delete -f kubernetes/pfcon_dev_innetwork_fs.yaml"     |  ./boxes.sh ${LightCyan}
                kubectl delete -f kubernetes/pfcon_dev_innetwork_fs.yaml
            fi
        else
            echo "kubectl delete -f kubernetes/pfcon_dev.yaml"               | ./boxes.sh ${LightCyan}
            kubectl delete -f kubernetes/pfcon_dev.yaml
        fi
    fi
    echo "Removing STOREBASE tree $STOREBASE"                                | ./boxes.sh
    rm -fr $STOREBASE
windowBottom
