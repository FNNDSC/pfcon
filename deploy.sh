#!/bin/bash
#
# NAME
#
#   deploy.sh
#
# SYNPOSIS
#
#   deploy.sh                   [-h]
#                               [-O <swarm|kubernetes>] \
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
#   Deploy pfcon services into a Swarm cluster:
#
#       deploy.sh up
#
#
#   Deploy pfcon services into a Kubernetes cluster:
#
#       deploy.sh -O kubernetes up
#
# ARGS
#
#
#   -h
#
#       Optional print usage help.
#
#   -O <swarm|kubernetes>
#
#       Explicitly set the orchestrator. Default is swarm.
#
#   -S <storeBase>
#
#       Explicitly set the STOREBASE dir to <storeBase>. This is the remote ChRIS
#       filesystem where pfcon and plugins share data (usually externally mounted NFS).
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

print_usage () {
    echo "Usage: ./deploy.sh [-h] [-O <swarm|kubernetes>] [-S <storeBase>] [up|down]"
    exit 1
}

while getopts ":hO:S:" opt; do
    case $opt in
        h) print_usage
           ;;
        O) ORCHESTRATOR=$OPTARG
           if ! [[ "$ORCHESTRATOR" =~ ^(swarm|kubernetes)$ ]]; then
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

COMMAND=up
if (( $# == 1 )) ; then
    COMMAND=$1
    if ! [[ "$COMMAND" =~ ^(up|down)$ ]]; then
        echo "Invalid value $COMMAND"
        print_usage
    fi
fi

title -d 1 "Setting global exports..."
    if [ -z ${STOREBASE+x} ]; then
        if [[ ! -d CHRIS_REMOTE_FS ]] ; then
            mkdir CHRIS_REMOTE_FS
        fi
        STOREBASE=$HERE/CHRIS_REMOTE_FS
    else
        if [[ ! -d $STOREBASE ]] ; then
            mkdir -p $STOREBASE
        fi
    fi
    echo -e "exporting STOREBASE=$STOREBASE "                      | ./boxes.sh
    export STOREBASE=$STOREBASE
windowBottom

if [[ "$COMMAND" == 'up' ]]; then

    title -d 1 "Starting pfcon containerized prod environment on $ORCHESTRATOR"
    if [[ $ORCHESTRATOR == swarm ]]; then
        echo "docker stack deploy -c swarm/docker-compose_prod.yml pfcon_stack"           | ./boxes.sh ${LightCyan}
        docker stack deploy -c swarm/docker-compose_prod.yml pfcon_stack
    elif [[ $ORCHESTRATOR == kubernetes ]]; then
        echo "kubectl create namespace chris"   | ./boxes.sh ${LightCyan}
        kubectl create namespace chris
        echo "kubectl create configmap pman-config" "--from-env-file secrets/.pman.env"   | ./boxes.sh ${LightCyan}
        kubectl create configmap pman-config --from-env-file secrets/.pman.env --namespace chris
        echo "kubectl create configmap pfcon-config" "--from-env-file secrets/.pfcon.env" | ./boxes.sh ${LightCyan}
        kubectl create configmap pfcon-config --from-env-file secrets/.pfcon.env --namespace chris
        echo "envsubst < kubernetes/pfcon_prod.yaml | kubectl apply -f -"                 | ./boxes.sh ${LightCyan}
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
        echo " kubectl delete configmaps pfcon-config pman-config --namespace chris"  | ./boxes.sh ${LightCyan}
        kubectl delete configmaps pfcon-config pman-config --namespace chris
        echo "kubectl delete -f kubernetes/pfcon_prod.yaml"              | ./boxes.sh ${LightCyan}
        kubectl delete -f kubernetes/pfcon_prod.yaml
        echo "kubectl delete namespace chris"   | ./boxes.sh ${LightCyan}
        kubectl delete namespace chris
    fi
    echo "Removing STOREBASE tree $STOREBASE"                            | ./boxes.sh
    rm -fr $STOREBASE
    windowBottom
fi
