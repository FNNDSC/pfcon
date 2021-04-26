#!/bin/bash
#
# NAME
#
#   deploy.sh
#
# SYNPOSIS
#
#   deploy.sh                   [-O <swarm|kubernetes>] \
#                               [-S <storeBase>]        \
#                               [up|down]
#
# DESC
#
#   'deploy.sh' script will depending on the argument deploy the pfcon set
#    of services in production or tear down the system.
#
# TYPICAL CASES:
#
#   Run full pman instantiation:
#
#       deploy.sh up
#
# ARGS
#
#
#   -O <swarm|kubernetes>
#
#       Explicitly set the orchestrator. Default is swarm.
#
#   -S <storeBase>
#
#       Explicitly set the STOREBASE dir to <storeBase>. This is useful
#       mostly in non-Linux hosts (like macOS) where there might be a mismatch
#       between the actual STOREBASE path and the text of the path shared between
#       the macOS host and the docker VM.
#
#   [up|down] (optional, default = 'up')
#
#       Denotes whether to fire up or tear down the production set of services.
#
#


source ./decorate.sh
source ./cparse.sh

declare -i STEP=0
ORCHESTRATOR=swarm
HERE=$(pwd)
echo "Starting script in dir $HERE"

print_usage () {
    echo "Usage: ./deploy.sh [-S <storeBase>] [-O <swarm|kubernetes>] [up|down]"
    exit 1
}

while getopts ":S:O:" opt; do
    case $opt in
        S) b_storeBase=1
           STOREBASE=$OPTARG
           ;;
        O) ORCHESTRATOR=$OPTARG
           if ! [[ "$ORCHESTRATOR" =~ ^(swarm|kubernetes)$ ]]; then
              echo "Invalid value for option -- O"
              print_usage
           fi
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

COMMAND=up
if (( $# == 1 )) ; then
    COMMAND=$1
    if ! [[ "$COMMAND" =~ ^(up|down)$ ]]; then
        echo "Invalid value $COMMAND"
        print_usage
    fi
fi

title -d 1 "Setting global exports..."
    if (( ! b_storeBase )) ; then
        if [[ ! -d FS/remote ]] ; then
            mkdir -p FS/remote
        fi
        cd FS/remote
        STOREBASE=$(pwd)
        cd $HERE
    fi
    echo -e "exporting STOREBASE=$STOREBASE "                      | ./boxes.sh
    export STOREBASE=$STOREBASE
windowBottom

if [[ "$COMMAND" == 'up' ]]; then

    title -d 1 "Starting pfcon containerized prod environment on $ORCHESTRATOR"
    if [[ $ORCHESTRATOR == swarm ]]; then
        echo "docker stack deploy -c swarm/docker-compose_prod.yml pfcon_stack"         | ./boxes.sh ${LightCyan}
        docker stack deploy -c swarm/docker-compose_prod.yml pfcon_stack
    elif [[ $ORCHESTRATOR == kubernetes ]]; then
        echo "kubectl create configmap pman-config --from-env-file secrets/.pman.env"   | ./boxes.sh ${LightCyan}
        kubectl create configmap pman-config --from-env-file secrets/.pman.env
        echo "kubectl create configmap pfcon-config --from-env-file secrets/.pfcon.env" | ./boxes.sh ${LightCyan}
        kubectl create configmap pfcon-config --from-env-file secrets/.pfcon.env
        echo "envsubst < kubernetes/pfcon_prod.yaml | kubectl apply -f -"               | ./boxes.sh ${LightCyan}
        envsubst < kubernetes/pfcon_prod.yaml | kubectl apply -f -
    fi
    windowBottom
fi

if [[ "$COMMAND" == 'down' ]]; then

    title -d 1 "Destroying pfcon containerized prod environment on $ORCHESTRATOR"
    if [[ $ORCHESTRATOR == swarm ]]; then
        echo "docker stack rm pfcon_stack"                               | ./boxes.sh ${LightCyan}
        docker stack rm pfcon_stack
    elif [[ $ORCHESTRATOR == kubernetes ]]; then
        echo " kubectl delete configmaps pfcon-config pman-config"       | ./boxes.sh ${LightCyan}
        kubectl delete configmaps pfcon-config pman-config
        echo "kubectl delete -f kubernetes/pfcon_prod.yaml"              | ./boxes.sh ${LightCyan}
        kubectl delete -f kubernetes/pfcon_prod.yaml
    fi
    echo "Removing ./FS tree"                                            | ./boxes.sh
    rm -fr ./FS
    windowBottom
fi
