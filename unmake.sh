#!/bin/bash
#
# NAME
#
#   unmake.sh
#
# SYNPOSIS
#
#   make.sh                     [-O <swarm|kubernetes>]
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
#   Destroy pfcon dev instance on Kubernetes:
#
#       unmake.sh -O kubernetes
#
# ARGS
#
#
#   -O <swarm|kubernetes>
#
#       Explicitly set the orchestrator. Default is swarm.
#
#

source ./decorate.sh

declare -i STEP=0
ORCHESTRATOR=swarm

print_usage () {
    echo "Usage: ./unmake.sh [-O <swarm|kubernetes>]"
    exit 1
}

while getopts ":O:" opt; do
    case $opt in
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

title -d 1 "Destroying pfcon containerized dev environment on $ORCHESTRATOR"
    if [[ $ORCHESTRATOR == swarm ]]; then
        echo "docker stack rm pfcon_dev_stack"                               | ./boxes.sh ${LightCyan}
        docker stack rm pfcon_dev_stack
    elif [[ $ORCHESTRATOR == kubernetes ]]; then
        echo "kubectl delete -f kubernetes/pfcon_dev.yaml"                   | ./boxes.sh ${LightCyan}
        kubectl delete -f kubernetes/pfcon_dev.yaml
    fi
    echo "Removing ./FS tree"                                       | ./boxes.sh
    rm -fr ./FS
windowBottom
