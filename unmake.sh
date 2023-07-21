#!/bin/bash
#
# NAME
#
#   unmake.sh
#
# SYNPOSIS
#
#   unmake.sh                     [-h] [-N]
#                                 [-O <swarm|kubernetes>]
#                                 [-S <storeBase>]
#
#
# DESC
#
#   'unmake.sh' destroys a pfcon development instance running on Swarm or Kubernetes.
#
# TYPICAL CASES:
#
#   Destroy pfcon dev instance on Swarm:
#
#       unmake.sh
#
#   Destroy pfcon dev instance operating in-network on Swarm:
#
#       unmake.sh -N
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
#   -O <swarm|kubernetes>
#
#       Explicitly set the orchestrator. Default is swarm.
#
#   -S <storeBase>
#
#       Explicitly set the STOREBASE dir to <storeBase>. This is the remote ChRIS
#       filesystem where pfcon and plugins share data.
#
#

source ./decorate.sh

declare -i STEP=0
ORCHESTRATOR=swarm

print_usage () {
    echo "Usage: ./unmake.sh [-h] [-N] [-O <swarm|kubernetes>] [-S <storeBase>]"
    exit 1
}

while getopts ":hNO:S:" opt; do
    case $opt in
        h) print_usage
           ;;
        N) b_pfconInNetwork=1
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

title -d 1 "Setting global exports..."
    if [ -z ${STOREBASE+x} ]; then
        STOREBASE=$(pwd)/CHRIS_REMOTE_FS
    fi
    if (( b_pfconInNetwork )) ; then
        echo -e "PFCON_INNETWORK=True"                             | ./boxes.sh
    else
        echo -e "PFCON_INNETWORK=False"                            | ./boxes.sh
    fi
    echo -e "ORCHESTRATOR=$ORCHESTRATOR"                | ./boxes.sh
    echo -e "exporting STOREBASE=$STOREBASE "           | ./boxes.sh
    export STOREBASE=$STOREBASE
    export SOURCEDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
    echo -e "exporting SOURCEDIR=$SOURCEDIR "                           | ./boxes.sh
windowBottom

title -d 1 "Destroying pfcon containerized dev environment on $ORCHESTRATOR"
    if [[ $ORCHESTRATOR == swarm ]]; then
        echo "docker stack rm pfcon_dev_stack"                               | ./boxes.sh ${LightCyan}
        docker stack rm pfcon_dev_stack
        if (( b_pfconInNetwork )) ; then
            echo "docker volume rm -f pfcon_dev_stack_swift_storage_dev"
            sleep 15
            docker volume rm pfcon_dev_stack_swift_storage_dev
        fi
    elif [[ $ORCHESTRATOR == kubernetes ]]; then
        if (( b_pfconInNetwork )) ; then
            echo "kubectl delete -f kubernetes/pfcon_dev_innetwork.yaml"     | ./boxes.sh ${LightCyan}
            kubectl delete -f kubernetes/pfcon_dev_innetwork.yaml
            echo "Removing swift_storage folder $SOURCEDIR/swift_storage"  | ./boxes.sh
            rm -fr $SOURCEDIR/swift_storage
        else
            echo "kubectl delete -f kubernetes/pfcon_dev.yaml"               | ./boxes.sh ${LightCyan}
            kubectl delete -f kubernetes/pfcon_dev.yaml
        fi
    fi
    echo "Removing STOREBASE tree $STOREBASE"                                | ./boxes.sh
    rm -fr $STOREBASE
windowBottom
